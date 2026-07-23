import sqlite3
import json
from pathlib import Path

import pytest

from erakshak.part_b.telegram_parser import TelegramParser
from erakshak.part_b.telegram_pipeline import run_telegram_pipeline
from erakshak.adb.client import ADBClient
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger


@pytest.fixture
def synthetic_telegram_db(tmp_path: Path) -> Path:
    """Create a synthetic cache4.db for testing the parser."""
    db_path = tmp_path / "cache4.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create mock schema
    cursor.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, name TEXT, status TEXT, data BLOB)")
    cursor.execute("CREATE TABLE messages (mid INTEGER PRIMARY KEY, uid INTEGER, read_state INTEGER, date INTEGER, dialog_id INTEGER, data BLOB)")
    cursor.execute("CREATE TABLE dialogs (did INTEGER PRIMARY KEY, date INTEGER, unread_count INTEGER, last_mid INTEGER)")
    
    # Insert mock data
    cursor.execute("INSERT INTO users (uid, name, status) VALUES (1, 'Alice', 'online')")
    cursor.execute("INSERT INTO users (uid, name, status) VALUES (2, 'Bob', 'offline')")
    
    cursor.execute("INSERT INTO messages (mid, uid, read_state, date, dialog_id) VALUES (101, 1, 1, 1600000000, 10)")
    cursor.execute("INSERT INTO messages (mid, uid, read_state, date, dialog_id) VALUES (102, 2, 0, 1600000005, 10)")
    
    cursor.execute("INSERT INTO dialogs (did, date, unread_count, last_mid) VALUES (10, 1600000005, 1, 102)")
    
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def unsupported_db(tmp_path: Path) -> Path:
    """Create a DB with an unrecognized schema."""
    db_path = tmp_path / "unsupported.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE weird_table (id INTEGER PRIMARY KEY, stuff TEXT)")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def synthetic_telegram_db_degraded(tmp_path: Path) -> Path:
    """Create a DB with some expected columns missing to test graceful degradation."""
    db_path = tmp_path / "cache4_degraded.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # missing 'status' and 'name' in users, missing 'dialog_id' in messages
    cursor.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, weird_col TEXT)")
    cursor.execute("CREATE TABLE messages (mid INTEGER PRIMARY KEY, uid INTEGER, read_state INTEGER, date INTEGER)")
    cursor.execute("CREATE TABLE dialogs (did INTEGER PRIMARY KEY, date INTEGER)")
    
    cursor.execute("INSERT INTO users (uid, weird_col) VALUES (1, 'Unknown')")
    cursor.execute("INSERT INTO messages (mid, uid, read_state, date) VALUES (101, 1, 1, 1600000000)")
    cursor.execute("INSERT INTO dialogs (did, date) VALUES (10, 1600000005)")
    
    conn.commit()
    conn.close()
    return db_path


def test_telegram_parser_supported(synthetic_telegram_db: Path):
    with TelegramParser(synthetic_telegram_db) as parser:
        assert parser.supported is True
        
        data = parser.parse_all()
        assert data["status"] == "success"
        
        users = data["users"]
        assert len(users) == 2
        assert users[0]["name"] == "Alice"
        assert users[1]["name"] == "Bob"
        
        messages = data["messages"]
        assert len(messages) == 2
        assert messages[0]["mid"] == 101
        
        dialogs = data["dialogs"]
        assert len(dialogs) == 1
        assert dialogs[0]["did"] == 10


def test_telegram_parser_degraded(synthetic_telegram_db_degraded: Path):
    with TelegramParser(synthetic_telegram_db_degraded) as parser:
        assert parser.supported is True
        
        data = parser.parse_all()
        assert data["status"] == "success"
        
        # Name should be gracefully missing/empty since column was missing
        users = data["users"]
        assert len(users) == 1
        assert users[0].get("uid") == 1
        assert users[0].get("name") == ""  # Defaults to empty string
        
        messages = data["messages"]
        assert len(messages) == 1
        assert messages[0].get("mid") == 101
        assert "dialog_id" not in messages[0]  # Was missing in schema
        
        dialogs = data["dialogs"]
        assert len(dialogs) == 1
        assert dialogs[0].get("did") == 10


def test_telegram_parser_unsupported(unsupported_db: Path):
    with TelegramParser(unsupported_db) as parser:
        assert parser.supported is False
        data = parser.parse_all()
        assert data["status"] == "unsupported"
        assert "Unrecognized schema" in parser.errors[0]


def test_telegram_pipeline_no_packages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Setup mock infrastructure
    case_folder = CaseFolder(tmp_path, "CASE", "EXHIBIT")
    case_folder.create()
    audit = AuditLogger(tmp_path / "audit.jsonl", "CASE", "EXHIBIT")
    manifest = ManifestWriter(tmp_path / "manifest.jsonl", tmp_path / "hashes.txt", "CASE", "EXHIBIT")
    adb = ADBClient("mock_serial", audit, "adb")
    
    # Mock acquire_telegram_databases to return empty
    def mock_acquire(*args, **kwargs):
        return {
            "packages_found": [],
            "packages_not_found": ["org.telegram.messenger"],
            "db_results": {},
            "warnings": [],
            "errors": []
        }
    monkeypatch.setattr("erakshak.part_b.telegram_pipeline.acquire_telegram_databases", mock_acquire)
    
    summary = run_telegram_pipeline(adb, case_folder, manifest, audit)
    assert len(summary["acquisition"]["packages_found"]) == 0
    assert summary["parsing"]["total_users"] == 0


def test_telegram_pipeline_with_db(tmp_path: Path, synthetic_telegram_db: Path, monkeypatch: pytest.MonkeyPatch):
    # Setup mock infrastructure
    case_folder = CaseFolder(tmp_path, "CASE", "EXHIBIT")
    case_folder.create()
    audit = AuditLogger(tmp_path / "audit.jsonl", "CASE", "EXHIBIT")
    manifest = ManifestWriter(tmp_path / "manifest.jsonl", tmp_path / "hashes.txt", "CASE", "EXHIBIT")
    adb = ADBClient("mock_serial", audit, "adb")
    
    # Place synthetic DB in the expected raw acquisition folder
    pkg_dir = case_folder.raw_apps_telegram_dir / "org.telegram.messenger"
    pkg_dir.mkdir(parents=True)
    
    target_db = pkg_dir / "cache4.db"
    # Copy synthetic db
    target_db.write_bytes(synthetic_telegram_db.read_bytes())
    
    # Mock acquire_telegram_databases to return success
    def mock_acquire(*args, **kwargs):
        return {
            "packages_found": ["org.telegram.messenger"],
            "packages_not_found": [],
            "db_results": {},
            "warnings": [],
            "errors": []
        }
    monkeypatch.setattr("erakshak.part_b.telegram_pipeline.acquire_telegram_databases", mock_acquire)
    
    summary = run_telegram_pipeline(adb, case_folder, manifest, audit)
    
    assert len(summary["parsing"]["parsed_dbs"]) == 1
    assert summary["parsing"]["total_users"] == 2
    assert summary["parsing"]["total_messages"] == 2
    
    # Check JSONL output
    derived_dir = case_folder.derived_dir / "apps" / "telegram" / "org.telegram.messenger"
    assert (derived_dir / "cache4_users.jsonl").exists()
    assert (derived_dir / "cache4_messages.jsonl").exists()
    assert (derived_dir / "cache4_dialogs.jsonl").exists()
