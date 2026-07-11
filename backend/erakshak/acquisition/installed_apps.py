"""Installed application acquisition for E-RAKSHAK.

Enumerates all packages (system and third-party) via ``pm list packages``
and enriches each record with version, permissions, and install-time data
from ``dumpsys package``.  Produces a JSONL manifest of every installed
application and a JSON summary of notable permission grants.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from erakshak.adb.client import ADBClient, ADBResult
from erakshak.adb.parsers import parse_packages, parse_dumpsys_package_detail
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.config.defaults import (
    DUMPSYS_TIMEOUT,
    LONG_ADB_TIMEOUT,
    STATUS_ACQUIRED,
    STATUS_FAILED,
)

# Permissions that are forensically significant (access to comms,
# location, media, or sensor data).
_NOTABLE_PERMISSIONS: list[str] = [
    "android.permission.READ_CALL_LOG",
    "android.permission.READ_SMS",
    "android.permission.READ_CONTACTS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_EXTERNAL_STORAGE",
]


def acquire_installed_apps(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
) -> dict:
    """Collect installed application information.

    Runs the following read-only commands:
    - ``adb shell pm list packages -f -U --show-versioncode``  (all)
    - ``adb shell pm list packages -f -3 -U --show-versioncode``  (3rd-party)
    - ``adb shell pm list packages -f -s -U --show-versioncode``  (system)
    - ``adb shell dumpsys package``  (detailed package metadata)

    Writes:
    - ``raw/system/packages_all.txt``
    - ``raw/system/packages_third_party.txt``
    - ``raw/system/packages_system.txt``
    - ``raw/system/dumpsys_package.txt``
    - ``derived/installed_apps.jsonl``
    - ``derived/app_permission_summary.json``

    Args:
        adb: An initialised ADBClient bound to the target device serial.
        case_folder: CaseFolder providing output paths.
        manifest: ManifestWriter for recording acquired artifacts.
        audit: AuditLogger for the forensic audit trail.

    Returns:
        A dict with acquisition ``status``, ``app_count``, and ``warnings``.
    """
    results: dict[str, Any] = {"status": "acquired", "app_count": 0, "warnings": []}
    started_at: str = datetime.now(timezone.utc).isoformat()

    # ── pm list packages (all) ───────────────────────────────────────
    all_pkg_result: ADBResult = adb.shell(
        ["pm", "list", "packages", "--user", "0", "-f", "-U", "--show-versioncode"],
        timeout=LONG_ADB_TIMEOUT,
        audit_action="pm_list_all",
    )
    raw_all: Path = case_folder.raw_system_dir / "packages_all.txt"
    if all_pkg_result.return_code == 0:
        raw_all.write_text(all_pkg_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="packages_all",
            source_type="adb_command",
            source_command_or_path="pm list packages --user 0 -f -U --show-versioncode",
            destination_path=raw_all,
            status=STATUS_ACQUIRED,
            reason_code=None,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── pm list packages (third-party) ───────────────────────────────
    tp_result: ADBResult = adb.shell(
        ["pm", "list", "packages", "--user", "0", "-f", "-3", "-U", "--show-versioncode"],
        timeout=LONG_ADB_TIMEOUT,
        audit_action="pm_list_third_party",
    )
    raw_tp: Path = case_folder.raw_system_dir / "packages_third_party.txt"
    if tp_result.return_code == 0:
        raw_tp.write_text(tp_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="packages_third_party",
            source_type="adb_command",
            source_command_or_path="pm list packages --user 0 -f -3 -U --show-versioncode",
            destination_path=raw_tp,
            status=STATUS_ACQUIRED,
            reason_code=None,
        )

    # ── pm list packages (system) ────────────────────────────────────
    sys_result: ADBResult = adb.shell(
        ["pm", "list", "packages", "--user", "0", "-f", "-s", "-U", "--show-versioncode"],
        timeout=LONG_ADB_TIMEOUT,
        audit_action="pm_list_system",
    )
    raw_sys: Path = case_folder.raw_system_dir / "packages_system.txt"
    if sys_result.return_code == 0:
        raw_sys.write_text(sys_result.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="packages_system",
            source_type="adb_command",
            source_command_or_path="pm list packages --user 0 -f -s -U --show-versioncode",
            destination_path=raw_sys,
            status=STATUS_ACQUIRED,
            reason_code=None,
        )

    # ── Parse package lists ──────────────────────────────────────────
    all_packages: list[dict] = (
        parse_packages(all_pkg_result.stdout)
        if all_pkg_result.return_code == 0
        else []
    )

    tp_packages: set[str] = set()
    if tp_result.return_code == 0:
        for p in parse_packages(tp_result.stdout):
            tp_packages.add(p.get("package_name", ""))

    sys_packages: set[str] = set()
    if sys_result.return_code == 0:
        for p in parse_packages(sys_result.stdout):
            sys_packages.add(p.get("package_name", ""))

    # ── dumpsys package (large output, long timeout) ─────────────────
    dumpsys_pkg_result: ADBResult = adb.shell(
        ["dumpsys", "package"],
        timeout=LONG_ADB_TIMEOUT,
        audit_action="dumpsys_package",
    )
    raw_dumpsys: Path = case_folder.raw_system_dir / "dumpsys_package.txt"
    dumpsys_text: str = ""

    if dumpsys_pkg_result.return_code == 0:
        dumpsys_text = dumpsys_pkg_result.stdout
        raw_dumpsys.write_text(dumpsys_text, encoding="utf-8")
        manifest.add_file(
            artifact_class="dumpsys_package",
            source_type="adb_command",
            source_command_or_path="dumpsys package",
            destination_path=raw_dumpsys,
            status=STATUS_ACQUIRED,
            reason_code=None,
        )
    else:
        results["warnings"].append("dumpsys package failed or timed out")

    # ── Build enriched JSONL + permission summary ────────────────────
    apps_jsonl_path: Path = case_folder.derived_dir / "installed_apps.jsonl"
    permission_summary: dict[str, Any] = {
        "total_apps": 0,
        "third_party_apps": 0,
        "system_apps": 0,
        "notable_permissions": {},
    }

    with open(apps_jsonl_path, "w", encoding="utf-8") as f:
        for pkg in all_packages:
            pkg_name: str = pkg.get("package_name", "")
            is_system: bool = pkg_name in sys_packages
            is_third_party: bool = pkg_name in tp_packages

            # Enrich with dumpsys detail when available
            detail: dict = {}
            if dumpsys_text:
                detail = parse_dumpsys_package_detail(dumpsys_text, pkg_name)

            app_record: dict[str, Any] = {
                "package_name": pkg_name,
                "app_name": detail.get("app_name"),
                "apk_path": pkg.get("apk_path", ""),
                "install_time": detail.get("first_install_time"),
                "last_update_time": detail.get("last_update_time"),
                "version_name": detail.get("version_name"),
                "version_code": pkg.get("version_code"),
                "requested_permissions": detail.get("requested_permissions", []),
                "granted_permissions": detail.get("granted_permissions", []),
                "uid": pkg.get("uid"),
                "is_system_app": is_system,
                "source_command": "pm list packages + dumpsys package",
                "parse_confidence": "high" if detail else "basic",
            }
            f.write(json.dumps(app_record, ensure_ascii=False) + "\n")

            # ── Aggregate counts ─────────────────────────────────────
            permission_summary["total_apps"] += 1
            if is_third_party:
                permission_summary["third_party_apps"] += 1
            if is_system:
                permission_summary["system_apps"] += 1

            # ── Track forensically notable permission grants ─────────
            for perm in detail.get("granted_permissions", []):
                if perm in _NOTABLE_PERMISSIONS:
                    perm_list: list[str] = permission_summary[
                        "notable_permissions"
                    ].setdefault(perm, [])
                    perm_list.append(pkg_name)

    manifest.add_file(
        artifact_class="installed_apps",
        source_type="parsed",
        source_command_or_path="pm+dumpsys package",
        destination_path=apps_jsonl_path,
        status=STATUS_ACQUIRED,
        reason_code=None,
    )

    # ── Write permission summary ─────────────────────────────────────
    perm_summary_path: Path = case_folder.derived_dir / "app_permission_summary.json"
    with open(perm_summary_path, "w", encoding="utf-8") as f:
        json.dump(permission_summary, f, indent=2, ensure_ascii=False)
    manifest.add_file(
        artifact_class="app_permission_summary",
        source_type="parsed",
        source_command_or_path="pm+dumpsys package",
        destination_path=perm_summary_path,
        status=STATUS_ACQUIRED,
        reason_code=None,
    )

    results["app_count"] = permission_summary["total_apps"]

    completed_at: str = datetime.now(timezone.utc).isoformat()
    audit.log(
        action="installed_apps_acquired",
        command_category="apps",
        command_redacted="pm list packages + dumpsys package",
        result=results["status"],
        return_code=0,
        duration_ms=None,
        output_path=str(apps_jsonl_path),
        warning="; ".join(results["warnings"]) if results["warnings"] else None,
        error=None,
    )

    return results
