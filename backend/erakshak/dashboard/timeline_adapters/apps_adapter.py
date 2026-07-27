"""Apps timeline adapter for E-RAKSHAK."""

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
    """Load package install and update logs from derived/installed_apps.jsonl."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    apps_file = case_folder / "derived" / "installed_apps.jsonl"
    if not apps_file.is_file():
        warnings.append("derived/installed_apps.jsonl not found.")
        return events, warnings

    try:
        row_idx = 0
        with open(apps_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    app = json.loads(line)
                except Exception as e:
                    warnings.append(f"Malformed JSON line in derived/installed_apps.jsonl: {e}. Skipped.")
                    continue

                pkg = app.get("package_name") or "unknown"
                ver = app.get("version_name") or app.get("version_code") or "unknown"
                
                # Check 1: Install Event
                install_time = app.get("first_install_time") or app.get("install_time")
                if install_time:
                    dt = parse_timestamp(install_time, timezone)
                    if dt:
                        ts_iso = to_iso(dt)
                        ts_sort = to_epoch_ms(dt)
                        summary = f"App Installed: {pkg} (v{ver})"
                        evt_id = make_event_id(
                            case_id=case_id,
                            exhibit_id=exhibit_id,
                            source_file=str(apps_file.relative_to(case_folder)),
                            row_index=row_idx,
                            timestamp=ts_iso,
                            event_type="app_installed",
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
                            source_app="Android",
                            source_type="package_manager",
                            category="apps",
                            event_type="app_installed",
                            title=f"Application Installed: {pkg}",
                            summary=summary,
                            confidence="high",
                            source_file=str(apps_file.relative_to(case_folder)),
                            parser="PackageManagerParser",
                            raw_json=line
                        ))
                
                # Check 2: Update Event (if different from install time)
                update_time = app.get("last_update_time") or app.get("update_time")
                if update_time and update_time != install_time:
                    dt = parse_timestamp(update_time, timezone)
                    if dt:
                        ts_iso = to_iso(dt)
                        ts_sort = to_epoch_ms(dt)
                        summary = f"App Updated: {pkg} (v{ver})"
                        evt_id = make_event_id(
                            case_id=case_id,
                            exhibit_id=exhibit_id,
                            source_file=str(apps_file.relative_to(case_folder)),
                            row_index=row_idx + 100000, # ensure different row_index offset
                            timestamp=ts_iso,
                            event_type="app_updated",
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
                            source_app="Android",
                            source_type="package_manager",
                            category="apps",
                            event_type="app_updated",
                            title=f"Application Updated: {pkg}",
                            summary=summary,
                            confidence="high",
                            source_file=str(apps_file.relative_to(case_folder)),
                            parser="PackageManagerParser",
                            raw_json=line
                        ))

                row_idx += 1

    except Exception as e:
        warnings.append(f"Failed parsing derived/installed_apps.jsonl: {e}")

    return events, warnings
