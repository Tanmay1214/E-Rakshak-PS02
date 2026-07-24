"""Device identity and software information acquisition for E-RAKSHAK.

Collects hardware identifiers, build properties, kernel details, and
security configuration via read-only ADB commands.  Produces both raw
text captures and structured JSON summaries.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from erakshak.adb.client import ADBClient, ADBResult
from erakshak.adb.parsers import parse_getprop, parse_location_dumpsys
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.config.defaults import (
    DEFAULT_ADB_TIMEOUT,
    STATUS_ACQUIRED,
    STATUS_FAILED,
    STATUS_NOT_EXPOSED,
)


def acquire_device_info(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
) -> dict:
    """Collect device identity and software info.

    Runs the following read-only commands:
    - ``adb shell getprop``
    - ``adb shell settings get global device_name``
    - ``adb shell cat /proc/cpuinfo``
    - ``adb shell uname -a``
    - ``adb shell cat /proc/version``
    - ``adb shell getenforce``

    Writes:
    - ``raw/system/getprop.txt``
    - ``raw/system/cpuinfo.txt``
    - ``raw/system/uname.txt``
    - ``raw/system/proc_version.txt``
    - ``derived/device_identity.json``
    - ``derived/software_summary.json``

    Args:
        adb: An initialised ADBClient bound to the target device serial.
        case_folder: CaseFolder providing output paths.
        manifest: ManifestWriter for recording acquired artifacts.
        audit: AuditLogger for the forensic audit trail.

    Returns:
        A dict containing ``device_identity``, ``software_summary``,
        acquisition ``status``, and any ``warnings``.
    """
    results: dict[str, Any] = {"status": "acquired", "warnings": []}
    started_at: str = datetime.now(timezone.utc).isoformat()

    # ── getprop ──────────────────────────────────────────────────────
    getprop_result: ADBResult = adb.shell(
        ["getprop"], timeout=DEFAULT_ADB_TIMEOUT, audit_action="getprop"
    )
    raw_getprop_path: Path = case_folder.raw_system_dir / "getprop.txt"
    props: dict[str, str] = {}

    if getprop_result.return_code == 0:
        raw_getprop_path.write_text(getprop_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="device_properties",
            source_type="adb_command",
            source_command_or_path="adb shell getprop",
            destination_path=raw_getprop_path,
            status=STATUS_ACQUIRED,
            reason_code=None,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        props = parse_getprop(getprop_result.stdout)
    else:
        results["warnings"].append("getprop failed")
        results["status"] = "partial"
        manifest.add_status_record(
            artifact_class="device_properties",
            source_type="adb_command",
            source_command_or_path="adb shell getprop",
            status=STATUS_FAILED,
            reason_code=str(getprop_result.stderr),
        )

    # ── device_name ──────────────────────────────────────────────────
    devname_result: ADBResult = adb.shell(
        ["settings", "get", "global", "device_name"],
        audit_action="device_name",
    )
    device_name: str | None = (
        devname_result.stdout.strip()
        if devname_result.return_code == 0
        else None
    )
    if device_name == "null":
        device_name = None

    # ── cpuinfo ──────────────────────────────────────────────────────
    cpuinfo_result: ADBResult = adb.shell(
        ["cat", "/proc/cpuinfo"], audit_action="cpuinfo"
    )
    cpuinfo_path: Path = case_folder.raw_system_dir / "cpuinfo.txt"
    if cpuinfo_result.return_code == 0:
        cpuinfo_path.write_text(cpuinfo_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="cpu_info",
            source_type="adb_command",
            source_command_or_path="adb shell cat /proc/cpuinfo",
            destination_path=cpuinfo_path,
            status=STATUS_ACQUIRED,
            reason_code=None,
        )

    # ── uname ────────────────────────────────────────────────────────
    uname_result: ADBResult = adb.shell(
        ["uname", "-a"], audit_action="uname"
    )
    uname_path: Path = case_folder.raw_system_dir / "uname.txt"
    if uname_result.return_code == 0:
        uname_path.write_text(uname_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="kernel_info",
            source_type="adb_command",
            source_command_or_path="adb shell uname -a",
            destination_path=uname_path,
            status=STATUS_ACQUIRED,
            reason_code=None,
        )

    # ── /proc/version ────────────────────────────────────────────────
    procver_result: ADBResult = adb.shell(
        ["cat", "/proc/version"], audit_action="proc_version"
    )
    procver_path: Path = case_folder.raw_system_dir / "proc_version.txt"
    if procver_result.return_code == 0:
        procver_path.write_text(procver_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="kernel_version",
            source_type="adb_command",
            source_command_or_path="adb shell cat /proc/version",
            destination_path=procver_path,
            status=STATUS_ACQUIRED,
            reason_code=None,
        )

    # ── getenforce ───────────────────────────────────────────────────
    se_result: ADBResult = adb.shell(
        ["getenforce"], audit_action="getenforce"
    )
    selinux: str = (
        se_result.stdout.strip() if se_result.return_code == 0 else "unknown"
    )

    # ── dumpsys location ──────────────────────────────────────────────
    location_result: ADBResult = adb.shell(
        ["dumpsys", "location"], timeout=DEFAULT_ADB_TIMEOUT, audit_action="dumpsys_location"
    )
    raw_location_path: Path = case_folder.raw_system_dir / "dumpsys_location.txt"
    location_list = []
    
    if location_result.return_code == 0:
        raw_location_path.write_text(location_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="dumpsys_location",
            source_type="adb_command",
            source_command_or_path="adb shell dumpsys location",
            destination_path=raw_location_path,
            status=STATUS_ACQUIRED,
            reason_code=None,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        location_list = parse_location_dumpsys(location_result.stdout)
    else:
        results["warnings"].append("dumpsys location failed")
        results["status"] = "partial"
        manifest.add_status_record(
            artifact_class="dumpsys_location",
            source_type="adb_command",
            source_command_or_path="adb shell dumpsys location",
            status=STATUS_FAILED,
            reason_code=str(location_result.stderr),
        )

    # Save derived/device_location.json
    location_path: Path = case_folder.derived_dir / "device_location.json"
    with open(location_path, "w", encoding="utf-8") as f:
        json.dump({"last_known_locations": location_list}, f, indent=2, ensure_ascii=False)
    manifest.add_file(
        artifact_class="device_location",
        source_type="parsed",
        source_command_or_path="dumpsys location",
        destination_path=location_path,
        status=STATUS_ACQUIRED if location_list else STATUS_NOT_EXPOSED,
        reason_code=None if location_list else "No active locations cached",
    )

    # ── Helper: safe property lookup ─────────────────────────────────
    def prop(key: str, default: str = "not_exposed") -> str:
        """Return a system property value or *default* if missing."""
        return props.get(key, default)

    # ── Build device_identity.json ───────────────────────────────────
    device_identity: dict[str, Any] = {
        "manufacturer": prop("ro.product.manufacturer"),
        "brand": prop("ro.product.brand"),
        "model": prop("ro.product.model"),
        "device": prop("ro.product.device"),
        "product_name": prop("ro.product.name"),
        "board": prop("ro.product.board"),
        "hardware": prop("ro.hardware"),
        "device_name": device_name,
        "serial_prop": prop("ro.serialno"),
        "adb_serial": adb.serial,
        "build_fingerprint": prop("ro.build.fingerprint"),
        "cpu_abi": prop("ro.product.cpu.abi"),
    }

    identity_path: Path = case_folder.derived_dir / "device_identity.json"
    with open(identity_path, "w", encoding="utf-8") as f:
        json.dump(device_identity, f, indent=2, ensure_ascii=False)
    manifest.add_file(
        artifact_class="device_identity",
        source_type="parsed",
        source_command_or_path="getprop+settings",
        destination_path=identity_path,
        status=STATUS_ACQUIRED,
        reason_code=None,
    )

    # ── Build software_summary.json ──────────────────────────────────
    software_summary: dict[str, Any] = {
        "android_release": prop("ro.build.version.release"),
        "sdk_level": prop("ro.build.version.sdk"),
        "security_patch": prop("ro.build.version.security_patch"),
        "build_id": prop("ro.build.id"),
        "build_display_id": prop("ro.build.display.id"),
        "build_fingerprint": prop("ro.build.fingerprint"),
        "build_date": prop("ro.build.date"),
        "kernel_version": (
            uname_result.stdout.strip()
            if uname_result.return_code == 0
            else "unknown"
        ),
        "selinux_status": selinux,
        "verified_boot_state": prop("ro.boot.verifiedbootstate"),
        "verified_boot_hash": prop("ro.boot.vbmeta.digest"),
        "flash_locked": prop("ro.boot.flash.locked"),
        "encryption_state": prop("ro.crypto.state"),
        "encryption_type": prop("ro.crypto.type"),
    }

    software_path: Path = case_folder.derived_dir / "software_summary.json"
    with open(software_path, "w", encoding="utf-8") as f:
        json.dump(software_summary, f, indent=2, ensure_ascii=False)
    manifest.add_file(
        artifact_class="software_summary",
        source_type="parsed",
        source_command_or_path="getprop+uname+getenforce",
        destination_path=software_path,
        status=STATUS_ACQUIRED,
        reason_code=None,
    )

    completed_at: str = datetime.now(timezone.utc).isoformat()
    audit.log(
        action="device_info_acquired",
        command_category="device_info",
        command_redacted="getprop+settings+cpuinfo+uname+getenforce",
        result=results["status"],
        return_code=0,
        duration_ms=None,
        output_path=str(case_folder.derived_dir),
        warning="; ".join(results["warnings"]) if results["warnings"] else None,
        error=None,
    )

    return {
        "device_identity": device_identity,
        "software_summary": software_summary,
        **results,
    }
