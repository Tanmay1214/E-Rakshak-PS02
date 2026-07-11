"""Acquire device timeline and user-activity data.

Runs a battery of ``dumpsys`` commands, persists every raw output to
``raw/system/``, then parses the outputs into a unified set of timeline
events and an app-usage summary.

Output artefacts
----------------
- ``raw/system/dumpsys_activity.txt``
- ``raw/system/dumpsys_activity_recents.txt``
- ``raw/system/dumpsys_usagestats.txt``
- ``raw/system/dumpsys_batterystats.txt``
- ``raw/system/dumpsys_notification.txt``
- ``raw/system/dumpsys_jobscheduler.txt``
- ``raw/system/dumpsys_alarm.txt``
- ``raw/system/dumpsys_activity_processes.txt``
- ``derived/device_timeline_events.jsonl``
- ``derived/app_usage_summary.jsonl``
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

# Regex to pull running-process entries from dumpsys activity processes.
_PROC_RE = re.compile(r"ProcessRecord\{[^}]*\s+(\S+)/([\d]+)")


def _extract_running_processes(text: str) -> list[dict]:
    """Return a list of ``{process_name, pid}`` dicts."""
    results: list[dict] = []
    for match in _PROC_RE.finditer(text):
        results.append({
            "event_type": "running_process",
            "source": "dumpsys_activity_processes",
            "process_name": match.group(1),
            "pid": match.group(2),
        })
    return results


# ---------------------------------------------------------------------------
# Command table
# ---------------------------------------------------------------------------

def _build_command_table(dumpsys_timeout: int, long_timeout: int) -> list[dict]:
    """Return the list of shell commands to execute."""
    return [
        {
            "args": ["dumpsys", "activity"],
            "filename": "dumpsys_activity.txt",
            "action": "dumpsys_activity",
            "timeout": long_timeout,
        },
        {
            "args": ["dumpsys", "activity", "recents"],
            "filename": "dumpsys_activity_recents.txt",
            "action": "dumpsys_recents",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "usagestats"],
            "filename": "dumpsys_usagestats.txt",
            "action": "dumpsys_usagestats",
            "timeout": long_timeout,
        },
        {
            "args": ["dumpsys", "batterystats"],
            "filename": "dumpsys_batterystats.txt",
            "action": "dumpsys_batterystats",
            "timeout": long_timeout,
        },
        {
            "args": ["dumpsys", "notification"],
            "filename": "dumpsys_notification.txt",
            "action": "dumpsys_notification",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "jobscheduler"],
            "filename": "dumpsys_jobscheduler.txt",
            "action": "dumpsys_jobscheduler",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "alarm"],
            "filename": "dumpsys_alarm.txt",
            "action": "dumpsys_alarm",
            "timeout": dumpsys_timeout,
        },
        {
            "args": ["dumpsys", "activity", "processes"],
            "filename": "dumpsys_activity_processes.txt",
            "action": "dumpsys_processes",
            "timeout": dumpsys_timeout,
        },
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def acquire_timeline(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Collect device timeline and user-activity data.

    Runs multiple ``dumpsys`` commands, saves each raw output, then
    parses recent-app tasks, usage-stats entries, battery events, and
    running processes into a unified timeline.

    Parameters
    ----------
    adb : ADBClient
        Connected ADB wrapper.
    case_folder : CaseFolder
        Open case folder.
    manifest : ManifestWriter
        Manifest writer for chain-of-custody records.
    audit : AuditLogger
        Audit trail logger.

    Returns
    -------
    dict
        Summary with ``status``, ``timeline_event_count``,
        ``usage_count``, ``warnings``.
    """
    from erakshak.adb.parsers import (
        parse_dumpsys_activity_recents,
        parse_dumpsys_usagestats,
        parse_dumpsys_battery_stats,
    )
    from erakshak.config.defaults import (
        DUMPSYS_TIMEOUT,
        LONG_ADB_TIMEOUT,
        STATUS_ACQUIRED,
        STATUS_FAILED,
    )

    results: dict = {
        "status": STATUS_ACQUIRED,
        "timeline_event_count": 0,
        "usage_count": 0,
        "warnings": [],
    }

    commands = _build_command_table(DUMPSYS_TIMEOUT, LONG_ADB_TIMEOUT)
    raw_outputs: dict[str, str] = {}  # filename -> stdout

    # ---- 1. Execute every command and persist raw output --------------------
    for cmd in commands:
        cmd_str = f"adb shell {' '.join(cmd['args'])}"
        try:
            r = adb.shell(
                cmd["args"],
                timeout=cmd["timeout"],
                audit_action=cmd["action"],
            )
            raw_path: Path = case_folder.raw_system_dir / cmd["filename"]

            if r.return_code == 0 and not r.timed_out:
                raw_path.write_text(r.stdout, encoding="utf-8")
                manifest.add_file(
                    f"timeline_{cmd['action']}", "adb_command",
                    cmd_str, raw_path,
                )
                raw_outputs[cmd["filename"]] = r.stdout
            else:
                reason = "timed_out" if r.timed_out else f"rc={r.return_code}"
                manifest.add_status_record(
                    f"timeline_{cmd['action']}", "adb_command",
                    cmd_str, STATUS_FAILED, reason,
                )
                results["warnings"].append(f"{cmd['action']} failed: {reason}")
        except Exception as exc:  # noqa: BLE001
            results["warnings"].append(
                f"{cmd['action']} exception: {exc!s}"
            )

    # ---- 2. Parse structured events ----------------------------------------
    timeline_events: list[dict] = []

    # 2a. Recent apps
    if "dumpsys_activity_recents.txt" in raw_outputs:
        for item in parse_dumpsys_activity_recents(
            raw_outputs["dumpsys_activity_recents.txt"]
        ):
            timeline_events.append({
                "event_type": "recent_app",
                "source": "dumpsys_activity_recents",
                **item,
            })

    # 2b. Usage stats
    usage_summary: list[dict] = []
    if "dumpsys_usagestats.txt" in raw_outputs:
        for item in parse_dumpsys_usagestats(
            raw_outputs["dumpsys_usagestats.txt"]
        ):
            usage_summary.append(item)
            timeline_events.append({
                "event_type": "app_usage",
                "source": "dumpsys_usagestats",
                **item,
            })

    # 2c. Battery stats (screen on/off, boot, charge events)
    if "dumpsys_batterystats.txt" in raw_outputs:
        for item in parse_dumpsys_battery_stats(
            raw_outputs["dumpsys_batterystats.txt"]
        ):
            timeline_events.append({
                "event_type": item.get("type", "battery_event"),
                "source": "dumpsys_batterystats",
                **item,
            })

    # 2d. Running processes
    if "dumpsys_activity_processes.txt" in raw_outputs:
        timeline_events.extend(
            _extract_running_processes(
                raw_outputs["dumpsys_activity_processes.txt"]
            )
        )

    # ---- 3. Write derived artefacts ----------------------------------------

    # device_timeline_events.jsonl
    timeline_path: Path = case_folder.derived_dir / "device_timeline_events.jsonl"
    with open(timeline_path, "w", encoding="utf-8") as fh:
        for evt in timeline_events:
            fh.write(json.dumps(evt, ensure_ascii=False, default=str) + "\n")
    manifest.add_file(
        "device_timeline", "parsed", "dumpsys multiple", timeline_path,
    )

    # app_usage_summary.jsonl
    usage_path: Path = case_folder.derived_dir / "app_usage_summary.jsonl"
    with open(usage_path, "w", encoding="utf-8") as fh:
        for item in usage_summary:
            fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    manifest.add_file(
        "app_usage_summary", "parsed", "dumpsys usagestats", usage_path,
    )

    # ---- 4. Finalise results ------------------------------------------------
    results["timeline_event_count"] = len(timeline_events)
    results["usage_count"] = len(usage_summary)

    if results["warnings"] and not timeline_events:
        results["status"] = "partial"

    audit.log(
        action="timeline_acquired",
        command_category="timeline",
        result=results["status"],
        output_path=str(timeline_path),
    )

    return results
