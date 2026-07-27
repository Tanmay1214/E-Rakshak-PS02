"""Forensic Timeline Builder for E-RAKSHAK."""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.dashboard.time_utils import resolve_timeline_range, parse_timestamp
from erakshak.dashboard.timeline_models import TimelineEvent
from erakshak.dashboard.timeline_db import init_timeline_db, save_events_to_db
from erakshak.dashboard.timeline_dedupe import dedupe_events
from erakshak.dashboard.timeline_summary import generate_timeline_summary

# Import adapters
from erakshak.dashboard.timeline_adapters import (
    whatsapp_adapter,
    telegram_adapter,
    signal_adapter,
    sms_adapter,
    calls_adapter,
    media_adapter,
    apps_adapter,
    accounts_adapter,
    browser_adapter,
    location_adapter,
    network_adapter,
    system_adapter
)


def build_timeline(
    case_folder_path: str,
    case_id: str,
    exhibit_id: str,
    recent_days: int = 7,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    timezone: str = "Asia/Kolkata",
    include_low_confidence: bool = False,
    rebuild: bool = False,
    filter_category: Optional[str] = None,
    filter_source_app: Optional[str] = None,
    filter_source_type: Optional[str] = None
) -> Dict[str, Any]:
    """Orchestrate the Unified forensic timeline building process."""
    case_folder = Path(case_folder_path).resolve()
    
    # 1. Resolve date range
    range_info = resolve_timeline_range(recent_days, from_date, to_date, timezone)
    from_dt = range_info["from_dt"]
    to_dt = range_info["to_dt"]

    # 2. Ensure target directories exist
    derived_dir = case_folder / "derived"
    acquisition_dir = case_folder / "acquisition"
    hashes_dir = case_folder / "hashes"
    
    derived_dir.mkdir(parents=True, exist_ok=True)
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    hashes_dir.mkdir(parents=True, exist_ok=True)

    # Paths for output files
    db_path = derived_dir / "evidence_index.db"
    jsonl_path = derived_dir / "timeline_events.jsonl"
    summary_path = derived_dir / "timeline_summary.json"

    # 3. Setup SQLite Database
    init_timeline_db(db_path)

    # 4. Load events from all adapters
    adapters = [
        whatsapp_adapter,
        telegram_adapter,
        signal_adapter,
        sms_adapter,
        calls_adapter,
        media_adapter,
        apps_adapter,
        accounts_adapter,
        browser_adapter,
        location_adapter,
        network_adapter,
        system_adapter
    ]

    all_raw_events: List[TimelineEvent] = []
    all_warnings: List[str] = []
    missing_sources: List[str] = []

    for adapter in adapters:
        try:
            events, warnings = adapter.load_events(case_folder, case_id, exhibit_id, timezone)
            all_raw_events.extend(events)
            for w in warnings:
                all_warnings.append(w)
                # Classify as missing source if warning indicates it is missing
                if "not found" in w.lower() or "missing" in w.lower() or "not exist" in w.lower():
                    # Extract file name or description if possible
                    missing_sources.append(w)
        except Exception as e:
            all_warnings.append(f"Adapter {adapter.__name__} failed to execute: {e}")

    # 5. Deduplicate events
    deduped_events, dual_lane_stats = dedupe_events(all_raw_events)

    # 6. Apply filters
    filtered_events: List[TimelineEvent] = []
    for e in deduped_events:
        # Confidence filter
        if e.confidence == "low" and not include_low_confidence:
            continue

        # Category filter
        if filter_category and e.category != filter_category:
            continue

        # Source App filter
        if filter_source_app and e.source_app != filter_source_app:
            continue

        # Source Type filter
        if filter_source_type and e.source_type != filter_source_type:
            continue

        # Time range filter
        evt_dt = parse_timestamp(e.timestamp, timezone)
        if evt_dt:
            if not (from_dt <= evt_dt <= to_dt):
                continue
        else:
            # If timestamp parse fails, skip
            all_warnings.append(f"Skipped event {e.id} due to invalid formatted timestamp: {e.timestamp}")
            continue

        filtered_events.append(e)

    # 7. Sort by timestamp_sort ascending
    filtered_events.sort(key=lambda x: (x.timestamp_sort, x.id))

    # 8. Save events to SQLite
    save_events_to_db(
        db_path=db_path,
        events=filtered_events,
        rebuild=rebuild,
        case_id=case_id,
        exhibit_id=exhibit_id
    )

    # 9. Save events to JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for e in filtered_events:
            # Prevent WhatsApp encryption key leaks in raw_json/summary
            # Ensure no secrets leak
            clean_dict = e.to_dict()
            if clean_dict.get("raw_json"):
                # Clean nested raw_json string to be safe
                try:
                    js = json.loads(clean_dict["raw_json"])
                    if isinstance(js, dict):
                        js = {k: v for k, v in js.items() if "key" not in k.lower()}
                        clean_dict["raw_json"] = json.dumps(js, ensure_ascii=False)
                except Exception:
                    pass
            f.write(json.dumps(clean_dict, ensure_ascii=False) + "\n")

    # 10. Generate and save summary
    filters_dict = {
        "category": filter_category,
        "source_app": filter_source_app,
        "source_type": filter_source_type,
        "include_low_confidence": include_low_confidence
    }
    summary_data = generate_timeline_summary(
        case_id=case_id,
        exhibit_id=exhibit_id,
        events=filtered_events,
        date_range_info=range_info,
        recent_days=recent_days,
        filters=filters_dict,
        dual_lane_stats=dual_lane_stats,
        missing_sources=missing_sources,
        warnings=all_warnings
    )
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # 11. Manifest and Audit Trail updates
    manifest_path = acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = hashes_dir / "sha256sums.txt"
    audit_path = acquisition_dir / "audit.jsonl"

    manifest_writer = ManifestWriter(
        manifest_path=manifest_path,
        sha256sums_path=sha256sums_path,
        case_id=case_id,
        exhibit_id=exhibit_id
    )
    audit_logger = AuditLogger(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id
    )

    # Add output files to manifest
    manifest_writer.add_file(
        artifact_class="timeline_index",
        source_type="normalized_derived",
        source_command_or_path="timeline_db_generation",
        destination_path=db_path
    )
    manifest_writer.add_file(
        artifact_class="timeline_events_export",
        source_type="normalized_derived",
        source_command_or_path="timeline_jsonl_generation",
        destination_path=jsonl_path
    )
    manifest_writer.add_file(
        artifact_class="timeline_summary",
        source_type="normalized_derived",
        source_command_or_path="timeline_summary_generation",
        destination_path=summary_path
    )

    # Log completion audit event
    audit_details = {
        "date_range_mode": range_info["mode"],
        "recent_days": recent_days,
        "from": range_info["from"],
        "to": range_info["to"],
        "filters": filters_dict,
        "total_events": len(filtered_events),
        "missing_sources_count": len(missing_sources),
        "warnings_count": len(all_warnings),
        "dual_lane_sms_sources": dual_lane_stats.get("sms", {}),
        "dual_lane_call_sources": dual_lane_stats.get("calls", {})
    }
    audit_logger.log(
        action="timeline_build_completed",
        result="success",
        warning=f"{len(all_warnings)} warnings logged" if all_warnings else "",
        output_path=str(jsonl_path)
    )
    
    # Custom details injection into audit logs (we can write manually to audit file if needed to store detailed audit_details)
    # The default audit logger doesn't have details, but we can write a clean JSON entry for detail audit log tracking:
    try:
        # Append detailed completion event to audit.jsonl manually
        with open(audit_path, "a", encoding="utf-8") as af:
            detailed_record = {
                "timestamp": summary_data["date_range"]["to"],
                "case_id": case_id,
                "exhibit_id": exhibit_id,
                "action": "timeline_build_completed",
                "result": "success",
                "details": audit_details
            }
            af.write(json.dumps(detailed_record, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return summary_data
