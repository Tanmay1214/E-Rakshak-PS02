"""Signal pipeline tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erakshak.adb.client import ADBClient
from erakshak.case.audit import AuditLogger
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.cli import build_parser
from erakshak.part_b.signal_pipeline import run_signal_pipeline


@pytest.fixture
def signal_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "signal.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE recipient (_id INTEGER PRIMARY KEY, phone TEXT)")
    conn.execute("CREATE TABLE thread (_id INTEGER PRIMARY KEY, recipient_id INTEGER)")
    conn.execute("CREATE TABLE sms (_id INTEGER PRIMARY KEY, thread_id INTEGER, body TEXT)")
    conn.execute("INSERT INTO recipient (_id, phone) VALUES (1, '+1555')")
    conn.execute("INSERT INTO thread (_id, recipient_id) VALUES (10, 1)")
    conn.execute("INSERT INTO sms (_id, thread_id, body) VALUES (100, 10, 'msg')")
    conn.commit()
    conn.close()
    return db_path


def test_signal_pipeline_with_db(tmp_path: Path, signal_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case_folder = CaseFolder(tmp_path, "CASE", "EXHIBIT")
    case_folder.create()
    audit = AuditLogger(tmp_path / "audit.jsonl", "CASE", "EXHIBIT")
    manifest = ManifestWriter(tmp_path / "manifest.jsonl", tmp_path / "hashes.txt", "CASE", "EXHIBIT")
    adb = ADBClient("mock_serial", audit, "adb")

    pkg_dir = case_folder.raw_apps_signal_dir / "org.thoughtcrime.securesms"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "databases_signal.db").write_bytes(signal_db.read_bytes())

    def mock_acquire(*args, **kwargs):
        return {
            "packages_found": ["org.thoughtcrime.securesms"],
            "packages_not_found": [],
            "db_results": {},
            "warnings": [],
            "errors": [],
        }

    monkeypatch.setattr("erakshak.part_b.signal_pipeline.acquire_signal_databases", mock_acquire)
    summary = run_signal_pipeline(adb, case_folder, manifest, audit)

    assert len(summary["parsing"]["parsed_dbs"]) == 1
    assert summary["parsing"]["total_recipients"] == 1
    assert summary["parsing"]["total_threads"] == 1
    assert summary["parsing"]["total_messages"] == 1
    derived = case_folder.derived_dir / "apps" / "signal" / "org.thoughtcrime.securesms"
    assert (derived / "databases_signal_recipients.jsonl").exists()
    assert (derived / "databases_signal_threads.jsonl").exists()
    assert (derived / "databases_signal_messages.jsonl").exists()


def test_signal_cli_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["signal-acquire", "--case", "CLI1", "--exhibit", "EX1", "--output", str(tmp_path)])

    mock_adb = MagicMock(spec=ADBClient)
    mock_adb.serial = "mock_serial"
    monkeypatch.setattr("erakshak.cli.ADBClient", lambda *a, **k: mock_adb)
    monkeypatch.setattr("erakshak.cli._resolve_serial", lambda *a, **k: "mock_serial")
    monkeypatch.setattr(
        "erakshak.part_b.signal_pipeline.run_signal_pipeline",
        lambda *a, **k: {
            "acquisition": {"packages_found": [], "packages_not_found": ["org.thoughtcrime.securesms"], "warnings": [], "errors": []},
            "parsing": {"parsed_dbs": [], "unsupported_dbs": [], "total_recipients": 0, "total_threads": 0, "total_messages": 0, "warnings": [], "errors": []},
            "output_dir": str(tmp_path),
        },
    )

    with pytest.raises(SystemExit) as exc_info:
        args.func(args)
    assert exc_info.value.code == 0
    assert (tmp_path / "CLI1" / "EX1" / "acquisition" / "audit.jsonl").exists()


def test_signal_auto_key_flag_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["signal-acquire", "--case", "CLI2", "--exhibit", "EX2", "--output", str(tmp_path), "--signal-auto-key"])

    mock_adb = MagicMock(spec=ADBClient)
    mock_adb.serial = "mock_serial"
    captured: dict = {}
    monkeypatch.setattr("erakshak.cli.ADBClient", lambda *a, **k: mock_adb)
    monkeypatch.setattr("erakshak.cli._resolve_serial", lambda *a, **k: "mock_serial")

    def mock_pipeline(*args, **kwargs):
        captured.update(kwargs)
        return {
            "acquisition": {"packages_found": [], "packages_not_found": ["org.thoughtcrime.securesms"], "warnings": [], "errors": []},
            "parsing": {"parsed_dbs": [], "unsupported_dbs": [], "total_recipients": 0, "total_threads": 0, "total_messages": 0, "warnings": [], "errors": []},
            "key_extraction": {"attempted": False, "success": False, "error": ""},
            "output_dir": str(tmp_path),
        }

    monkeypatch.setattr("erakshak.part_b.signal_pipeline.run_signal_pipeline", mock_pipeline)

    with pytest.raises(SystemExit) as exc_info:
        args.func(args)
    assert exc_info.value.code == 0
    assert captured["auto_extract_key"] is True
