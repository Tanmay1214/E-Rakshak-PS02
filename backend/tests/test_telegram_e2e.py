import sqlite3
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erakshak.adb.client import ADBClient
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.part_b.telegram_pipeline import run_telegram_pipeline
from erakshak.case.hashing import hash_file
from erakshak.cli import build_parser

@pytest.fixture
def synthetic_telegram_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "cache4.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, name TEXT, status TEXT, data BLOB)")
    cursor.execute("CREATE TABLE messages (mid INTEGER PRIMARY KEY, uid INTEGER, read_state INTEGER, date INTEGER, dialog_id INTEGER, data BLOB)")
    cursor.execute("CREATE TABLE dialogs (did INTEGER PRIMARY KEY, date INTEGER, unread_count INTEGER, last_mid INTEGER)")
    cursor.execute("INSERT INTO users (uid, name, status) VALUES (1, 'Alice', 'online')")
    cursor.execute("INSERT INTO messages (mid, uid, read_state, date, dialog_id) VALUES (101, 1, 1, 1600000000, 10)")
    conn.commit()
    conn.close()
    return db_path

@pytest.fixture
def mock_adb(synthetic_telegram_db: Path) -> MagicMock:
    adb = MagicMock(spec=ADBClient)
    adb.serial = "mock_serial"
    
    # Mock shell output based on args
    def mock_shell(args, **kwargs):
        res = MagicMock()
        res.ok = True
        res.stdout = ""
        res.stderr = ""
        res.timed_out = False
        res.return_code = 0
        res.duration_ms = 100
        
        cmd = " ".join(args)
        if "pm list packages" in cmd:
            res.stdout = "package:org.telegram.messenger\n"
            return res
        if "ls -la" in cmd:
            if "cache4.db" in cmd:
                size = synthetic_telegram_db.stat().st_size
                res.stdout = f"-rw-rw---- 1 root root {size} 2021-01-01 12:00 cache4.db\n"
            elif "/sdcard/Telegram" in cmd:
                res.stdout = "-rw-rw---- 1 root root 100 2021-01-01 12:00 file.jpg\n"
            else:
                res.ok = False
                res.return_code = 1
                res.stderr = "No such file or directory"
        return res
        
    adb.shell.side_effect = mock_shell
    
    def mock_pull(remote_path, local_dest, **kwargs):
        res = MagicMock()
        res.timed_out = False
        res.return_code = 0
        res.duration_ms = 100
        res.stderr = ""
        if "cache4.db" in remote_path and "cache4.db-" not in remote_path:
            shutil.copy2(synthetic_telegram_db, local_dest)
            res.ok = True
            return res
        res.ok = False
        res.return_code = 1
        res.stderr = "File not found"
        return res
        
    adb.pull.side_effect = mock_pull
    return adb


def test_telegram_pipeline_e2e(tmp_path: Path, mock_adb: MagicMock, synthetic_telegram_db: Path):
    case_folder = CaseFolder(tmp_path, "CASE_E2E", "EX01")
    case_folder.create()
    audit = AuditLogger(tmp_path / "audit.jsonl", "CASE_E2E", "EX01")
    manifest = ManifestWriter(tmp_path / "manifest.jsonl", tmp_path / "hashes.txt", "CASE_E2E", "EX01")
    
    summary = run_telegram_pipeline(mock_adb, case_folder, manifest, audit)
    
    # Verify Acquisition
    acq = summary["acquisition"]
    assert "org.telegram.messenger" in acq["packages_found"]
    
    # Verify Raw Evidence Not Modified
    raw_db_path = case_folder.raw_apps_telegram_dir / "org.telegram.messenger" / "files_cache4.db"
    assert raw_db_path.exists()
    assert hash_file(raw_db_path) == hash_file(synthetic_telegram_db)
    
    # Verify Parsing
    pars = summary["parsing"]
    assert len(pars["parsed_dbs"]) == 1
    assert pars["total_users"] == 1
    assert pars["total_messages"] == 1
    
    # Verify output JSONL
    derived_dir = case_folder.derived_dir / "apps" / "telegram" / "org.telegram.messenger"
    assert (derived_dir / "files_cache4_users.jsonl").exists()
    assert (derived_dir / "files_cache4_messages.jsonl").exists()
    assert (derived_dir / "telegram_summary.json").parent.exists()
    
def test_telegram_cli_entrypoint(tmp_path: Path, mock_adb: MagicMock, monkeypatch: pytest.MonkeyPatch):
    parser = build_parser()
    args = parser.parse_args(["telegram-acquire", "--case", "CLI1", "--exhibit", "EX1", "--output", str(tmp_path)])
    
    # We must patch ADBClient initialization in cli.py and _resolve_serial
    monkeypatch.setattr("erakshak.cli.ADBClient", lambda *a, **k: mock_adb)
    monkeypatch.setattr("erakshak.cli._resolve_serial", lambda *a, **k: "mock_serial")
    
    # We want to catch sys.exit(0)
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)
        
    assert exc_info.value.code == 0
    assert (tmp_path / "CLI1" / "EX1" / "acquisition" / "audit.jsonl").exists()
