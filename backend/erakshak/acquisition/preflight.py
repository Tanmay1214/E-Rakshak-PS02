"""Preflight checks for E-RAKSHAK acquisition.

Validates device connectivity, collects basic device information,
and writes a preflight.json summary before full acquisition begins.
All commands are read-only and forensically safe.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from erakshak.adb.client import ADBClient, ADBResult
from erakshak.adb.parsers import parse_adb_devices, parse_battery_info
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.config.defaults import DUMPSYS_TIMEOUT


def run_preflight(
    adb: ADBClient,
    case_folder: CaseFolder,
    case_id: str,
    exhibit_id: str,
    manifest: ManifestWriter,
    audit: AuditLogger,
) -> dict:
    """Run preflight checks and write preflight.json.

    Runs the following read-only commands against the connected device:
    - adb version
    - adb devices -l
    - adb shell date
    - adb shell getprop ro.product.model
    - adb shell getprop ro.build.version.release
    - adb shell getprop ro.build.version.security_patch
    - adb shell dumpsys battery
    - adb shell getenforce
    - adb shell su -c id  (detect if root is already available; does NOT run adb root)

    Writes ``acquisition/preflight.json`` and records the artifact in the
    manifest/audit trail.

    Args:
        adb: An initialised ADBClient bound to the target device serial.
        case_folder: CaseFolder providing output paths.
        case_id: Human-assigned case identifier.
        exhibit_id: Human-assigned exhibit identifier.
        manifest: ManifestWriter for recording acquired artifacts.
        audit: AuditLogger for the forensic audit trail.

    Returns:
        A dict with preflight results including device info, battery,
        SELinux status, root availability, warnings, and overall result.
    """
    warnings: list[str] = []
    started_at: str = datetime.now(timezone.utc).isoformat()

    # ── adb version ──────────────────────────────────────────────────
    adb_version_result: ADBResult = adb.get_adb_version()
    if adb_version_result.return_code == 0:
        adb_version = adb_version_result.stdout.strip().split("\n")[0]
    else:
        adb_version = "unknown"

    # ── adb devices -l ───────────────────────────────────────────────
    devices_result: ADBResult = adb.get_devices()
    connected_devices: list[dict] = parse_adb_devices(devices_result.stdout)

    # Determine state of the selected device
    device_state = "unknown"
    for dev in connected_devices:
        if dev.get("serial") == adb.serial:
            device_state = dev.get("state", "unknown")
            break

    # ── shell date ───────────────────────────────────────────────────
    date_result: ADBResult = adb.shell(["date"], audit_action="preflight_date")
    device_time_raw = (
        date_result.stdout.strip()
        if date_result.return_code == 0
        else "unavailable"
    )

    # ── getprop ro.product.model ─────────────────────────────────────
    model_result: ADBResult = adb.shell(
        ["getprop", "ro.product.model"], audit_action="preflight_model"
    )
    model = (
        model_result.stdout.strip()
        if model_result.return_code == 0
        else "unknown"
    )

    # ── getprop ro.build.version.release ─────────────────────────────
    release_result: ADBResult = adb.shell(
        ["getprop", "ro.build.version.release"], audit_action="preflight_release"
    )
    android_release = (
        release_result.stdout.strip()
        if release_result.return_code == 0
        else "unknown"
    )

    # ── getprop ro.build.version.security_patch ──────────────────────
    patch_result: ADBResult = adb.shell(
        ["getprop", "ro.build.version.security_patch"],
        audit_action="preflight_patch",
    )
    security_patch = (
        patch_result.stdout.strip()
        if patch_result.return_code == 0
        else "unknown"
    )

    # ── dumpsys battery ──────────────────────────────────────────────
    battery_result: ADBResult = adb.shell(
        ["dumpsys", "battery"],
        timeout=DUMPSYS_TIMEOUT,
        audit_action="preflight_battery",
    )
    battery_summary: dict = {}
    if battery_result.return_code == 0:
        battery_summary = parse_battery_info(battery_result.stdout)
    else:
        warnings.append("Battery info unavailable")
        battery_summary = {"status": "unavailable"}

    # ── getenforce ───────────────────────────────────────────────────
    selinux_result: ADBResult = adb.shell(
        ["getenforce"], audit_action="preflight_selinux"
    )
    selinux_status = (
        selinux_result.stdout.strip()
        if selinux_result.return_code == 0
        else "unknown"
    )

    # ── su -c id  (root detection only – never runs adb root) ────────
    su_result: ADBResult = adb.shell(
        ["su", "-c", "id"], timeout=5, audit_action="preflight_root_check"
    )
    root_available: bool | str
    if su_result.return_code == 0 and "uid=0" in su_result.stdout:
        root_available = True
    elif su_result.timed_out:
        root_available = "unknown"
        warnings.append("Root check timed out")
    else:
        root_available = False

    # ── Assemble preflight data ──────────────────────────────────────
    host_timestamp_utc: str = datetime.now(timezone.utc).isoformat()

    preflight_data: dict = {
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "selected_serial": adb.serial,
        "adb_version": adb_version,
        "connected_devices": connected_devices,
        "device_state": device_state,
        "host_timestamp_utc": host_timestamp_utc,
        "device_time_raw": device_time_raw,
        "device_model": model,
        "android_version": android_release,
        "security_patch": security_patch,
        "battery_summary": battery_summary,
        "selinux_status": selinux_status,
        "root_available": root_available,
        "warnings": warnings,
        "result": "pass" if device_state == "device" else "fail",
    }

    # ── Write preflight.json ─────────────────────────────────────────
    preflight_path: Path = case_folder.preflight_path
    with open(preflight_path, "w", encoding="utf-8") as f:
        json.dump(preflight_data, f, indent=2, ensure_ascii=False)

    completed_at: str = datetime.now(timezone.utc).isoformat()
    manifest.add_file(
        artifact_class="preflight",
        source_type="adb_commands",
        source_command_or_path="preflight_checks",
        destination_path=preflight_path,
        status="acquired",
        reason_code=None,
        started_at=started_at,
        completed_at=completed_at,
    )

    audit.log(
        action="preflight_complete",
        command_category="preflight",
        command_redacted="preflight_checks",
        result=preflight_data["result"],
        return_code=0,
        duration_ms=None,
        output_path=str(preflight_path),
        warning="; ".join(warnings) if warnings else None,
        error=None,
    )

    return preflight_data
