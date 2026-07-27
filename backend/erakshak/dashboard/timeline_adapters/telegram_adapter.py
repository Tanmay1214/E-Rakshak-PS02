"""Telegram timeline adapter for E-RAKSHAK."""

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
    """Load Telegram message JSONL dumps into TimelineEvents."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    telegram_dir = case_folder / "derived" / "apps" / "telegram"
    # Find all *_messages.jsonl files
    message_files = list(telegram_dir.glob("**/*_messages.jsonl"))

    if not message_files:
        warnings.append("Telegram message JSONL files not found under derived/apps/telegram/.")
        return events, warnings

    for msg_file in message_files:
        try:
            pkg_name = msg_file.parent.name
            
            # Look for a corresponding *_users.jsonl file to map UIDs to names
            users_map: Dict[int, str] = {}
            users_file = msg_file.parent / msg_file.name.replace("_messages.jsonl", "_users.jsonl")
            if users_file.is_file():
                with open(users_file, "r", encoding="utf-8") as uf:
                    for line in uf:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            user_data = json.loads(line)
                            uid = user_data.get("uid")
                            name = user_data.get("name") or ""
                            if uid is not None:
                                users_map[int(uid)] = name
                        except Exception:
                            pass

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

                    raw_ts = msg.get("date")
                    if not raw_ts:
                        row_idx += 1
                        warnings.append(f"Telegram message in {msg_file.name} lacks timestamp. Skipped.")
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        warnings.append(f"Telegram message in {msg_file.name} has unparseable timestamp: {raw_ts}. Skipped.")
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    body = msg.get("text") or msg.get("message") or ""
                    uid = msg.get("uid")
                    sender_name = users_map.get(int(uid)) if uid is not None else None
                    if not sender_name:
                        sender_name = f"User_{uid}" if uid is not None else "Unknown"

                    out = msg.get("out")
                    if out is True or out == 1 or str(out).lower() == "true":
                        direction = "outgoing"
                        sender = "Me"
                        receiver = sender_name
                    else:
                        direction = "incoming"
                        sender = sender_name
                        receiver = "Me"

                    event_type = "telegram_message"
                    title = f"Telegram Message from {sender}" if direction == "incoming" else f"Telegram Message to {receiver}"

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
                        source_app="Telegram",
                        source_type="telegram_parser",
                        category="messages",
                        event_type=event_type,
                        direction=direction,
                        title=title,
                        summary=body[:160] if body else None,
                        actor=sender if direction == "incoming" else receiver,
                        sender=sender,
                        receiver=receiver,
                        phone_number=None,
                        confidence="high",
                        source_file=str(msg_file.relative_to(case_folder)),
                        parser="TelegramParser",
                        raw_json=line
                    ))
                    row_idx += 1

        except Exception as e:
            warnings.append(f"Failed parsing Telegram file {msg_file.name}: {e}")

    return events, warnings
