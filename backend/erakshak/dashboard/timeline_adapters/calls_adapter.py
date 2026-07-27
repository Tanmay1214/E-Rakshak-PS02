"""Calls timeline adapter for E-RAKSHAK."""

import json
import re
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
    """Load call logs from derived, raw, and collector files."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    # Helper for title/direction mappings
    def get_call_info(type_val: str) -> Tuple[str, str]:
        t = str(type_val)
        if t == "1":
            return "incoming", "Incoming Call"
        elif t == "2":
            return "outgoing", "Outgoing Call"
        elif t == "3":
            return "missed", "Missed Call"
        else:
            return "unknown", "Phone Call"

    # 1. Preferred normalized: derived/call_logs.jsonl
    derived_calls = case_folder / "derived" / "call_logs.jsonl"
    if derived_calls.is_file():
        try:
            row_idx = 0
            with open(derived_calls, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        call = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in derived/call_logs.jsonl: {e}. Skipped.")
                        continue

                    raw_ts = call.get("timestamp") or call.get("date")
                    if not raw_ts:
                        row_idx += 1
                        warnings.append("Call log in derived/call_logs.jsonl lacks timestamp. Skipped.")
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        warnings.append(f"Call log in derived/call_logs.jsonl has unparseable timestamp: {raw_ts}. Skipped.")
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    number = call.get("number") or call.get("phone_number") or "Unknown"
                    duration = call.get("duration") or call.get("duration_seconds", 0)
                    type_val = call.get("type", "1")
                    direction, title = get_call_info(type_val)

                    summary = f"Call with {number}. Duration: {duration}s"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(derived_calls.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="phone_call",
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
                        source_app="Phone",
                        source_type="normalized_derived",
                        category="calls",
                        event_type="phone_call",
                        direction=direction,
                        title=title,
                        summary=summary,
                        actor=number,
                        sender="Me" if direction == "outgoing" else number,
                        receiver=number if direction == "outgoing" else "Me",
                        phone_number=number,
                        confidence="high",
                        source_file=str(derived_calls.relative_to(case_folder)),
                        parser="CallLogParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing derived/call_logs.jsonl: {e}")
    else:
        warnings.append("derived/call_logs.jsonl not found.")

    # 2. Raw content provider: raw/system/content_call_log.txt
    raw_calls = case_folder / "raw" / "system" / "content_call_log.txt"
    if raw_calls.is_file():
        try:
            row_idx = 0
            with open(raw_calls, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith("Row:"):
                        continue
                    
                    parsed_fields = {}
                    for field in ("_id", "number", "date", "duration", "type"):
                        pattern = rf"\b{field}=([^,\s]+)"
                        m = re.search(pattern, line)
                        if m:
                            parsed_fields[field] = m.group(1).strip()

                    raw_ts = parsed_fields.get("date")
                    if not raw_ts:
                        row_idx += 1
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    number = parsed_fields.get("number", "Unknown")
                    duration = parsed_fields.get("duration", "0")
                    type_val = parsed_fields.get("type", "1")
                    direction, title = get_call_info(type_val)

                    summary = f"Call with {number}. Duration: {duration}s"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(raw_calls.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="phone_call",
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
                        source_app="Phone",
                        source_type="adb_content_provider",
                        category="calls",
                        event_type="phone_call",
                        direction=direction,
                        title=title,
                        summary=summary,
                        actor=number,
                        sender="Me" if direction == "outgoing" else number,
                        receiver=number if direction == "outgoing" else "Me",
                        phone_number=number,
                        confidence="medium",
                        source_file=str(raw_calls.relative_to(case_folder)),
                        parser="CallLogParser",
                        raw_json=json.dumps(parsed_fields, ensure_ascii=False)
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing raw/system/content_call_log.txt: {e}")

    # 3. Collector call log: raw/collector/calls.jsonl
    coll_calls = case_folder / "raw" / "collector" / "calls.jsonl"
    if coll_calls.is_file():
        try:
            row_idx = 0
            with open(coll_calls, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        call = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in raw/collector/calls.jsonl: {e}. Skipped.")
                        continue

                    raw_ts = call.get("timestamp") or call.get("date")
                    if not raw_ts:
                        row_idx += 1
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    number = call.get("number") or call.get("phone_number") or "Unknown"
                    duration = call.get("duration") or call.get("duration_seconds", 0)
                    type_val = call.get("type", "1")
                    direction, title = get_call_info(type_val)

                    summary = f"Call with {number}. Duration: {duration}s"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(coll_calls.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="phone_call",
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
                        source_app="Phone",
                        source_type="collector_app_import",
                        category="calls",
                        event_type="phone_call",
                        direction=direction,
                        title=title,
                        summary=summary,
                        actor=number,
                        sender="Me" if direction == "outgoing" else number,
                        receiver=number if direction == "outgoing" else "Me",
                        phone_number=number,
                        confidence="high",
                        source_file=str(coll_calls.relative_to(case_folder)),
                        parser="CallLogParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing raw/collector/calls.jsonl: {e}")


    return events, warnings
