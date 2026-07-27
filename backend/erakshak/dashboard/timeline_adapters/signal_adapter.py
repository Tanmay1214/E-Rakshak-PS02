"""Signal timeline adapter for E-RAKSHAK."""

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
    """Load Signal message JSONL dumps into TimelineEvents."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    signal_dir = case_folder / "derived" / "apps" / "signal"
    # Find all *_messages.jsonl files
    message_files = list(signal_dir.glob("**/*_messages.jsonl"))

    if not message_files:
        warnings.append("Signal message JSONL files not found under derived/apps/signal/.")
        return events, warnings

    for msg_file in message_files:
        try:
            pkg_name = msg_file.parent.name
            row_idx = 0
            with open(msg_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in {msg_file.name}: {e}. Skipped.")
                        continue

                    raw_ts = msg.get("date") or msg.get("timestamp")
                    if not raw_ts:
                        row_idx += 1
                        warnings.append(f"Signal message in {msg_file.name} lacks timestamp. Skipped.")
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        warnings.append(f"Signal message in {msg_file.name} has unparseable timestamp: {raw_ts}. Skipped.")
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    body = msg.get("message") or msg.get("body") or ""
                    contact = msg.get("contact_name") or msg.get("phone") or "Unknown"
                    
                    received = msg.get("received")
                    sent = msg.get("sent")

                    if sent is True or sent == 1 or str(sent).lower() == "true":
                        direction = "outgoing"
                        sender = "Me"
                        receiver = contact
                    elif received is True or received == 1 or str(received).lower() == "true":
                        direction = "incoming"
                        sender = contact
                        receiver = "Me"
                    else:
                        direction = "incoming"  # default
                        sender = contact
                        receiver = "Me"

                    event_type = "signal_message"
                    title = f"Signal Message from {sender}" if direction == "incoming" else f"Signal Message to {receiver}"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(msg_file.relative_to(case_folder)),
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
                        source_app="Signal",
                        source_type="signal_parser",
                        category="messages",
                        event_type=event_type,
                        direction=direction,
                        title=title,
                        summary=body[:160] if body else None,
                        actor=sender if direction == "incoming" else receiver,
                        sender=sender,
                        receiver=receiver,
                        phone_number=msg.get("phone"),
                        confidence="high",
                        source_file=str(msg_file.relative_to(case_folder)),
                        parser="SignalParser",
                        raw_json=line
                    ))
                    row_idx += 1

        except Exception as e:
            warnings.append(f"Failed parsing Signal file {msg_file.name}: {e}")

    return events, warnings
