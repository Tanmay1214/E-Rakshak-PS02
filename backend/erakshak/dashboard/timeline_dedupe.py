"""Deduplication logic for E-RAKSHAK timeline."""

import hashlib
import re
from typing import Tuple, List, Dict, Any
from erakshak.dashboard.timeline_models import TimelineEvent
from erakshak.dashboard.time_utils import parse_timestamp


def dedupe_events(events: List[TimelineEvent]) -> Tuple[List[TimelineEvent], Dict[str, Any]]:
    """Deduplicate timeline events, especially SMS and Calls from multiple acquisition lanes.
    
    Priority order for duplicates:
      1. normalized_derived
      2. collector_app_import
      3. adb_content_provider
    """
    deduped_events: List[TimelineEvent] = []
    seen_ids = set()

    sms_stats = {"normalized_derived": 0, "adb_content_provider": 0, "collector_app_import": 0, "deduplicated": 0}
    call_stats = {"normalized_derived": 0, "adb_content_provider": 0, "collector_app_import": 0, "deduplicated": 0}

    # Group communication events (SMS/Calls) for deduplication
    # Key format: (category, event_type, rounded_timestamp_sec, normalized_phone, direction, optional_body_hash_or_duration)
    comm_groups: Dict[Tuple[Any, ...], List[TimelineEvent]] = {}
    other_events: List[TimelineEvent] = []

    priority_map = {
        "normalized_derived": 1,
        "collector_app_import": 2,
        "adb_content_provider": 3
    }

    for e in events:
        # 1. Deduplicate by exact ID first
        if e.id in seen_ids:
            if e.category == "messages" and e.event_type in ("sms_message", "mms_message"):
                sms_stats["deduplicated"] += 1
            elif e.category == "calls" and e.event_type == "phone_call":
                call_stats["deduplicated"] += 1
            continue

        # Ingest counts by source_type before communication-based deduping
        if e.category == "messages" and e.event_type in ("sms_message", "mms_message"):
            if e.source_type == "normalized_derived":
                sms_stats["normalized_derived"] += 1
            elif e.source_type == "adb_content_provider":
                sms_stats["adb_content_provider"] += 1
            elif e.source_type == "collector_app_import":
                sms_stats["collector_app_import"] += 1
        elif e.category == "calls" and e.event_type == "phone_call":
            if e.source_type == "normalized_derived":
                call_stats["normalized_derived"] += 1
            elif e.source_type == "adb_content_provider":
                call_stats["adb_content_provider"] += 1
            elif e.source_type == "collector_app_import":
                call_stats["collector_app_import"] += 1

        is_comm = False
        if e.category in ("messages", "calls") and e.event_type in ("sms_message", "mms_message", "phone_call"):
            dt = parse_timestamp(e.timestamp)
            ts_sec = int(dt.timestamp()) if dt else 0

            # Normalize phone number to keep last 10 digits
            phone_raw = e.phone_number or e.sender or e.receiver or ""
            phone_clean = "".join(c for c in phone_raw if c.isdigit())
            phone_match = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

            direction = (e.direction or "").lower()

            if e.category == "messages":
                # Deduplicate SMS/MMS by body hash or first 30 characters
                body = (e.summary or "").strip().lower()
                body_sig = hashlib.md5(body.encode("utf-8")).hexdigest()
                comm_key = (e.category, e.event_type, ts_sec, phone_match, direction, body_sig)
            else:
                # Deduplicate phone calls by duration or location details if present
                # Use raw_json parser or direct summary duration extraction
                duration_sec = 0
                if e.summary and "duration" in e.summary.lower():
                    # Try to extract duration from summary string: "Duration: 45s"
                    m = re.search(r"duration:?\s*(\d+)", e.summary, re.IGNORECASE)
                    if m:
                        duration_sec = int(m.group(1))
                comm_key = (e.category, e.event_type, ts_sec, phone_match, direction, duration_sec)

            if comm_key not in comm_groups:
                comm_groups[comm_key] = []
            comm_groups[comm_key].append(e)
            is_comm = True
        else:
            other_events.append(e)
            seen_ids.add(e.id)

    # Process communication groups and resolve priority lanes
    for comm_key, group in comm_groups.items():
        if len(group) == 1:
            best_event = group[0]
        else:
            # Sort by priority order, then by id to keep sorting stable and deterministic
            group.sort(key=lambda x: (priority_map.get(x.source_type, 99), x.id))
            best_event = group[0]

            discarded_count = len(group) - 1
            if best_event.category == "messages":
                sms_stats["deduplicated"] += discarded_count
            elif best_event.category == "calls":
                call_stats["deduplicated"] += discarded_count

        deduped_events.append(best_event)
        seen_ids.add(best_event.id)

    all_deduped = other_events + deduped_events

    stats = {
        "sms": sms_stats,
        "calls": call_stats
    }
    return all_deduped, stats
