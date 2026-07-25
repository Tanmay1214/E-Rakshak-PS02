"""Location evidence acquisition and parsing module for E-RAKSHAK.

Acquires dumpsys location snapshots, parses cell observations, extracts GPS
data from media EXIF metadata, maps Surat localities, and writes summaries.
"""

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from erakshak.adb.client import ADBClient, ADBResult
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.config.defaults import (
    DEFAULT_ADB_TIMEOUT,
    STATUS_ACQUIRED,
    STATUS_FAILED,
    STATUS_NOT_EXPOSED,
)
from erakshak.adb.parsers import parse_location_dumpsys
from erakshak.acquisition.media import extract_gps_from_exif


LOCALITIES_PATH = Path(__file__).resolve().parent.parent / "config" / "surat_localities.json"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the Haversine distance in kilometers between two GPS coordinates."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def nearest_surat_locality(lat: float, lon: float, threshold_km: float = 5.0) -> Optional[dict[str, Any]]:
    """Return the nearest Surat locality within threshold_km limit, else None."""
    try:
        if not LOCALITIES_PATH.is_file():
            return None
        with open(LOCALITIES_PATH, "r", encoding="utf-8") as f:
            localities = json.load(f)

        nearest_name = None
        min_dist = float("inf")

        for loc in localities:
            dist = haversine_distance(lat, lon, loc["latitude"], loc["longitude"])
            if dist < min_dist:
                min_dist = dist
                nearest_name = loc["name"]

        if min_dist <= threshold_km:
            return {"name": nearest_name, "distance_km": round(min_dist, 3)}
    except Exception:
        pass
    return None


