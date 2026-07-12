"""Acquire contacts from the Android device.

Attempts to query contacts directly via the Android content provider using ADB.
If blocked by Android's security model (SecurityException, permission denied,
etc.), it falls back to importing exported contacts from the companion
collector app's output.

Output artefacts
----------------
- ``raw/system/content_contacts.txt``     – verbatim content query output (if successful)
- ``raw/collector/contacts.jsonl``        – copied collector output (if fallback is used)
- ``derived/contacts.jsonl``              – normalised contacts records (from either source)
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


def acquire_contacts(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
    collector_folder: str | None = None,
) -> dict[str, Any]:
    """Acquire contacts.

    First tries querying content://com.android.contacts/contacts using ADB.
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
        "contact_count": 0,
        "warnings": [],
        "source": "none",
    }
    started_at = datetime.now(timezone.utc).isoformat()

    # ── Try ADB Content Query ───────────────────────────────────────────────
    query_cmd = ["content", "query", "--uri", "content://com.android.contacts/contacts"]
    adb_res = adb.shell(
        query_cmd,
        timeout=CONTENT_QUERY_TIMEOUT,
        audit_action="content_query_contacts",
    )

    is_adb_successful = False
    if adb_res.return_code == 0 and not adb_res.timed_out:
        stdout = adb_res.stdout
        # SecurityException/Permission denial is often printed to stdout or stderr
        if "SecurityException" not in stdout and "Permission Denial" not in stdout and "Error" not in stdout:
            is_adb_successful = True

    if is_adb_successful:
        # Write raw output
        raw_path = case_folder.raw_system_dir / "content_contacts.txt"
        raw_path.write_text(adb_res.stdout, encoding="utf-8")
        manifest.add_file(
            artifact_class="contacts_raw",
            source_type="adb_command",
            source_command_or_path="adb shell content query --uri content://com.android.contacts/contacts",
            destination_path=raw_path,
            status=STATUS_ACQUIRED,
            started_at=started_at,
        )

        # Parse contacts
        parsed_contacts = parse_content_query(adb_res.stdout)
        results["contact_count"] = len(parsed_contacts)

        # Write derived contacts.jsonl
        derived_path = case_folder.derived_dir / "contacts.jsonl"
        with open(derived_path, "w", encoding="utf-8") as fh:
            for contact in parsed_contacts:
                fh.write(json.dumps(contact, ensure_ascii=False) + "\n")

        manifest.add_file(
            artifact_class="contacts",
            source_type="adb_command",
            source_command_or_path="adb shell content query --uri content://com.android.contacts/contacts",
            destination_path=derived_path,
            status=STATUS_ACQUIRED,
            started_at=started_at,
        )

        results["status"] = STATUS_ACQUIRED
        results["source"] = "adb"
        audit.log(
            action="contacts_acquired_via_adb",
            command_category="contacts",
            result=STATUS_ACQUIRED,
            output_path=str(derived_path),
        )
        return results

    # ── Fallback to Collector Export ────────────────────────────────────────
    results["warnings"].append(
        "ADB contacts query blocked or failed. Attempting fallback to collector export."
    )
    audit.log(
        action="contacts_adb_failed",
        command_category="contacts",
        result="failed",
        warning=f"ADB query failed: rc={adb_res.return_code}, timeout={adb_res.timed_out}",
    )

    if collector_folder:
        src = Path(collector_folder)
        src_file = src / "contacts.jsonl"
        if src_file.exists():
            is_valid, line_count, err_msg = _validate_jsonl(src_file)
            if is_valid:
                # Copy to raw/collector/
                dest_raw = case_folder.raw_collector_dir / "contacts.jsonl"
                shutil.copy2(src_file, dest_raw)
                manifest.add_file(
                    artifact_class="collector_contacts",
                    source_type="collector_import",
                    source_command_or_path=str(src_file),
                    destination_path=dest_raw,
                    status=STATUS_ACQUIRED_FROM_COLLECTOR,
                    started_at=started_at,
                )

                # Copy to derived/contacts.jsonl
                derived_path = case_folder.derived_dir / "contacts.jsonl"
                shutil.copy2(src_file, derived_path)
                manifest.add_file(
                    artifact_class="contacts",
                    source_type="collector_import",
                    source_command_or_path=str(src_file),
                    destination_path=derived_path,
                    status=STATUS_ACQUIRED_FROM_COLLECTOR,
                    started_at=started_at,
                )

                results["status"] = STATUS_ACQUIRED_FROM_COLLECTOR
                results["contact_count"] = line_count
                results["source"] = "collector"
                audit.log(
                    action="contacts_acquired_via_collector",
                    command_category="contacts",
                    result=STATUS_ACQUIRED_FROM_COLLECTOR,
                    output_path=str(derived_path),
                )
                return results
            else:
                results["warnings"].append(
                    f"Collector contacts.jsonl exists but has invalid format: {err_msg}"
                )
        else:
            results["warnings"].append("Collector contacts.jsonl file not found in export folder.")
    else:
        results["warnings"].append(
            "No collector export folder provided. To acquire contacts on secure devices, "
            "run the collector app and provide the export folder via --collector-export-folder."
        )

    # ── Both failed ─────────────────────────────────────────────────────────
    manifest.add_status_record(
        artifact_class="contacts",
        source_type="adb_command",
        source_command_or_path="adb shell content query --uri content://com.android.contacts/contacts",
        status=STATUS_PERMISSION_DENIED,
        reason_code="security_blocked",
    )
    results["status"] = STATUS_PERMISSION_DENIED
    audit.log(
        action="contacts_acquisition_failed",
        command_category="contacts",
        result=STATUS_PERMISSION_DENIED,
        error="ADB query blocked and no collector export available",
    )
    return results
