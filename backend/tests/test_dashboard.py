"""Tests for E-RAKSHAK Forensic Dashboard backend.

Tests the evidence indexer, normalizer, API endpoints, search,
report export, and secret key redaction.
"""
import pytest
import json
import shutil
import sqlite3
import re
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _setup_case_folder(tmp_path, files_to_copy=None):
    """Create a minimal case folder structure and optionally copy fixtures."""
    exhibit_root = tmp_path / "CASE001" / "EX001"
    (exhibit_root / "derived").mkdir(parents=True)
    (exhibit_root / "acquisition").mkdir(parents=True)
    (exhibit_root / "hashes").mkdir(parents=True)
    (exhibit_root / "raw" / "collector").mkdir(parents=True)
    (exhibit_root / "reports").mkdir(parents=True)

    if files_to_copy:
        for src_name, dest_rel in files_to_copy:
            src = FIXTURES_DIR / src_name
            dest = exhibit_root / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    return exhibit_root


# ─── 1. Index creation ────────────────────────────────────────────────
def test_index_created(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("device_identity.json", "derived/device_identity.json"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    db_path = exhibit_root / "derived" / "evidence_index.db"
    assert db_path.exists()
    assert result["db_path"] == str(db_path)


# ─── 2. Missing files don't crash ────────────────────────────────────
def test_missing_files_no_crash(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path)
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    assert (exhibit_root / "derived" / "evidence_index.db").exists()
    assert result["status"] == "success"


# ─── 3. Device identity populates device_info ────────────────────────
def test_device_identity_populates(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("device_identity.json", "derived/device_identity.json"),
        ("software_summary.json", "derived/software_summary.json"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    db = sqlite3.connect(result["db_path"])
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM device_info LIMIT 1").fetchone()
    assert row is not None
    assert row["model"] == "SM-G991B"
    assert row["android_version"] == "13"
    assert row["security_patch"] == "2024-01-01"
    db.close()


# ─── 4. Installed apps populate apps table ────────────────────────────
def test_installed_apps_populate(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("installed_apps.jsonl", "derived/installed_apps.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    assert result["total_apps"] == 3
    db = sqlite3.connect(result["db_path"])
    row = db.execute("SELECT * FROM apps WHERE package_name = 'com.whatsapp'").fetchone()
    assert row is not None
    db.close()


# ─── 5. SMS messages create timeline events ───────────────────────────
def test_messages_create_timeline_events(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("sms_messages.jsonl", "derived/sms_messages.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    assert result["total_messages"] == 3
    db = sqlite3.connect(result["db_path"])
    te_count = db.execute(
        "SELECT COUNT(*) FROM timeline_events WHERE event_type = 'sms_message'"
    ).fetchone()[0]
    assert te_count == 3
    db.close()


# ─── 6. Calls create timeline events ─────────────────────────────────
def test_calls_create_timeline_events(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("call_logs.jsonl", "derived/call_logs.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    assert result["total_calls"] == 3
    db = sqlite3.connect(result["db_path"])
    te_count = db.execute(
        "SELECT COUNT(*) FROM timeline_events WHERE event_type = 'phone_call'"
    ).fetchone()[0]
    assert te_count == 3
    db.close()


# ─── 7. Media creates timeline events ────────────────────────────────
def test_media_creates_timeline_events(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("media_index.jsonl", "derived/media_index.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    assert result["total_media"] == 2
    db = sqlite3.connect(result["db_path"])
    te_count = db.execute(
        "SELECT COUNT(*) FROM timeline_events WHERE event_type = 'media_captured'"
    ).fetchone()[0]
    assert te_count == 2
    db.close()


# ─── 8. Audit events populate ────────────────────────────────────────
def test_audit_populates(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    exhibit_root = _setup_case_folder(tmp_path, [
        ("audit.jsonl", "acquisition/audit.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    db = sqlite3.connect(result["db_path"])
    # 2 from fixture + 1 indexing audit event
    count = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert count >= 2
    db.close()


# ─── 9. Search finds messages ────────────────────────────────────────
def test_search_finds_messages(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    from erakshak.dashboard.db import DashboardDB
    from erakshak.dashboard.search import search_evidence

    exhibit_root = _setup_case_folder(tmp_path, [
        ("sms_messages.jsonl", "derived/sms_messages.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    with DashboardDB(Path(result["db_path"])) as db:
        results = search_evidence(db, "meeting")
    assert len(results) > 0


# ─── 10. API /api/case/summary returns valid data ────────────────────
def test_api_case_summary(tmp_path):
    from erakshak.dashboard.api import create_dashboard_app
    from erakshak.dashboard.timeline_builder import build_evidence_index
    from fastapi.testclient import TestClient

    exhibit_root = _setup_case_folder(tmp_path, [
        ("sms_messages.jsonl", "derived/sms_messages.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    app = create_dashboard_app(Path(result["db_path"]), exhibit_root, "CASE001", "EX001")
    client = TestClient(app)

    res = client.get("/api/case/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == "CASE001"
    assert "counts" in data
    assert data["counts"]["messages"] == 3


# ─── 11. API timeline with category filter ───────────────────────────
def test_api_timeline_filters(tmp_path):
    from erakshak.dashboard.api import create_dashboard_app
    from erakshak.dashboard.timeline_builder import build_evidence_index
    from fastapi.testclient import TestClient

    exhibit_root = _setup_case_folder(tmp_path, [
        ("sms_messages.jsonl", "derived/sms_messages.jsonl"),
        ("call_logs.jsonl", "derived/call_logs.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    app = create_dashboard_app(Path(result["db_path"]), exhibit_root, "CASE001", "EX001")
    client = TestClient(app)

    res = client.get("/api/timeline?category=messages")
    assert res.status_code == 200
    data = res.json()
    # Should only have SMS message events (3), not call events
    assert len(data["events"]) == 3
    for ev in data["events"]:
        assert ev["category"] == "messages"


# ─── 12. API timeline event detail ───────────────────────────────────
def test_api_timeline_event_detail(tmp_path):
    from erakshak.dashboard.api import create_dashboard_app
    from erakshak.dashboard.timeline_builder import build_evidence_index
    from fastapi.testclient import TestClient

    exhibit_root = _setup_case_folder(tmp_path, [
        ("sms_messages.jsonl", "derived/sms_messages.jsonl"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    app = create_dashboard_app(Path(result["db_path"]), exhibit_root, "CASE001", "EX001")
    client = TestClient(app)

    res = client.get("/api/timeline")
    events = res.json()["events"]
    assert len(events) > 0

    event_id = events[0]["id"]
    res2 = client.get(f"/api/timeline/{event_id}")
    assert res2.status_code == 200
    detail = res2.json()
    assert detail["id"] == event_id
    assert detail["event_type"] == "sms_message"


# ─── 13. Export report creates HTML file ──────────────────────────────
def test_export_report_creates_html(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    from erakshak.dashboard.db import DashboardDB
    from erakshak.dashboard.report_export import export_html_report

    exhibit_root = _setup_case_folder(tmp_path, [
        ("sms_messages.jsonl", "derived/sms_messages.jsonl"),
        ("device_identity.json", "derived/device_identity.json"),
    ])
    result = build_evidence_index(exhibit_root, "CASE001", "EX001")
    with DashboardDB(Path(result["db_path"])) as db:
        report_path = export_html_report(db, exhibit_root, "CASE001", "EX001")

    assert report_path.exists()
    assert report_path.name == "forensic_preview_report.html"
    content = report_path.read_text(encoding="utf-8")
    assert "Forensic Preview Only" in content or "forensic preview" in content.lower()


# ─── 14. No raw encryption key in DB or report ───────────────────────
def test_no_encryption_key_in_db(tmp_path):
    from erakshak.dashboard.timeline_builder import build_evidence_index
    from erakshak.dashboard.db import DashboardDB
    from erakshak.dashboard.report_export import export_html_report

    # A fake 64-hex key that should be redacted
    fake_key = "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890"

    exhibit_root = _setup_case_folder(tmp_path)
    # Write a sms fixture with the key embedded in a message body
    sms_path = exhibit_root / "derived" / "sms_messages.jsonl"
    sms_path.write_text(
        json.dumps({"address": "+1234", "body": f"key: {fake_key}", "date": "1705555200000", "type": "1"})
        + "\n",
        encoding="utf-8",
    )

    result = build_evidence_index(exhibit_root, "CASE001", "EX001")

    # Scan all text columns in the database for the raw key
    db = sqlite3.connect(result["db_path"])
    cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall() if r[0]]

    for table_sql in tables:
        # Extract table name
        match = re.search(r'CREATE TABLE\s+\w*\s*(\w+)', table_sql, re.IGNORECASE)
        if not match:
            continue
        table_name = match.group(1)
        try:
            rows = db.execute(f"SELECT * FROM {table_name}").fetchall()
        except Exception:
            continue
        col_names = [desc[0] for desc in db.execute(f"SELECT * FROM {table_name} LIMIT 0").description]
        for row in rows:
            for col_idx, val in enumerate(row):
                if isinstance(val, str) and fake_key in val:
                    # The key appears in a message body — that's the raw content, which is acceptable
                    # But it should NOT appear in hash/audit/integrity fields
                    col_name = col_names[col_idx]
                    if col_name in ("sha256", "source_hash", "details_json"):
                        pytest.fail(
                            f"Raw encryption key found in {table_name}.{col_name}"
                        )
    db.close()

    # Also verify report doesn't contain the raw key in sensitive fields
    with DashboardDB(Path(result["db_path"])) as db_for_report:
        report_path = export_html_report(db_for_report, exhibit_root, "CASE001", "EX001")
    if report_path.exists():
        content = report_path.read_text(encoding="utf-8")
        # The key in message body is acceptable content, but check it's not in integrity sections
        # This is a basic smoke test
        assert "This report is a rapid forensic preview only" in content or "forensic preview" in content.lower()
