"""WhatsApp timeline adapter for E-RAKSHAK."""

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
    """Load WhatsApp chats, messages and summary metadata into TimelineEvents."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    # 1. Look for all result.json files recursively
    whatsapp_dir = case_folder / "derived" / "whatsapp_exporter"
    result_files = list(whatsapp_dir.glob("**/result.json"))

    parsed_any = False

    for result_file in result_files:
        try:
            # Determine profile and package from path structure
            rel_parts = result_file.relative_to(whatsapp_dir).parts
            if len(rel_parts) >= 3 and rel_parts[0] == "rooted":
                pkg_name = rel_parts[1]
                profile = rel_parts[2] if len(rel_parts) > 3 else "Default"
                source_type = "whatsapp_rooted"
            else:
                pkg_name = "com.whatsapp"
                profile = "Default"
                source_type = "whatsapp_exporter"

            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                warnings.append(f"WhatsApp file {result_file.name} is not a valid JSON object.")
                continue

            parsed_any = True
            row_idx = 0
            for chat_id, chat_val in data.items():
                messages = []
                if isinstance(chat_val, dict) and "messages" in chat_val:
                    messages = chat_val["messages"]
                elif isinstance(chat_val, list):
                    messages = chat_val

                if isinstance(messages, dict):
                    messages = list(messages.values())

                for msg in messages:
                    if not isinstance(msg, dict):
                        continue


                    # Extract timestamp
                    raw_ts = msg.get("timestamp") or msg.get("date")
                    if not raw_ts:
                        row_idx += 1
                        warnings.append(f"WhatsApp message in {result_file.name} lacks timestamp. Skipped.")
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        warnings.append(f"WhatsApp message in {result_file.name} has unparseable timestamp: {raw_ts}. Skipped.")
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    body = msg.get("message") or msg.get("body") or msg.get("text") or msg.get("data") or ""
                    
                    # Ensure no raw WhatsApp encryption keys appear anywhere in the event
                    # Clean/remove key details from message fields
                    if "key" in body.lower() and len(body) > 60:
                        # Redact potential keys
                        body = "[REDACTED KEY DATA]"
                        # Update raw msg values to prevent leaks into raw_json serialization
                        for k in list(msg.keys()):
                            if k in ("message", "body", "text", "data"):
                                msg[k] = "[REDACTED KEY DATA]"
                            elif "key" in k.lower():
                                # remove other keys
                                msg.pop(k, None)



                    from_me = msg.get("from_me")
                    if from_me is True or from_me == 1 or str(from_me).lower() == "true":
                        direction = "outgoing"
                        sender = "Me"
                        receiver = chat_id
                    else:
                        direction = "incoming"
                        sender = msg.get("sender") or chat_id
                        receiver = "Me"

                    # Check for call events vs chat messages
                    msg_type = str(msg.get("type", "message")).lower()
                    if "call" in msg_type or "call" in body.lower():
                        event_type = "whatsapp_call"
                        category = "calls"
                        title = f"WhatsApp Call ({direction.capitalize()})"
                    else:
                        event_type = "whatsapp_message"
                        category = "messages"
                        title = f"WhatsApp Message from {sender}" if direction == "incoming" else f"WhatsApp Message to {receiver}"

                    # Clean raw message dict for raw_json to ensure no encryption key leaks
                    clean_msg = {k: v for k, v in msg.items() if "key" not in k.lower()}
                    raw_json_str = json.dumps(clean_msg, ensure_ascii=False)

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(result_file.relative_to(case_folder)),
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
                        source_app="WhatsApp",
                        source_type=source_type,
                        category=category,
                        event_type=event_type,
                        direction=direction,
                        title=title,
                        summary=body[:160] if body else None,
                        actor=sender if direction == "incoming" else receiver,
                        sender=sender,
                        receiver=receiver,
                        phone_number=chat_id if "@" not in chat_id else chat_id.split("@")[0],
                        confidence="high",
                        source_file=str(result_file.relative_to(case_folder)),
                        parser="Whatsapp-Chat-Exporter",
                        raw_json=raw_json_str
                    ))
                    row_idx += 1

        except Exception as e:
            warnings.append(f"Failed parsing WhatsApp file {result_file.name}: {e}")

    # 2. If no result.json files parsed, look for whatsapp_preview_summary.json to generate a summary event
    if not parsed_any:
        summary_path = case_folder / "derived" / "whatsapp_preview_summary.json"
        if summary_path.is_file():
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_data = json.load(f)
                
                # Try to use current host timestamp or execution timestamp if present
                raw_ts = summary_data.get("timestamp") or summary_data.get("started_at")
                if raw_ts:
                    dt = parse_timestamp(raw_ts, timezone)
                    if dt:
                        ts_iso = to_iso(dt)
                        ts_sort = to_epoch_ms(dt)
                        evt_id = make_event_id(
                            case_id=case_id,
                            exhibit_id=exhibit_id,
                            source_file=str(summary_path.relative_to(case_folder)),
                            row_index=0,
                            timestamp=ts_iso,
                            event_type="parser_summary",
                            summary="WhatsApp acquisition summary"
                        )
                        events.append(TimelineEvent(
                            id=evt_id,
                            case_id=case_id,
                            exhibit_id=exhibit_id,
                            timestamp=ts_iso,
                            timestamp_sort=ts_sort,
                            bucket_15m=bucket_time(dt, 15),
                            bucket_1h=bucket_time(dt, 60),
                            source_app="WhatsApp",
                            source_type="whatsapp_exporter",
                            category="integrity",
                            event_type="parser_summary",
                            title="WhatsApp Parser Execution Summary",
                            summary=f"Parsed {summary_data.get('message_count', 0)} messages.",
                            confidence="medium",
                            source_file=str(summary_path.relative_to(case_folder)),
                            parser="Whatsapp-Chat-Exporter",
                            raw_json=json.dumps(summary_data, ensure_ascii=False)
                        ))
            except Exception as e:
                warnings.append(f"Failed parsing WhatsApp summary file {summary_path.name}: {e}")
        else:
            warnings.append("WhatsApp results file result.json not found under derived/whatsapp_exporter/.")

    return events, warnings
