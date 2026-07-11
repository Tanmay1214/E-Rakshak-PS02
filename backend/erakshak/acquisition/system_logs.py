"""Acquire system logs from the Android device.

Runs ``adb shell logcat -d`` (dump current ring-buffer, **never** clear)
and parses the output for forensically interesting events.

Forensic lead categories
------------------------
- **crashes** – FATAL, AndroidRuntime exceptions
- **app_launch** – ActivityManager START / displayed
- **security** – SELinux denials, KeyStore, auth events
- **usb** – USB plug / unplug / MTP
- **network** – connectivity changes, Wi-Fi, tethering
- **boot** – boot_completed, zygote, SystemServer
- **errors** – general logcat E-level entries

Output artefacts
----------------
- ``raw/system/logcat.txt``         – verbatim logcat dump
- ``derived/logcat_events.jsonl``   – one JSON object per forensic event
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


def acquire_system_logs(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Collect system logs.

    Runs ``adb shell logcat -d`` to dump the current log ring-buffer.
    The ``-c`` (clear) flag is **never** used — forensic data must not
    be destroyed.

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
        Summary with ``status``, ``event_count``, ``warnings``.
    """
    from erakshak.adb.parsers import parse_logcat
    from erakshak.config.defaults import (
        LOGCAT_TIMEOUT,
        STATUS_ACQUIRED,
        STATUS_FAILED,
    )

    results: dict = {
        "status": STATUS_ACQUIRED,
        "event_count": 0,
        "warnings": [],
    }
    started_at: str = datetime.now(timezone.utc).isoformat()

    # ---- 1. Run logcat -d ---------------------------------------------------
    logcat_result = adb.shell(
        ["logcat", "-d"],
        timeout=LOGCAT_TIMEOUT,
        audit_action="logcat_dump",
    )

    raw_path: Path = case_folder.raw_system_dir / "logcat.txt"

    # A non-zero return code (without timeout) means logcat itself failed.
    if logcat_result.return_code != 0 and not logcat_result.timed_out:
        manifest.add_status_record(
            "system_logs", "adb_command", "logcat -d",
            STATUS_FAILED, f"rc={logcat_result.return_code}",
        )
        results["status"] = STATUS_FAILED
        results["warnings"].append("logcat dump failed")
        audit.log(
            action="logcat_failed",
            command_category="logs",
            result="failed",
        )
        return results

    # ---- 2. Persist raw output ----------------------------------------------
    raw_path.write_text(logcat_result.stdout, encoding="utf-8")
    manifest.add_file(
        "logcat_raw", "adb_command", "logcat -d",
        raw_path, started_at=started_at,
    )

    # If logcat timed out but still produced partial output, we still save
    # what we have and mark a warning rather than failing outright.
    if logcat_result.timed_out:
        results["warnings"].append(
            "logcat timed out; partial output was saved"
        )

    # ---- 3. Parse forensic events -------------------------------------------
    events: list[dict] = parse_logcat(logcat_result.stdout)

    events_path: Path = case_folder.derived_dir / "logcat_events.jsonl"
    with open(events_path, "w", encoding="utf-8") as fh:
        for evt in events:
            fh.write(json.dumps(evt, ensure_ascii=False, default=str) + "\n")
    manifest.add_file("logcat_events", "parsed", "logcat -d", events_path)

    # ---- 4. Finalise --------------------------------------------------------
    results["event_count"] = len(events)

    if logcat_result.timed_out and events:
        results["status"] = "partial"
    elif logcat_result.timed_out and not events:
        results["status"] = STATUS_FAILED

    audit.log(
        action="logcat_acquired",
        command_category="logs",
        result=results["status"],
        output_path=str(events_path),
    )

    return results
