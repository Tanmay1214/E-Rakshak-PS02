"""Location timeline adapter for E-RAKSHAK."""

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
    """Load geolocational data coordinates logs from derived/location_evidence.jsonl."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    loc_file = case_folder / "derived" / "location_evidence.jsonl"
    if not loc_file.is_file():
        warnings.append("derived/location_evidence.jsonl not found.")
        return events, warnings

    try:
        row_idx = 0
        with open(loc_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    loc = json.loads(line)
                except Exception as e:
                    warnings.append(f"Malformed JSON line in derived/location_evidence.jsonl: {e}. Skipped.")
                    continue

                # Extract timestamp
                raw_ts = loc.get("timestamp")
                if not raw_ts:
                    row_idx += 1
                    warnings.append("Location record in derived/location_evidence.jsonl lacks timestamp. Skipped.")
                    continue

                dt = parse_timestamp(raw_ts, timezone)
                if not dt:
                    row_idx += 1
                    warnings.append(f"Location record in derived/location_evidence.jsonl has unparseable timestamp: {raw_ts}. Skipped.")
                    continue

                ts_iso = to_iso(dt)
                ts_sort = to_epoch_ms(dt)

                lat = loc.get("latitude")
                lon = loc.get("longitude")
                accuracy = loc.get("accuracy_meters")
                locality = loc.get("nearest_locality")
                notes = loc.get("notes") or ""

                source_type = loc.get("source_type") or "unknown"
                event_type = f"location_{source_type}"

                title = f"Location Log ({source_type.replace('_', ' ').capitalize()})"

                summary = f"Coordinates: {lat:.6f}, {lon:.6f}"
                if locality:
                    summary += f" (Near {locality})"
                if notes:
                    summary += f" - {notes}"

                evt_id = make_event_id(
                    case_id=case_id,
                    exhibit_id=exhibit_id,
                    source_file=str(loc_file.relative_to(case_folder)),
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
                    source_app="Location",
                    source_type=source_type,
                    category="locations",
                    event_type=event_type,
                    title=title,
                    summary=summary,
                    location_lat=lat,
                    location_lon=lon,
                    location_accuracy=accuracy,
                    media_path=loc.get("linked_media_path"),
                    confidence=loc.get("confidence") or "medium",
                    source_file=str(loc_file.relative_to(case_folder)),
                    parser="LocationEvidenceParser",
                    raw_json=line
                ))
                row_idx += 1

    except Exception as e:
        warnings.append(f"Failed parsing derived/location_evidence.jsonl: {e}")

    return events, warnings
