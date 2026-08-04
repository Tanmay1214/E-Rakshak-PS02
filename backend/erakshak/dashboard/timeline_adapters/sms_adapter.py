"""SMS timeline adapter for E-RAKSHAK."""

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
    """Load SMS and MMS logs from derived, raw, and collector files."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    # 1. Preferred normalized: derived/sms_messages.jsonl
    derived_sms = case_folder / "derived" / "sms_messages.jsonl"
    if derived_sms.is_file():
        try:
            row_idx = 0
            with open(derived_sms, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in derived/sms_messages.jsonl: {e}. Skipped.")
                        continue

                    # derived messages usually have 'timestamp' or 'date'
                    raw_ts = msg.get("timestamp") or msg.get("date") or msg.get("date_sent")
                    if not raw_ts:
                        row_idx += 1
                        warnings.append("SMS message in derived/sms_messages.jsonl lacks timestamp. Skipped.")
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        warnings.append(f"SMS message in derived/sms_messages.jsonl has unparseable timestamp: {raw_ts}. Skipped.")
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    body = msg.get("body") or msg.get("message") or ""
                    address = msg.get("address") or msg.get("sender") or msg.get("receiver") or "Unknown"
                    direction_val = str(msg.get("type", "1"))
                    direction = "incoming" if direction_val == "1" else ("outgoing" if direction_val == "2" else "unknown")

                    event_type = "sms_message"
                    title = f"SMS Message ({direction.capitalize()})"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(derived_sms.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type=event_type,
                        summary=body[:160]
                    )

                    events.append(TimelineEvent(
                        id=evt_id,
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        timestamp=ts_iso,
                        timestamp_sort=ts_sort,
                        bucket_15m=bucket_time(dt, 15),
                        bucket_1h=bucket_time(dt, 60),
                        source_app="SMS",
                        source_type="normalized_derived",
                        category="messages",
                        event_type=event_type,
                        direction=direction,
                        title=title,
                        summary=body[:160] if body else None,
                        actor=address,
                        sender="Me" if direction == "outgoing" else address,
                        receiver=address if direction == "outgoing" else "Me",
                        phone_number=address,
                        deleted_status=msg.get("deleted_status") or ("deleted_marker" if "This message was deleted" in body else None),
                        recovered_status=msg.get("recovered_status") or ("recovered" if msg.get("recovered") else None),
                        confidence="high",
                        source_file=str(derived_sms.relative_to(case_folder)),
                        parser="SMSParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing derived/sms_messages.jsonl: {e}")
    else:
        warnings.append("derived/sms_messages.jsonl not found.")

    # 2. Raw content provider: raw/system/content_sms.txt
    raw_sms = case_folder / "raw" / "system" / "content_sms.txt"
    if raw_sms.is_file():
        try:
            row_idx = 0
            with open(raw_sms, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith("Row:"):
                        continue
                    
                    # Parse Row line
                    parsed_fields = {}
                    for field in ("_id", "address", "date", "type", "body"):
                        pattern = rf"\b{field}=([^,\s]+)"
                        if field == "body":
                            pattern = r"\bbody=(.*)$"
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

                    body = parsed_fields.get("body", "")
                    address = parsed_fields.get("address", "Unknown")
                    direction_val = parsed_fields.get("type", "1")
                    direction = "incoming" if direction_val == "1" else ("outgoing" if direction_val == "2" else "unknown")

                    event_type = "sms_message"
                    title = f"SMS Message ({direction.capitalize()})"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(raw_sms.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type=event_type,
                        summary=body[:160]
                    )

                    events.append(TimelineEvent(
                        id=evt_id,
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        timestamp=ts_iso,
                        timestamp_sort=ts_sort,
                        bucket_15m=bucket_time(dt, 15),
                        bucket_1h=bucket_time(dt, 60),
                        source_app="SMS",
                        source_type="adb_content_provider",
                        category="messages",
                        event_type=event_type,
                        direction=direction,
                        title=title,
                        summary=body[:160] if body else None,
                        actor=address,
                        sender="Me" if direction == "outgoing" else address,
                        receiver=address if direction == "outgoing" else "Me",
                        phone_number=address,
                        deleted_status=parsed_fields.get("deleted_status") or ("deleted_marker" if "This message was deleted" in body else None),
                        recovered_status=parsed_fields.get("recovered_status") or ("recovered" if parsed_fields.get("recovered") else None),
                        confidence="medium",
                        source_file=str(raw_sms.relative_to(case_folder)),
                        parser="SMSParser",
                        raw_json=json.dumps(parsed_fields, ensure_ascii=False)
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing raw/system/content_sms.txt: {e}")

    # 3. Collector SMS/MMS: raw/collector/sms.jsonl & mms.jsonl
    for coll_file, is_mms in [("sms.jsonl", False), ("mms.jsonl", True)]:
        coll_path = case_folder / "raw" / "collector" / coll_file
        if coll_path.is_file():
            try:
                row_idx = 0
                with open(coll_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except Exception as e:
                            warnings.append(f"Malformed JSON line in raw/collector/{coll_file}: {e}. Skipped.")
                            continue

                        raw_ts = msg.get("timestamp") or msg.get("date")
                        if not raw_ts:
                            row_idx += 1
                            continue

                        dt = parse_timestamp(raw_ts, timezone)
                        if not dt:
                            row_idx += 1
                            continue

                        ts_iso = to_iso(dt)
                        ts_sort = to_epoch_ms(dt)

                        body = msg.get("body") or msg.get("message") or ""
                        address = msg.get("address") or msg.get("sender") or msg.get("receiver") or "Unknown"
                        direction_val = str(msg.get("type", "1"))
                        direction = "incoming" if direction_val == "1" else ("outgoing" if direction_val == "2" else "unknown")

                        event_type = "mms_message" if is_mms else "sms_message"
                        title = f"MMS Message ({direction.capitalize()})" if is_mms else f"SMS Message ({direction.capitalize()})"

                        evt_id = make_event_id(
                            case_id=case_id,
                            exhibit_id=exhibit_id,
                            source_file=str(coll_path.relative_to(case_folder)),
                            row_index=row_idx,
                            timestamp=ts_iso,
                            event_type=event_type,
                            summary=body[:160]
                        )

                        events.append(TimelineEvent(
                            id=evt_id,
                            case_id=case_id,
                            exhibit_id=exhibit_id,
                            timestamp=ts_iso,
                            timestamp_sort=ts_sort,
                            bucket_15m=bucket_time(dt, 15),
                            bucket_1h=bucket_time(dt, 60),
                            source_app="SMS",
                            source_type="collector_app_import",
                            category="messages",
                            event_type=event_type,
                            direction=direction,
                            title=title,
                            summary=body[:160] if body else None,
                            actor=address,
                            sender="Me" if direction == "outgoing" else address,
                            receiver=address if direction == "outgoing" else "Me",
                            phone_number=address,
                            deleted_status=msg.get("deleted_status") or ("deleted_marker" if "This message was deleted" in body else None),
                            recovered_status=msg.get("recovered_status") or ("recovered" if msg.get("recovered") else None),
                            confidence="high",
                            source_file=str(coll_path.relative_to(case_folder)),
                            parser="SMSParser",
                            raw_json=line
                        ))
                        row_idx += 1
            except Exception as e:
                warnings.append(f"Failed parsing raw/collector/{coll_file}: {e}")



    return events, warnings
