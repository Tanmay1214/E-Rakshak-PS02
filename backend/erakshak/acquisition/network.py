"""Acquire network configuration and connection data.

Runs a set of ``dumpsys`` and shell commands to capture the device's
current network state: interfaces, IP addresses, Wi-Fi, cellular,
Bluetooth, routes, and active TCP/UDP connections.

Output artefacts
----------------
- ``raw/system/dumpsys_connectivity.txt``
- ``raw/system/dumpsys_wifi.txt``
- ``raw/system/dumpsys_telephony.txt``
- ``raw/system/dumpsys_bluetooth.txt``
- ``raw/system/ip_addr.txt``
- ``raw/system/ip_route.txt``
- ``raw/system/netstat.txt``
- ``derived/network_summary.json``
- ``derived/network_connections.jsonl``
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_telephony_text(text: str) -> dict:
    """Quick extraction of mobile-operator and SIM info from dumpsys."""
    info: dict = {"mobile_operator": None, "sim_info": None}

    op_match = re.search(r"mOperatorAlphaLong\s*=\s*(\S+)", text)
    if op_match:
        info["mobile_operator"] = op_match.group(1)

    sim_match = re.search(r"mSimState\s*=\s*(\S+)", text)
    if sim_match:
        info["sim_info"] = sim_match.group(1)

    return info


def _parse_bluetooth_devices(text: str) -> list[str]:
    """Return unique Bluetooth device names (capped at 50)."""
    matches = re.findall(r"name\s*=\s*(.+?)(?:,|\n)", text)
    seen: set[str] = set()
    unique: list[str] = []
    for name in matches:
        stripped = name.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            unique.append(stripped)
            if len(unique) >= 50:
                break
    return unique


# ---------------------------------------------------------------------------
# Command table
# ---------------------------------------------------------------------------

def _build_command_table(
    dumpsys_timeout: int, default_timeout: int,
) -> list[dict]:
    """Return the list of shell commands to execute."""
    return [
        {
            "args": ["dumpsys", "connectivity"],
            "file": "dumpsys_connectivity.txt",
            "action": "dumpsys_connectivity",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "wifi"],
            "file": "dumpsys_wifi.txt",
            "action": "dumpsys_wifi",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "telephony.registry"],
            "file": "dumpsys_telephony.txt",
            "action": "dumpsys_telephony",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "bluetooth_manager"],
            "file": "dumpsys_bluetooth.txt",
            "action": "dumpsys_bluetooth",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["ip", "addr"],
            "file": "ip_addr.txt",
            "action": "ip_addr",
            "timeout": default_timeout,
        },
        {
            "args": ["ip", "route"],
            "file": "ip_route.txt",
            "action": "ip_route",
            "timeout": default_timeout,
        },
        {
            "args": ["netstat"],
            "file": "netstat.txt",
            "action": "netstat",
            "timeout": default_timeout,
        },
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def acquire_network(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Collect network information.

    Runs connectivity, Wi-Fi, telephony, Bluetooth, IP, route and
    ``netstat`` commands.  Raw outputs are persisted; parsed data is
    written as a summary JSON and a connections JSONL.

    Parameters
    ----------
    adb : ADBClient
        Connected ADB wrapper.
    case_folder : CaseFolder
        Open case folder.
    manifest : ManifestWriter
        Manifest writer.
    audit : AuditLogger
        Audit trail logger.

    Returns
    -------
    dict
        Summary with ``status`` and ``warnings``.
    """
    from erakshak.adb.parsers import (
        parse_ip_addr,
        parse_ip_route,
        parse_netstat,
        parse_dumpsys_wifi,
    )
    from erakshak.config.defaults import (
        DUMPSYS_TIMEOUT,
        DEFAULT_ADB_TIMEOUT,
        STATUS_ACQUIRED,
        STATUS_FAILED,
        STATUS_COMMAND_UNAVAILABLE,
    )

    results: dict = {"status": STATUS_ACQUIRED, "warnings": []}

    commands = _build_command_table(DUMPSYS_TIMEOUT, DEFAULT_ADB_TIMEOUT)
    raw_outputs: dict[str, str] = {}

    # ---- 1. Run all network commands ----------------------------------------
    for cmd in commands:
        cmd_str = f"adb shell {' '.join(cmd['args'])}"
        try:
            r = adb.shell(
                cmd["args"],
                timeout=cmd["timeout"],
                audit_action=cmd["action"],
            )
            raw_path: Path = case_folder.raw_system_dir / cmd["file"]

            if r.return_code == 0 and not r.timed_out:
                raw_path.write_text(r.stdout, encoding="utf-8")
                manifest.add_file(
                    f"network_{cmd['action']}", "adb_command",
                    cmd_str, raw_path,
                )
                raw_outputs[cmd["file"]] = r.stdout
            else:
                reason = "timed_out" if r.timed_out else f"rc={r.return_code}"
                status = (
                    STATUS_COMMAND_UNAVAILABLE
                    if "not found" in r.stderr.lower()
                    else STATUS_FAILED
                )
                manifest.add_status_record(
                    f"network_{cmd['action']}", "adb_command",
                    cmd_str, status, reason,
                )
                results["warnings"].append(f"{cmd['action']}: {status}")
        except Exception as exc:  # noqa: BLE001
            results["warnings"].append(
                f"{cmd['action']} exception: {exc!s}"
            )

    # ---- 2. Build network summary -------------------------------------------
    summary: dict = {
        "current_ip": None,
        "wifi_ssid": None,
        "saved_wifi_networks": [],
        "mac_address": None,
        "sim_info": None,
        "mobile_operator": None,
        "bluetooth_devices": [],
        "vpn_active": None,
        "dns_servers": [],
        "default_route": None,
        "interfaces": [],
    }

    # 2a. ip addr → interfaces, wlan IP, MAC
    if "ip_addr.txt" in raw_outputs:
        interfaces = parse_ip_addr(raw_outputs["ip_addr.txt"])
        summary["interfaces"] = interfaces
        for iface in interfaces:
            if "wlan" in iface.get("name", "").lower():
                ipv4 = iface.get("ipv4")
                if isinstance(ipv4, list) and ipv4:
                    summary["current_ip"] = ipv4[0]
                elif isinstance(ipv4, str) and ipv4:
                    summary["current_ip"] = ipv4
                if iface.get("mac"):
                    summary["mac_address"] = iface["mac"]

    # 2b. ip route → default gateway
    if "ip_route.txt" in raw_outputs:
        routes = parse_ip_route(raw_outputs["ip_route.txt"])
        for route in routes:
            if route.get("destination") == "default":
                summary["default_route"] = route
                break

    # 2c. Wi-Fi → SSID + saved networks
    if "dumpsys_wifi.txt" in raw_outputs:
        wifi_info = parse_dumpsys_wifi(raw_outputs["dumpsys_wifi.txt"])
        summary["wifi_ssid"] = wifi_info.get("current_ssid")
        summary["saved_wifi_networks"] = wifi_info.get("saved_networks", [])

    # 2d. Telephony → operator + SIM state
    if "dumpsys_telephony.txt" in raw_outputs:
        tel_info = _parse_telephony_text(raw_outputs["dumpsys_telephony.txt"])
        summary["mobile_operator"] = tel_info["mobile_operator"]
        summary["sim_info"] = tel_info["sim_info"]

    # 2e. Bluetooth → paired device names
    if "dumpsys_bluetooth.txt" in raw_outputs:
        summary["bluetooth_devices"] = _parse_bluetooth_devices(
            raw_outputs["dumpsys_bluetooth.txt"]
        )

    # ---- 3. VPN detection heuristic ----------------------------------------
    if "dumpsys_connectivity.txt" in raw_outputs:
        conn_text = raw_outputs["dumpsys_connectivity.txt"]
        summary["vpn_active"] = bool(
            re.search(r"VPN", conn_text, re.IGNORECASE)
        )
        # DNS servers (common in newer Android output)
        dns_matches = re.findall(
            r"DnsServer\s*[:=]\s*[\[/]*([\d.]+)", conn_text,
        )
        summary["dns_servers"] = list(dict.fromkeys(dns_matches))  # unique

    # ---- 4. Write network_summary.json --------------------------------------
    summary_path: Path = case_folder.derived_dir / "network_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False, default=str)
    manifest.add_file(
        "network_summary", "parsed", "network commands", summary_path,
    )

    # ---- 5. Parse active connections (netstat) ------------------------------
    connections: list[dict] = []
    if "netstat.txt" in raw_outputs:
        connections = parse_netstat(raw_outputs["netstat.txt"])

    connections_path: Path = case_folder.derived_dir / "network_connections.jsonl"
    with open(connections_path, "w", encoding="utf-8") as fh:
        for conn in connections:
            fh.write(json.dumps(conn, ensure_ascii=False) + "\n")
    manifest.add_file(
        "network_connections", "parsed", "netstat", connections_path,
    )

    # ---- 6. Finalise --------------------------------------------------------
    if results["warnings"]:
        results["status"] = "partial"

    audit.log(
        action="network_acquired",
        command_category="network",
        result=results["status"],
        output_path=str(summary_path),
    )

    return results
