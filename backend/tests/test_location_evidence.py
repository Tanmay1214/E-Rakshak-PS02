"""Tests for location evidence acquisition module in E-RAKSHAK."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from erakshak.acquisition.location_evidence import acquire_location_evidence
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger


def test_location_evidence_ingestion(tmp_path: Path) -> None:
    case_folder = CaseFolder(tmp_path, "CASE001", "EXHIBIT001")
    case_folder.create()

    manifest_path = case_folder.exhibit_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = case_folder.exhibit_path / "hashes" / "sha256sums.txt"
    audit_path = case_folder.exhibit_path / "acquisition" / "audit.jsonl"
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = ManifestWriter(manifest_path, sha256sums_path, "CASE001", "EXHIBIT001")
    audit = AuditLogger(audit_path, "CASE001", "EXHIBIT001")

    # Create dummy media_index.jsonl containing GPS info (close to Nana Varachha 21.222, 72.885)
    media_index_path = case_folder.derived_dir / "media_index.jsonl"
    media_entry = {
        "filename": "exif_photo.jpg",
        "source_path": "/sdcard/DCIM/exif_photo.jpg",
        "local_path": str(case_folder.exhibit_path / "raw" / "media" / "exif_photo.jpg"),
        "gps_info": {
            "latitude": 21.223,
            "longitude": 72.886,
            "altitude": 10.0,
            "date_stamp": "2023:06:05",
            "time_stamp": "12:00:00"
        }
    }
    with open(media_index_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(media_entry) + "\n")

    # Create dummy cell_observations.jsonl (close to Adajan 21.195, 72.795)
    cell_obs_path = case_folder.derived_dir / "cell_observations.jsonl"
    cell_entry = {
        "timestamp": "2023-06-05T12:05:00Z",
        "latitude": 21.196,
        "longitude": 72.796,
        "accuracy": 200.0,
        "lac": 4001,
        "cid": 1002
    }
    with open(cell_obs_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(cell_entry) + "\n")

    # Mock ADB shell returns error for dumpsys location (testing missing dumpsys doesn't crash)
    mock_adb = MagicMock()
    mock_adb.serial = "emulator-5554"
    mock_adb.shell.return_value = MagicMock(
        ok=False,
        stdout="",
        stderr="Permission denied"
    )

    summary = acquire_location_evidence(
        adb=mock_adb,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit,
        include_dumpsys=True,
        include_media_exif=True,
        include_cell_observations=True,
        case_id="CASE001",
        exhibit_id="EXHIBIT001"
    )

    # Check results
    assert summary["location_records"] == 2
    assert summary["sources"]["media_exif"] == 1
    assert summary["sources"]["cell_tower"] == 1
    assert summary["sources"]["dumpsys_location"] == 0

    # Read location_evidence.jsonl output and verify nearest localities mapping
    loc_evidence_path = case_folder.derived_dir / "location_evidence.jsonl"
    assert loc_evidence_path.is_file()

    with open(loc_evidence_path, "r", encoding="utf-8") as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
        assert len(lines) == 2
        
        # EXIF Entry
        exif_rec = next(r for r in lines if r["source_type"] == "media_exif")
        assert exif_rec["latitude"] == 21.223
        assert exif_rec["longitude"] == 72.886
        assert exif_rec["nearest_locality"] == "Nana Varachha"
        
        # Cell Tower Entry
        cell_rec = next(r for r in lines if r["source_type"] == "cell_tower")
        assert cell_rec["latitude"] == 21.196
        assert cell_rec["longitude"] == 72.796
        assert cell_rec["nearest_locality"] == "Adajan"

    # Verify summary JSON output
    summary_path = case_folder.derived_dir / "location_summary.json"
    assert summary_path.is_file()
    with open(summary_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
        assert data["location_records"] == 2
        assert "Full Google Location History is not available through normal ADB." in data["warnings"]
