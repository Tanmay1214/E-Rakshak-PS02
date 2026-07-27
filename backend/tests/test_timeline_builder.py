"""Unit tests for timeline builder orchestrator and validations."""

import json
import sqlite3
from pathlib import Path
from erakshak.dashboard.timeline_builder import build_timeline


def test_timeline_builder_complete_flow(tmp_path: Path) -> None:
    # Setup mock data directory structure
    case_id = "CASE001"
    exhibit_id = "EXHIBIT001"
    
    # Setup case/exhibit directories
    ex_dir = tmp_path / case_id / exhibit_id
    ex_dir.mkdir(parents=True)
    
    derived_dir = ex_dir / "derived"
    derived_dir.mkdir()
    
    # 1. Mock SMS log
    with open(derived_dir / "sms_messages.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "body": "test sms message", "address": "+919876543210", "type": 1}) + "\n")
        
    # 2. Mock Low confidence Media log (written to raw/collector/media_index.jsonl)
    coll_dir = ex_dir / "raw" / "collector"
    coll_dir.mkdir(parents=True, exist_ok=True)
    with open(coll_dir / "media_index.jsonl", "w", encoding="utf-8") as f:
        # File modified timestamp only (which maps to low confidence in media_adapter)
        f.write(json.dumps({"modified": "2026-07-25T13:00:00+05:30", "file_path": "/sdcard/photo.jpg"}) + "\n")

    # 3. Mock WhatsApp Chat Exporter output containing a simulated raw key string to validate key redaction
    wa_dir = derived_dir / "whatsapp_exporter"
    wa_dir.mkdir()
    result_data = {
        "+919876543210@s.whatsapp.net": [
            {
                "timestamp": "2026-07-25T14:00:00+05:30",
                "message": "Here is the encryption key 00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
                "from_me": False,
                "sender": "Alice"
            }
        ]
    }
    with open(wa_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f)

    # Execute Build - Default (low confidence excluded)
    summary = build_timeline(
        case_folder_path=str(ex_dir),
        case_id=case_id,
        exhibit_id=exhibit_id,
        recent_days=7,
        timezone="Asia/Kolkata",
        include_low_confidence=False,
        rebuild=True
    )

    # 1. Output files must be created
    db_path = derived_dir / "evidence_index.db"
    jsonl_path = derived_dir / "timeline_events.jsonl"
    summary_path = derived_dir / "timeline_summary.json"

    assert db_path.exists()
    assert jsonl_path.exists()
    assert summary_path.exists()

    # 2. Assert counts
    assert summary["total_events"] == 2  # SMS + WhatsApp (Media is low confidence, so excluded)

    # 3. Check SQLite DB
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM timeline_events")
    count = cursor.fetchone()[0]
    assert count == 2

    # Verify sorting
    cursor.execute("SELECT timestamp FROM timeline_events ORDER BY timestamp_sort ASC")
    rows = cursor.fetchall()
    assert "12:00:00" in rows[0][0]
    assert "14:00:00" in rows[1][0]
    conn.close()

    # 4. Check JSONL sorting and format
    with open(jsonl_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 2
    assert "12:00:00" in lines[0]["timestamp"]
    assert "14:00:00" in lines[1]["timestamp"]

    # 5. NO SECRETS/KEYS VALIDATION
    # Check JSONL contents
    for line in lines:
        for val in line.values():
            if val and isinstance(val, str):
                assert "00112233445566778899aabbccddeeff" not in val

    # Check Summary
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "00112233445566778899aabbccddeeff" not in summary_text

    # Check Audit Logs
    audit_file = ex_dir / "acquisition" / "audit.jsonl"
    assert audit_file.exists()
    audit_text = audit_file.read_text(encoding="utf-8")
    assert "00112233445566778899aabbccddeeff" not in audit_text
    assert "timeline_build_completed" in audit_text

    # Check Manifest Logs
    manifest_file = ex_dir / "acquisition" / "acquisition_manifest.jsonl"
    assert manifest_file.exists()
    manifest_text = manifest_file.read_text(encoding="utf-8")
    assert "timeline_index" in manifest_text
    assert "timeline_events_export" in manifest_text
    assert "timeline_summary" in manifest_text

    # Check sha256sums
    hash_file = ex_dir / "hashes" / "sha256sums.txt"
    assert hash_file.exists()
    hash_text = hash_file.read_text(encoding="utf-8")
    assert "evidence_index.db" in hash_text
    assert "timeline_events.jsonl" in hash_text
    assert "timeline_summary.json" in hash_text


def test_timeline_builder_with_low_confidence(tmp_path: Path) -> None:
    # Setup mock data directory structure
    case_id = "CASE002"
    exhibit_id = "EXHIBIT002"
    ex_dir = tmp_path / case_id / exhibit_id
    ex_dir.mkdir(parents=True)
    derived_dir = ex_dir / "derived"
    derived_dir.mkdir()
    
    # Mock SMS log
    with open(derived_dir / "sms_messages.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "body": "test sms message", "address": "+919876543210", "type": 1}) + "\n")
        
    # Mock Low confidence Media log (written to raw/collector/media_index.jsonl)
    coll_dir = ex_dir / "raw" / "collector"
    coll_dir.mkdir(parents=True, exist_ok=True)
    with open(coll_dir / "media_index.jsonl", "w", encoding="utf-8") as f:
        # File modified timestamp only (which maps to low confidence in media_adapter)
        f.write(json.dumps({"modified": "2026-07-25T13:00:00+05:30", "file_path": "/sdcard/photo.jpg"}) + "\n")

    # Execute Build - With low confidence
    summary = build_timeline(
        case_folder_path=str(ex_dir),
        case_id=case_id,
        exhibit_id=exhibit_id,
        recent_days=7,
        timezone="Asia/Kolkata",
        include_low_confidence=True,
        rebuild=True
    )
    # Both SMS and Media should be included
    assert summary["total_events"] == 2
    assert summary["counts_by_confidence"].get("low") == 1
    assert summary["counts_by_confidence"].get("high") == 1


def test_timeline_builder_filters(tmp_path: Path) -> None:
    case_id = "CASE003"
    exhibit_id = "EXHIBIT003"
    ex_dir = tmp_path / case_id / exhibit_id
    ex_dir.mkdir(parents=True)
    derived_dir = ex_dir / "derived"
    derived_dir.mkdir()
    
    # 1. Mock SMS log (messages category)
    with open(derived_dir / "sms_messages.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "body": "test sms", "address": "+9198", "type": 1}) + "\n")
        
    # 2. Mock Call log (calls category)
    with open(derived_dir / "call_logs.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:01:00+05:30", "number": "+9198", "duration": 10, "type": 1}) + "\n")

    # Build with category filter = calls
    summary = build_timeline(
        case_folder_path=str(ex_dir),
        case_id=case_id,
        exhibit_id=exhibit_id,
        recent_days=7,
        filter_category="calls",
        rebuild=True
    )
    # Only Calls should be in timeline
    assert summary["total_events"] == 1
    assert summary["counts_by_category"].get("calls") == 1
    assert "messages" not in summary["counts_by_category"]
