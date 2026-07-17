"""Unit tests for WhatsApp Plaintext Parsing/Export Pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from erakshak.part_b.whatsapp_exporter_runner import (
    find_wtsexporter,
    is_sqlite_database,
    locate_whatsapp_artifacts,
    run_whatsapp_chat_exporter,
)
from erakshak.part_b.whatsapp_parse_pipeline import parse_decrypted_whatsapp


# ── 1. find_wtsexporter finds bundled executable ────────────────────────────
@patch("os.path.exists")
def test_find_wtsexporter_bundled(mock_exists: MagicMock) -> None:
    # Match on first candidate
    mock_exists.side_effect = lambda p: p == "platform-tools/tools/whatsapp-chat-exporter/wtsexporter.exe"
    
    found = find_wtsexporter()
    assert "wtsexporter.exe" in found
    assert Path(found).is_absolute()


# ── 2. find_wtsexporter falls back to PATH ──────────────────────────────────
@patch("os.path.exists")
@patch("shutil.which")
def test_find_wtsexporter_path(mock_which: MagicMock, mock_exists: MagicMock) -> None:
    mock_exists.return_value = False
    mock_which.return_value = "/usr/local/bin/wtsexporter"
    
    found = find_wtsexporter()
    assert found == "/usr/local/bin/wtsexporter"


# ── 3. missing wtsexporter raises clear RuntimeError ────────────────────────
@patch("os.path.exists")
@patch("shutil.which")
def test_find_wtsexporter_missing(mock_which: MagicMock, mock_exists: MagicMock) -> None:
    mock_exists.return_value = False
    mock_which.return_value = None
    
    with pytest.raises(RuntimeError, match="wtsexporter not found. Install with: pip install whatsapp-chat-exporter"):
        find_wtsexporter()


# ── 4. is_sqlite_database returns true for SQLite header ────────────────────
def test_is_sqlite_database_true(tmp_path: Path) -> None:
    db_file = tmp_path / "msgstore.db"
    db_file.write_bytes(b"SQLite format 3\x00extra_header_bytes")
    assert is_sqlite_database(db_file) is True


# ── 5. is_sqlite_database returns false for encrypted/random file ───────────
def test_is_sqlite_database_false(tmp_path: Path) -> None:
    db_file = tmp_path / "msgstore.db"
    db_file.write_bytes(b"ENC_BACKUP_BYTES_NOT_SQLITE")
    assert is_sqlite_database(db_file) is False


# ── 6. locate_whatsapp_artifacts finds msgstore.db ──────────────────────────
def test_locate_whatsapp_artifacts_msgstore_only(tmp_path: Path) -> None:
    case_folder = tmp_path / "CASE001" / "EXHIBIT001"
    msgstore_path = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "msgstore.db"
    msgstore_path.parent.mkdir(parents=True, exist_ok=True)
    msgstore_path.write_bytes(b"SQLite format 3\x00hdr")
    
    artifacts = locate_whatsapp_artifacts(case_folder)
    assert artifacts["msgstore_db"] == msgstore_path
    assert artifacts["wa_db"] is None
    assert artifacts["media_dir"] is None


# ── 7. locate_whatsapp_artifacts finds optional wa.db and media_dir ────────
def test_locate_whatsapp_artifacts_optional(tmp_path: Path) -> None:
    case_folder = tmp_path / "CASE001" / "EXHIBIT001"
    
    msgstore_path = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "msgstore.db"
    msgstore_path.parent.mkdir(parents=True, exist_ok=True)
    msgstore_path.write_bytes(b"SQLite format 3\x00hdr")
    
    wa_db_path = case_folder / "raw" / "apps" / "whatsapp" / "wa.db"
    wa_db_path.parent.mkdir(parents=True, exist_ok=True)
    wa_db_path.touch()
    
    media_path = case_folder / "processed" / "apps" / "whatsapp" / "media"
    media_path.mkdir(parents=True, exist_ok=True)
    
    artifacts = locate_whatsapp_artifacts(case_folder)
    assert artifacts["msgstore_db"] == msgstore_path
    assert artifacts["wa_db"] == wa_db_path
    assert artifacts["media_dir"] == media_path


# ── 8. run_whatsapp_chat_exporter builds correct argv list ──────────────────
# ── 9. run_whatsapp_chat_exporter uses shell=False ──────────────────────────
@patch("erakshak.part_b.whatsapp_exporter_runner.find_wtsexporter")
@patch("subprocess.run")
def test_run_whatsapp_chat_exporter_argv(mock_run: MagicMock, mock_find: MagicMock, tmp_path: Path) -> None:
    mock_find.return_value = "/bin/wtsexporter"
    
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "wtsexporter ran successfully"
    mock_proc.stderr = ""
    mock_run.return_value = mock_proc
    
    case_folder = tmp_path / "CASE001" / "EXHIBIT001"
    msgstore_path = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "msgstore.db"
    msgstore_path.parent.mkdir(parents=True, exist_ok=True)
    msgstore_path.write_bytes(b"SQLite format 3\x00hdr")
    
    # Add optional wa.db
    wa_db_path = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "wa.db"
    wa_db_path.touch()
    
    vcard_file = tmp_path / "contacts.vcf"
    vcard_file.touch()
    
    res = run_whatsapp_chat_exporter(
        case_id="CASE001",
        exhibit_id="EXHIBIT001",
        output_root=tmp_path,
        wa_db=wa_db_path,
        vcard_path=vcard_file,
        time_offset=3,
        filter_date="> 2026-07-10",
        filter_date_format="%Y-%m-%d"
    )
    
    assert res["status"] == "success"
    mock_run.assert_called_once()
    
    call_args, call_kwargs = mock_run.call_args
    argv = call_args[0]
    
    # Check that shell=False
    assert call_kwargs.get("shell") is not True
    
    # Check argv components
    assert argv[0] == "/bin/wtsexporter"
    assert "-a" in argv
    assert "-d" in argv
    assert str(msgstore_path) in argv
    assert "-w" in argv
    assert str(wa_db_path) in argv
    assert "-m" in argv
    # Check default media_temp folder path is used when media_dir is None
    expected_media = case_folder / "derived" / "whatsapp_exporter" / "media_temp"
    assert str(expected_media) in argv
    assert "--pretty-print-json" in argv
    assert "--enrich-from-vcards" in argv
    assert str(vcard_file) in argv
    assert "--time-offset" in argv
    assert "3" in argv
    assert "--date" in argv
    assert "> 2026-07-10" in argv
    assert "--date-format" in argv
    assert "%Y-%m-%d" in argv



# ── 10. parse pipeline writes audit start/completed events ──────────────────
# ── 11. parse pipeline creates whatsapp_preview_summary.json ────────────────
# ── 12. parse pipeline does not mention encryption key anywhere ──────────────
@patch("erakshak.part_b.whatsapp_exporter_runner.find_wtsexporter")
@patch("subprocess.run")
def test_whatsapp_parse_pipeline(mock_run: MagicMock, mock_find: MagicMock, tmp_path: Path) -> None:
    mock_find.return_value = "/bin/wtsexporter"
    
    # Mock exporter successful run
    def side_effect(argv, *args, **kwargs):
        html_dir = Path(argv[argv.index("-o") + 1])
        html_dir.mkdir(parents=True, exist_ok=True)
        (html_dir / "index.html").write_text("<html>Chats</html>")
        (html_dir / "916352151167-Darsh-Sharda-LNMIIT.html").write_text("<html>Darsh</html>")
        
        json_path = Path(argv[argv.index("-j") + 1])
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({
            "12345678@s.whatsapp.net": {
                "name": "Alice",
                "messages": [
                    {"sender": "Alice", "text": "Hello"},
                    {"sender": "Me", "text": "Hi"}
                ]
            }
        }))
        
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "wtsexporter completed"
        mock_proc.stderr = ""
        return mock_proc
        
    mock_run.side_effect = side_effect
    
    case_folder = tmp_path / "CASE001" / "EXHIBIT001"
    msgstore_path = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "msgstore.db"
    msgstore_path.parent.mkdir(parents=True, exist_ok=True)
    msgstore_path.write_bytes(b"SQLite format 3\x00hdr")
    
    res = parse_decrypted_whatsapp(
        case_id="CASE001",
        exhibit_id="EXHIBIT001",
        output_root=tmp_path
    )
    
    assert res["status"] == "success"
    
    # Verify HTML files renaming
    html_dir = case_folder / "derived" / "whatsapp_exporter" / "html"
    assert (html_dir / "index.html").is_file()
    assert (html_dir / "Darsh-Sharda-LNMIIT.html").is_file()
    assert not (html_dir / "916352151167-Darsh-Sharda-LNMIIT.html").exists()
    
    # Verify whatsapp_preview_summary.json exists and has correct stats
    summary_path = case_folder / "derived" / "whatsapp_preview_summary.json"
    assert summary_path.is_file()
    summary_data = json.loads(summary_path.read_text())
    
    assert summary_data["chat_count"] == 1
    assert summary_data["message_count"] == 2
    assert summary_data["app"] == "WhatsApp"
    assert summary_data["parser"] == "Whatsapp-Chat-Exporter"
    
    # Check audit log events
    audit_file = case_folder / "acquisition" / "audit.jsonl"
    assert audit_file.is_file()
    audit_lines = [json.loads(line) for line in audit_file.read_text().splitlines()]
    
    actions = [e["action"] for e in audit_lines]
    assert "whatsapp_exporter_parse_started" in actions
    assert "whatsapp_exporter_parse_completed" in actions
    
    # 12. Pipeline does not mention encryption key anywhere
    for event in audit_lines:
        assert "key" not in event["action"]
        assert "key" not in str(event.get("details", ""))
        assert "crypt" not in str(event.get("details", ""))


@patch("erakshak.part_b.whatsapp_exporter_runner.find_wtsexporter")
@patch("subprocess.run")
def test_whatsapp_parse_pipeline_generates_vcard(mock_run: MagicMock, mock_find: MagicMock, tmp_path: Path) -> None:
    mock_find.return_value = "/bin/wtsexporter"
    
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "wtsexporter completed"
    mock_proc.stderr = ""
    mock_run.return_value = mock_proc
    
    case_folder = tmp_path / "CASE001" / "EXHIBIT001"
    msgstore_path = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "msgstore.db"
    msgstore_path.parent.mkdir(parents=True, exist_ok=True)
    msgstore_path.write_bytes(b"SQLite format 3\x00hdr")
    
    # Create derived contacts.jsonl
    contacts_jsonl = case_folder / "derived" / "contacts.jsonl"
    contacts_jsonl.parent.mkdir(parents=True, exist_ok=True)
    contacts_jsonl.write_text(
        json.dumps({"display_name": "Bob", "phone": "+919876543210"}) + "\n" +
        json.dumps({"display_name": "Alka Bhabhi", "phone_number": "0987654321"}) + "\n",
        encoding="utf-8"
    )
    
    res = parse_decrypted_whatsapp(
        case_id="CASE001",
        exhibit_id="EXHIBIT001",
        output_root=tmp_path
    )
    
    assert res["status"] == "success"
    mock_run.assert_called_once()
    
    call_args, call_kwargs = mock_run.call_args
    argv = call_args[0]
    
    # Check that generated contacts.vcf is passed
    vcard_idx = argv.index("--enrich-from-vcards")
    generated_vcf = argv[vcard_idx + 1]
    assert "contacts.vcf" in generated_vcf
    assert Path(generated_vcf).is_file()
    
    # Check default country code is passed
    cc_idx = argv.index("--default-country-code")
    assert argv[cc_idx + 1] == "91"
    
    # Read the generated vCard and verify contacts
    vcard_content = Path(generated_vcf).read_text(encoding="utf-8")
    assert "FN:Bob" in vcard_content
    assert "TEL;TYPE=CELL:+919876543210" in vcard_content
    assert "FN:Alka Bhabhi" in vcard_content
    assert "TEL;TYPE=CELL:0987654321" in vcard_content

