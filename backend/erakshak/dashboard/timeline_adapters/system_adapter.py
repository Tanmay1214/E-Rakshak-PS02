"""System timeline adapter for E-RAKSHAK."""

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any
from erakshak.dashboard.timeline_models import TimelineEvent
from erakshak.dashboard.timeline_ids import make_event_id
from erakshak.dashboard.time_utils import parse_timestamp, to_epoch_ms, to_iso, bucket_time


def load_events(
    case_folder: Path,
    case_id: str,
    exhibit_id: str,
    timezone: str = "Asia/Kolkata"
) -> Tuple[List[TimelineEvent], List[str]]:
    """Load system level logs (logcat, usage stats, system events) into TimelineEvents."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    derived_dir = case_folder / "derived"

    system_sources = [
        ("logcat_events.jsonl", "logcat_event", "logcat", "medium", "Logcat Log Entry"),
        ("device_timeline_events.jsonl", "system_event", "dumpsys", "medium", "System Event"),
        ("app_usage_summary.jsonl", "app_usage_event", "dumpsys", "medium", "App Usage Log")
    ]

    for filename, event_type, source_type, base_confidence, base_title in system_sources:
        filepath = derived_dir / filename
        if not filepath.is_file():
            continue

        try:
            row_idx = 0
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in {filename}: {e}. Skipped.")
                        continue

                    # Extract timestamp
                    raw_ts = record.get("timestamp") or record.get("last_time_used") or record.get("date")
                    if not raw_ts:
                        row_idx += 1
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    # Extract properties
                    app = record.get("package_name") or record.get("tag") or "Android"
                    message = record.get("message") or record.get("event") or ""
                    
                    if event_type == "app_usage_event":
                        duration = record.get("total_time_ms") or 0
                        message = f"App '{app}' used for {duration} ms."

                    summary = f"[{app}] {message}" if app else message

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(filepath.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type=event_type,
                        summary=summary
                    )

                    events.append(TimelineEvent(
                        id=evt_id,
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        timestamp=ts_iso,
                        timestamp_sort=ts_sort,
                        bucket_15m=bucket_time(dt, 15),
                        bucket_1h=bucket_time(dt, 60),
                        source_app=app or "Android",
                        source_type=source_type,
                        category="system",
                        event_type=event_type,
                        title=base_title,
                        summary=summary,
                        confidence=base_confidence,
                        source_file=str(filepath.relative_to(case_folder)),
                        parser="SystemParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing system logs file {filename}: {e}")

    # Check warnings
    for filename, _, _, _, _ in system_sources:
        if not (derived_dir / filename).is_file():
            warnings.append(f"derived/{filename} not found.")

    return events, warnings