def acquire_location_evidence(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
    *,
    include_dumpsys: bool = True,
    include_media_exif: bool = True,
    include_cell_observations: bool = True,
    case_id: str = "",
    exhibit_id: str = "",
) -> dict[str, Any]:
    """Extract location evidence from dumpsys, media files, and cell towers."""
    started_at = datetime.now(timezone.utc).isoformat()
    warnings = ["Full Google Location History is not available through normal ADB."]
    
    raw_location_dir = case_folder.exhibit_path / "raw" / "location"
    raw_location_dir.mkdir(parents=True, exist_ok=True)
    
    location_records = []
    
    sources_counts = {
        "media_exif": 0,
        "mediastore": 0,
        "cell_tower": 0,
        "dumpsys_location": 0,
        "app_artifact": 0,
    }

    # 1. Acquire and parse live location snapshots from ADB
    if include_dumpsys:
        # Dumpsys location
        loc_res: ADBResult = adb.shell(["dumpsys", "location"], timeout=DEFAULT_ADB_TIMEOUT, audit_action="location_dumpsys")
        raw_loc_path = raw_location_dir / "dumpsys_location.txt"
        if loc_res.return_code == 0:
            raw_loc_path.write_text(loc_res.stdout, encoding="utf-8")
            manifest.add_file(
                artifact_class="dumpsys_location_raw",
                source_type="adb_command",
                source_command_or_path="adb shell dumpsys location",
                destination_path=raw_loc_path,
                status=STATUS_ACQUIRED,
                started_at=started_at,
            )
            
            # Parse coordinates
            parsed_locs = parse_location_dumpsys(loc_res.stdout)
            for loc in parsed_locs:
                ts_iso = None
                if loc.get("timestamp_ms"):
                    try:
                        ts_iso = datetime.fromtimestamp(loc["timestamp_ms"] / 1000.0, timezone.utc).isoformat()
                    except Exception:
                        pass
                if not ts_iso:
                    ts_iso = started_at
                    
                nearest = nearest_surat_locality(loc["latitude"], loc["longitude"])
                
                location_records.append({
                    "timestamp": ts_iso,
                    "source_type": "dumpsys_location",
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "accuracy_meters": loc.get("accuracy"),
                    "nearest_locality": nearest["name"] if nearest else None,
                    "source_file": "dumpsys_location.txt",
                    "linked_media_path": None,
                    "confidence": "medium",
                    "notes": f"Provider: {loc.get('provider', 'unknown')}",
                })
                sources_counts["dumpsys_location"] += 1
        else:
            manifest.add_status_record(
                artifact_class="dumpsys_location_raw",
                source_type="adb_command",
                source_command_or_path="adb shell dumpsys location",
                status=STATUS_FAILED,
                reason_code=str(loc_res.stderr),
            )

        # Dumpsys location GNSS
        gnss_res: ADBResult = adb.shell(["dumpsys", "location", "--gnss"], timeout=DEFAULT_ADB_TIMEOUT, audit_action="location_gnss")
        raw_gnss_path = raw_location_dir / "dumpsys_location_gnss.txt"
        if gnss_res.return_code == 0:
            raw_gnss_path.write_text(gnss_res.stdout, encoding="utf-8")
            manifest.add_file(
                artifact_class="dumpsys_location_gnss_raw",
                source_type="adb_command",
                source_command_or_path="adb shell dumpsys location --gnss",
                destination_path=raw_gnss_path,
                status=STATUS_ACQUIRED,
                started_at=started_at,
            )
        else:
            manifest.add_status_record(
                artifact_class="dumpsys_location_gnss_raw",
                source_type="adb_command",
                source_command_or_path="adb shell dumpsys location --gnss",
                status=STATUS_FAILED,
                reason_code=str(gnss_res.stderr),
            )

    # 2. Ingest location from Media EXIF metadata (either from index or direct scanning)
    if include_media_exif:
        media_index_path = case_folder.derived_dir / "media_index.jsonl"
        # Try to parse from existing media_index first
        if media_index_path.is_file():
            try:
                with open(media_index_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        gps_info = entry.get("gps_info")
                        if gps_info and gps_info.get("latitude") is not None:
                            lat = gps_info["latitude"]
                            lon = gps_info["longitude"]
                            nearest = nearest_surat_locality(lat, lon)
                            
                            ts = "unknown"
                            if gps_info.get("date_stamp"):
                                ts = f"{gps_info['date_stamp']} {gps_info.get('time_stamp', '')}".strip()
                            else:
                                ts = entry.get("modified_time") or started_at
                                
                            location_records.append({
                                "timestamp": ts,
                                "source_type": "media_exif",
                                "latitude": lat,
                                "longitude": lon,
                                "accuracy_meters": None,
                                "nearest_locality": nearest["name"] if nearest else None,
                                "source_file": "media_index.jsonl",
                                "linked_media_path": entry.get("local_path"),
                                "confidence": "high",
                                "notes": f"Filename: {entry.get('filename')}",
                            })
                            sources_counts["media_exif"] += 1
            except Exception as e:
                warnings.append(f"Error parsing media_index.jsonl for GPS: {e}")
        
        # Ingest directly from raw/media/ folder if pulled JPEGs are present and not already processed
        raw_media_folder = case_folder.exhibit_path / "raw" / "media"
        if raw_media_folder.is_dir() and sources_counts["media_exif"] == 0:
            for filepath in raw_media_folder.glob("**/*"):
                if filepath.is_file() and filepath.suffix.lower() in (".jpg", ".jpeg"):
                    gps_info = extract_gps_from_exif(filepath)
                    if gps_info and gps_info.get("latitude") is not None:
                        lat = gps_info["latitude"]
                        lon = gps_info["longitude"]
                        nearest = nearest_surat_locality(lat, lon)
                        
                        ts = "unknown"
                        if gps_info.get("date_stamp"):
                            ts = f"{gps_info['date_stamp']} {gps_info.get('time_stamp', '')}".strip()
                        else:
                            ts = started_at
                            
                        location_records.append({
                            "timestamp": ts,
                            "source_type": "media_exif",
                            "latitude": lat,
                            "longitude": lon,
                            "accuracy_meters": None,
                            "nearest_locality": nearest["name"] if nearest else None,
                            "source_file": filepath.name,
                            "linked_media_path": str(filepath),
                            "confidence": "high",
                            "notes": f"Filename: {filepath.name}",
                        })
                        sources_counts["media_exif"] += 1

        # Also ingest from raw/collector/media_index.jsonl if available
        coll_media_index = case_folder.exhibit_path / "raw" / "collector" / "media_index.jsonl"
        if coll_media_index.is_file():
            try:
                with open(coll_media_index, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        # MediaStore sometimes has direct lat/lon columns
                        lat = entry.get("latitude")
                        lon = entry.get("longitude")
                        if lat is not None and lon is not None:
                            nearest = nearest_surat_locality(lat, lon)
                            ts = entry.get("date_added") or entry.get("modified_time") or started_at
                            location_records.append({
                                "timestamp": ts,
                                "source_type": "mediastore",
                                "latitude": float(lat),
                                "longitude": float(lon),
                                "accuracy_meters": None,
                                "nearest_locality": nearest["name"] if nearest else None,
                                "source_file": "collector/media_index.jsonl",
                                "linked_media_path": entry.get("relative_path"),
                                "confidence": "high",
                                "notes": f"MediaStore metadata index",
                            })
                            sources_counts["mediastore"] += 1
            except Exception as e:
                warnings.append(f"Error parsing collector media_index.jsonl for GPS: {e}")

    # 3. Ingest cell observations if available
    if include_cell_observations:
        cell_obs_path = case_folder.derived_dir / "cell_observations.jsonl"
        if cell_obs_path.is_file():
            try:
                with open(cell_obs_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        lat = entry.get("latitude")
                        lon = entry.get("longitude")
                        if lat is not None and lon is not None:
                            nearest = nearest_surat_locality(lat, lon)
                            location_records.append({
                                "timestamp": entry.get("timestamp") or started_at,
                                "source_type": "cell_tower",
                                "latitude": float(lat),
                                "longitude": float(lon),
                                "accuracy_meters": entry.get("accuracy"),
                                "nearest_locality": nearest["name"] if nearest else None,
                                "source_file": "cell_observations.jsonl",
                                "linked_media_path": None,
                                "confidence": "low",
                                "notes": f"Cell Tower: LAC={entry.get('lac')}, CID={entry.get('cid')}",
                            })
                            sources_counts["cell_tower"] += 1
            except Exception as e:
                warnings.append(f"Error parsing cell_observations.jsonl: {e}")

    # Sort location records by timestamp
    try:
        location_records.sort(key=lambda x: x["timestamp"])
    except Exception:
        pass

    # Determine date range
    first_date = None
    last_date = None
    valid_dates = [r["timestamp"] for r in location_records if r["timestamp"] != "unknown"]
    if valid_dates:
        first_date = min(valid_dates)
        last_date = max(valid_dates)

    # 4. Write location_evidence.jsonl
    loc_jsonl = case_folder.derived_dir / "location_evidence.jsonl"
    with open(loc_jsonl, "w", encoding="utf-8") as f:
        for r in location_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest.add_file(
        artifact_class="location_evidence",
        source_type="parsed",
        source_command_or_path="location_evidence_acq",
        destination_path=loc_jsonl,
        status=STATUS_ACQUIRED if location_records else STATUS_NOT_EXPOSED,
    )

    # 5. Write location_summary.json
    summary_path = case_folder.derived_dir / "location_summary.json"
    summary_data = {
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "location_records": len(location_records),
        "sources": sources_counts,
        "date_range": {
            "first": first_date,
            "last": last_date,
        },
        "warnings": warnings,
    }
    
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    manifest.add_file(
        artifact_class="location_summary",
        source_type="parsed",
        source_command_or_path="location_evidence_acq",
        destination_path=summary_path,
        status=STATUS_ACQUIRED,
    )

    # Log to audit trail
    audit.log(
        action="collect_location_evidence",
        command_category="location",
        result="success" if location_records else "success_no_data",
        warning="; ".join(warnings) if warnings else None,
        output_path=str(summary_path),
    )

    return summary_data
