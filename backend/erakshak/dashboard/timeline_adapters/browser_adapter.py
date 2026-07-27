"""Browser timeline adapter for E-RAKSHAK."""

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
    """Load browser visit, search, and download records from derived JSONL outputs."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    derived_dir = case_folder / "derived"

    browser_sources = [
        ("browser_history.jsonl", "browser_visit", "Web Visit"),
        ("browser_searches.jsonl", "browser_search", "Search Query"),
        ("browser_downloads.jsonl", "browser_download", "File Download")
    ]

    for filename, event_type, base_title in browser_sources:
        filepath = derived_dir / filename
        if not filepath.is_file():
            # Missing files are skipped without crash; we record warnings
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
                    raw_ts = record.get("timestamp")
                    if not raw_ts:
                        row_idx += 1
                        warnings.append(f"Browser record in {filename} lacks timestamp. Skipped.")
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        warnings.append(f"Browser record in {filename} has unparseable timestamp: {raw_ts}. Skipped.")
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    browser_app = record.get("browser") or record.get("package_name") or "Chrome"

                    # Determine summaries and links based on event types
                    if event_type == "browser_visit":
                        url = record.get("url") or ""
                        title_text = record.get("title") or ""
                        summary = f"Visited {title_text or url}"
                        title = f"Web Visit ({browser_app})"
                    elif event_type == "browser_search":
                        term = record.get("search_term") or ""
                        url = record.get("url") or ""
                        summary = f"Searched: {term}"
                        title = f"Search Term ({browser_app})"
                    else:  # browser_download
                        target = record.get("target_path") or ""
                        d_url = record.get("download_url") or ""
                        summary = f"Downloaded file to {Path(target).name if target else d_url}"
                        title = f"File Downloaded ({browser_app})"

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
                        source_app=browser_app,
                        source_type="browser_history_db",
                        category="browser",
                        event_type=event_type,
                        title=title,
                        summary=summary,
                        actor=record.get("profile", "Default"),
                        phone_number=None,
                        email=None,
                        file_path=record.get("target_path") if event_type == "browser_download" else None,
                        confidence="high",
                        source_file=str(filepath.relative_to(case_folder)),
                        parser="ChromiumHistoryParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing browser evidence file {filename}: {e}")

    # Check warnings
    for filename, _, _ in browser_sources:
        if not (derived_dir / filename).is_file():
            warnings.append(f"derived/{filename} not found.")

    return events, warnings
