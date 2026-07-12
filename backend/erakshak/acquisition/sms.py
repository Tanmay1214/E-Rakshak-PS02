"""Acquire SMS messages from the Android device.

Attempts to query SMS directly via the Android content provider using ADB.
If blocked by Android's security model (SecurityException, permission denied,
etc.), it falls back to importing exported SMS from the companion
collector app's output.

Output artefacts
----------------
- ``raw/system/content_sms.txt``         – verbatim content query output (if successful)
- ``raw/collector/sms.jsonl``            – copied collector output (if fallback is used)
- ``derived/sms_messages.jsonl``         – normalised SMS records (from either source)
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


def acquire_sms(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
    collector_folder: str | None = None,
) -> dict[str, Any]:
    """Acquire SMS messages.

    First tries querying content://sms using ADB.
    If that fails, falls back to the collector folder if provided.
    """
    from erakshak.adb.parsers import parse_content_query
    from erakshak.case.hashing import hash_file
    from erakshak.config.defaults import (
        CONTENT_QUERY_TIMEOUT,
        STATUS_ACQUIRED,
        STATUS_ACQUIRED_FROM_COLLECTOR,
        STATUS_FAILED,
        STATUS_PERMISSION_DENIED,
    )
    from erakshak.acquisition.collector_import import _validate_jsonl

    results: dict[str, Any] = {
        "status": STATUS_FAILED,
        "message_count": 0,
        "warnings": [],
        "source": "none",
    }
    started_at = datetime.now(timezone.utc).isoformat()

    # ── Try ADB Content Query ───────────────────────────────────────────────
    query_cmd = ["content", "query", "--uri", "content://sms"]
    adb_res = adb.shell(
        query_cmd,
        timeout=CONTENT_QUERY_TIMEOUT,
        audit_action="content_query_sms",
    )

    is_adb_successful = False
    if adb_res.return_code == 0 and not adb_res.timed_out:
        stdout = adb_res.stdout
        # SecurityException/Permission denial is often printed to stdout or stderr
        if "SecurityException" not in stdout and "Permission Denial" not in stdout and "Error" not in stdout:
            is_adb_successful = True

    if is_adb_successful:
        # Write raw output
        raw_path = case_folder.raw_system_dir / "content_sms.txt"
        raw_path.write_text(adb_res.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="sms_raw",
            source_type="adb_command",
            source_command_or_path="adb shell content query --uri content://sms",
            destination_path=raw_path,
            status=STATUS_ACQUIRED,
            started_at=started_at,
        )

        # Parse SMS
        parsed_sms = parse_content_query(adb_res.stdout)
        results["message_count"] = len(parsed_sms)

        # Write derived sms_messages.jsonl
        derived_path = case_folder.derived_dir / "sms_messages.jsonl"
        with open(derived_path, "w", encoding="utf-8") as fh:
            for msg in parsed_sms:
                fh.write(json.dumps(msg, ensure_ascii=False) + "\n")

        manifest.add_file(
            artifact_class="sms",
            source_type="adb_command",
            source_command_or_path="adb shell content query --uri content://sms",
            destination_path=derived_path,
            status=STATUS_ACQUIRED,
            started_at=started_at,
        )

        results["status"] = STATUS_ACQUIRED
        results["source"] = "adb"
        audit.log(
            action="sms_acquired_via_adb",
            command_category="sms",
            result=STATUS_ACQUIRED,
            output_path=str(derived_path),
        )
        return results

    # ── Fallback to Collector Export ────────────────────────────────────────
    results["warnings"].append(
        "ADB SMS query blocked or failed. Attempting fallback to collector export."
    )
    audit.log(
        action="sms_adb_failed",
        command_category="sms",
        result="failed",
        warning=f"ADB query failed: rc={adb_res.return_code}, timeout={adb_res.timed_out}",
    )

    if collector_folder:
        src = Path(collector_folder)
        src_file = src / "sms.jsonl"
        if src_file.exists():
            is_valid, line_count, err_msg = _validate_jsonl(src_file)
            if is_valid:
                # Copy to raw/collector/
                dest_raw = case_folder.raw_collector_dir / "sms.jsonl"
                shutil.copy2(src_file, dest_raw)
                manifest.add_file(
                    artifact_class="collector_sms",
                    source_type="collector_import",
                    source_command_or_path=str(src_file),
                    destination_path=dest_raw,
                    status=STATUS_ACQUIRED_FROM_COLLECTOR,
                    started_at=started_at,
                )

                # Copy to derived/sms_messages.jsonl
                derived_path = case_folder.derived_dir / "sms_messages.jsonl"
                shutil.copy2(src_file, derived_path)
                manifest.add_file(
                    artifact_class="sms",
                    source_type="collector_import",
                    source_command_or_path=str(src_file),
                    destination_path=derived_path,
                    status=STATUS_ACQUIRED_FROM_COLLECTOR,
                    started_at=started_at,
                )

                results["status"] = STATUS_ACQUIRED_FROM_COLLECTOR
                results["message_count"] = line_count
                results["source"] = "collector"
                audit.log(
                    action="sms_acquired_via_collector",
                    command_category="sms",
                    result=STATUS_ACQUIRED_FROM_COLLECTOR,
                    output_path=str(derived_path),
                )
                return results
            else:
                results["warnings"].append(
                    f"Collector sms.jsonl exists but has invalid format: {err_msg}"
                )
        else:
            results["warnings"].append("Collector sms.jsonl file not found in export folder.")
    else:
        results["warnings"].append(
            "No collector export folder provided. To acquire SMS on secure devices, "
            "run the collector app and provide the export folder via --collector-export-folder."
        )

    # ── Both failed ─────────────────────────────────────────────────────────
    manifest.add_status_record(
        artifact_class="sms",
        source_type="adb_command",
        source_command_or_path="adb shell content query --uri content://sms",
        status=STATUS_PERMISSION_DENIED,
        reason_code="security_blocked",
    )
    results["status"] = STATUS_PERMISSION_DENIED
    audit.log(
        action="sms_acquisition_failed",
        command_category="sms",
        result=STATUS_PERMISSION_DENIED,
        error="ADB query blocked and no collector export available",
    )
    return results
