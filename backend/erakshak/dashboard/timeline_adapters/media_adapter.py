"""Media timeline adapter for E-RAKSHAK."""

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
    """Load media captures/files logs from derived and raw/collector indexes."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    media_sources = [
        (case_folder / "derived" / "media_index.jsonl", "mediastore", "high"),
        (case_folder / "raw" / "collector" / "media_index.jsonl", "filesystem", "high")
    ]

    for source_file, source_type, base_confidence in media_sources:
        if not source_file.is_file():
            # If both are missing, we warn later or skip silently
            continue

        try:
            row_idx = 0
            with open(source_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in {source_file.name}: {e}. Skipped.")
                        continue

                    # Extract timestamp
                    raw_ts = item.get("date_taken") or item.get("modified") or item.get("timestamp") or item.get("date_added")
                    if not raw_ts:
                        row_idx += 1
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    file_path = item.get("file_path") or item.get("path") or "unknown_file"
                    media_path = item.get("media_path") or file_path
                    mime = str(item.get("mime_type") or "").lower()

                    # Determine event type
                    if mime.startswith("image") or file_path.endswith((".jpg", ".jpeg", ".png", ".gif")):
                        event_type = "image_captured"
                        title = "Image Captured/Saved"
                    elif mime.startswith("video") or file_path.endswith((".mp4", ".3gp", ".mkv", ".avi")):
                        event_type = "video_found"
                        title = "Video Saved"
                    elif mime.startswith("audio") or file_path.endswith((".mp3", ".wav", ".aac", ".ogg")):
                        event_type = "audio_found"
                        title = "Audio Track Saved"
                    else:
                        event_type = "media_file"
                        title = "Media File Indexed"

                    summary = f"File: {Path(file_path).name} ({mime or 'unknown format'})"

                    # Determine confidence: if filesystem timestamp only, mark low
                    confidence = base_confidence
                    if not item.get("date_taken") and item.get("modified") and source_type == "filesystem":
                        confidence = "low"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(source_file.relative_to(case_folder)),
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
                        source_app="Media",
                        source_type=source_type,
                        category="media",
                        event_type=event_type,
                        title=title,
                        summary=summary,
                        file_path=file_path,
                        media_path=media_path,
                        thumbnail_path=item.get("thumbnail_path"),
                        confidence=confidence,
                        source_file=str(source_file.relative_to(case_folder)),
                        parser="MediaIndexer",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing media index {source_file.name}: {e}")

    # Check warning if both missing
    if not (case_folder / "derived" / "media_index.jsonl").is_file() and not (case_folder / "raw" / "collector" / "media_index.jsonl").is_file():
        warnings.append("derived/media_index.jsonl and raw/collector/media_index.jsonl files not found.")

    return events, warnings
