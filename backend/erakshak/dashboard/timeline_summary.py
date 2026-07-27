"""Timeline summary generator for E-RAKSHAK."""

from typing import List, Dict, Any, Optional
from erakshak.dashboard.timeline_models import TimelineEvent


def generate_timeline_summary(
    case_id: str,
    exhibit_id: str,
    events: List[TimelineEvent],
    date_range_info: Dict[str, Any],
    recent_days: int,
    filters: Dict[str, Any],
    dual_lane_stats: Dict[str, Any],
    missing_sources: List[str],
    warnings: List[str]
) -> Dict[str, Any]:
    """Compile counts and stats to write the timeline_summary.json file."""
    counts_by_category: Dict[str, int] = {}
    counts_by_source_app: Dict[str, int] = {}
    counts_by_source_type: Dict[str, int] = {}
    counts_by_confidence: Dict[str, int] = {}
    counts_by_day: Dict[str, int] = {}

    for e in events:
        # Category count
        cat = e.category or "unknown"
        counts_by_category[cat] = counts_by_category.get(cat, 0) + 1

        # Source app count
        app = e.source_app or "unknown"
        counts_by_source_app[app] = counts_by_source_app.get(app, 0) + 1

        # Source type count
        stype = e.source_type or "unknown"
        counts_by_source_type[stype] = counts_by_source_type.get(stype, 0) + 1

        # Confidence count
        conf = e.confidence or "high"
        counts_by_confidence[conf] = counts_by_confidence.get(conf, 0) + 1

        # Day count (using YYYY-MM-DD from timestamp)
        if e.timestamp:
            day_str = e.timestamp.split("T")[0]
            counts_by_day[day_str] = counts_by_day.get(day_str, 0) + 1

    return {
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "date_range": {
            "mode": date_range_info.get("mode", "recent_days"),
            "from": date_range_info.get("from", ""),
            "to": date_range_info.get("to", "")
        },
        "recent_days": recent_days,
        "filters": {
            "category": filters.get("category"),
            "source_app": filters.get("source_app"),
            "source_type": filters.get("source_type"),
            "include_low_confidence": filters.get("include_low_confidence", False)
        },
        "total_events": len(events),
        "counts_by_category": counts_by_category,
        "counts_by_source_app": counts_by_source_app,
        "counts_by_source_type": counts_by_source_type,
        "counts_by_confidence": counts_by_confidence,
        "counts_by_day": counts_by_day,
        "dual_lane_sources": {
            "sms": {
                "normalized_derived": dual_lane_stats.get("sms", {}).get("normalized_derived", 0),
                "adb_content_provider": dual_lane_stats.get("sms", {}).get("adb_content_provider", 0),
                "collector_app_import": dual_lane_stats.get("sms", {}).get("collector_app_import", 0),
                "deduplicated": dual_lane_stats.get("sms", {}).get("deduplicated", 0)
            },
            "calls": {
                "normalized_derived": dual_lane_stats.get("calls", {}).get("normalized_derived", 0),
                "adb_content_provider": dual_lane_stats.get("calls", {}).get("adb_content_provider", 0),
                "collector_app_import": dual_lane_stats.get("calls", {}).get("collector_app_import", 0),
                "deduplicated": dual_lane_stats.get("calls", {}).get("deduplicated", 0)
            }
        },
        "missing_sources": missing_sources,
        "warnings": warnings
    }
