"""Tests for call_logs, sms, and contacts acquisition modules."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.adb.client import ADBClient, ADBResult
from erakshak.acquisition.call_logs import acquire_call_logs
from erakshak.acquisition.sms import acquire_sms
from erakshak.acquisition.contacts import acquire_contacts


@pytest.fixture
def mock_infrastructure(tmp_path: Path):
    """Fixture providing real/mock case directory structure."""
    # Build case folder tree in tmp_path
    case_folder = CaseFolder(str(tmp_path), "CASE001", "EXHIBIT001")
    case_folder.create()

    manifest_path = case_folder.acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = case_folder.hashes_dir / "sha256sums.txt"
    manifest = ManifestWriter(manifest_path, sha256sums_path, "CASE001", "EXHIBIT001")
    
    audit_path = case_folder.acquisition_dir / "audit.jsonl"
    audit = AuditLogger(audit_path, "CASE001", "EXHIBIT001")

    # Mock ADB client
    adb = MagicMock(spec=ADBClient)

    return adb, case_folder, manifest, audit


def test_acquire_call_logs_adb_success(mock_infrastructure):
    """Test call logs acquisition when ADB query succeeds."""
    adb, case_folder, manifest, audit = mock_infrastructure

    # Mock successful ADB shell output
    adb.shell.return_value = ADBResult(
        command=["content", "query", "--uri", "content://call_log/calls"],
        stdout="Row: 0 number=1234567890, type=1, date=1600000000000, duration=100, name=John\n",
        stderr="",
        return_code=0,
        started_at="2026-07-12T00:00:00Z",
        completed_at="2026-07-12T00:00:01Z",
        duration_ms=1000.0,
    )

    res = acquire_call_logs(adb, case_folder, manifest, audit)
    
    assert res["status"] == "acquired"
    assert res["call_count"] == 1
    assert res["source"] == "adb"
    
    # Verify files created
    assert (case_folder.raw_system_dir / "content_call_log.txt").exists()
    derived_file = case_folder.derived_dir / "call_logs.jsonl"
    assert derived_file.exists()
    
    # Check parsed records
    lines = derived_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["number"] == "1234567890"
    assert record["name"] == "John"


def test_acquire_call_logs_fallback_success(mock_infrastructure, tmp_path):
    """Test call logs acquisition falls back to collector file when ADB query fails."""
    adb, case_folder, manifest, audit = mock_infrastructure

    # Mock failed ADB shell output (e.g. permission denied/SecurityException)
    adb.shell.return_value = ADBResult(
        command=["content", "query", "--uri", "content://call_log/calls"],
        stdout="java.lang.SecurityException: Permission Denial\n",
        stderr="",
        return_code=1,
        started_at="2026-07-12T00:00:00Z",
        completed_at="2026-07-12T00:00:01Z",
        duration_ms=1000.0,
    )

    # Create collector folder and calls.jsonl export
    coll_dir = tmp_path / "collector_exports"
    coll_dir.mkdir()
    calls_file = coll_dir / "calls.jsonl"
    calls_file.write_text('{"number": "9876543210", "name": "Alice"}\n')

    res = acquire_call_logs(adb, case_folder, manifest, audit, collector_folder=str(coll_dir))
    
    assert res["status"] == "acquired_from_collector"
    assert res["call_count"] == 1
    assert res["source"] == "collector"
    
    # Verify files copied/created
    assert (case_folder.raw_collector_dir / "calls.jsonl").exists()
    assert (case_folder.derived_dir / "call_logs.jsonl").exists()
    
    # Check parsed records
    derived_file = case_folder.derived_dir / "call_logs.jsonl"
    record = json.loads(derived_file.read_text(encoding="utf-8").strip())
    assert record["number"] == "9876543210"


def test_acquire_call_logs_both_fail(mock_infrastructure):
    """Test call logs acquisition fails completely if both ADB and fallback fail."""
    adb, case_folder, manifest, audit = mock_infrastructure

    adb.shell.return_value = ADBResult(
        command=["content", "query", "--uri", "content://call_log/calls"],
        stdout="SecurityException\n",
        stderr="",
        return_code=1,
        started_at="2026-07-12T00:00:00Z",
        completed_at="2026-07-12T00:00:01Z",
        duration_ms=1000.0,
    )

    res = acquire_call_logs(adb, case_folder, manifest, audit, collector_folder=None)
    
    assert res["status"] == "permission_denied"
    assert res["call_count"] == 0
    assert res["source"] == "none"


def test_acquire_sms_adb_success(mock_infrastructure):
    """Test SMS acquisition when ADB query succeeds."""
    adb, case_folder, manifest, audit = mock_infrastructure

    adb.shell.return_value = ADBResult(
        command=["content", "query", "--uri", "content://sms"],
        stdout="Row: 0 address=123, body=Hello, type=1\n",
        stderr="",
        return_code=0,
        started_at="2026-07-12T00:00:00Z",
        completed_at="2026-07-12T00:00:01Z",
        duration_ms=1000.0,
    )

    res = acquire_sms(adb, case_folder, manifest, audit)
    
    assert res["status"] == "acquired"
    assert res["message_count"] == 1
    assert res["source"] == "adb"
    
    assert (case_folder.raw_system_dir / "content_sms.txt").exists()
    assert (case_folder.derived_dir / "sms_messages.jsonl").exists()


def test_acquire_contacts_adb_success(mock_infrastructure):
    """Test contacts acquisition when ADB query succeeds."""
    adb, case_folder, manifest, audit = mock_infrastructure

    adb.shell.return_value = ADBResult(
        command=["content", "query", "--uri", "content://com.android.contacts/contacts"],
        stdout="Row: 0 display_name=Bob, starred=1\n",
        stderr="",
        return_code=0,
        started_at="2026-07-12T00:00:00Z",
        completed_at="2026-07-12T00:00:01Z",
        duration_ms=1000.0,
    )

    res = acquire_contacts(adb, case_folder, manifest, audit)
    
    assert res["status"] == "acquired"
    assert res["contact_count"] == 1
    assert res["source"] == "adb"
    
    assert (case_folder.raw_system_dir / "content_contacts.txt").exists()
    assert (case_folder.derived_dir / "contacts.jsonl").exists()
