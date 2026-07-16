"""Unit tests for WhatsApp Part B Key Capture and Decryption Pipeline."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from erakshak.part_b.whatsapp_decrypt import (
    validate_hex_key,
    key_metadata,
    is_sqlite_database,
    redact_secret,
    decrypt_with_wadecrypt,
    ensure_wadecrypt_available,
)
from erakshak.part_b.whatsapp_pipeline import run_whatsapp_key_capture_and_decrypt


# ── 1. validate_hex_key accepts lowercase 64 hex ────────────────────────────
def test_validate_hex_key_lowercase() -> None:
    valid_key = "a" * 64
    assert validate_hex_key(valid_key) == valid_key


# ── 2. validate_hex_key accepts uppercase 64 hex and returns lowercase ───────
def test_validate_hex_key_uppercase() -> None:
    valid_key_upper = "A" * 64
    assert validate_hex_key(valid_key_upper) == "a" * 64


# ── 3. validate_hex_key rejects short keys ──────────────────────────────────
def test_validate_hex_key_short() -> None:
    short_key = "a" * 63
    with pytest.raises(ValueError, match="Must be a 64-character hexadecimal string"):
        validate_hex_key(short_key)


# ── 4. validate_hex_key rejects non-hex keys ────────────────────────────────
def test_validate_hex_key_non_hex() -> None:
    non_hex = "g" * 64
    with pytest.raises(ValueError, match="Must be a 64-character hexadecimal string"):
        validate_hex_key(non_hex)


# ── 5. key_metadata does not expose raw key ─────────────────────────────────
def test_key_metadata_no_raw_key() -> None:
    key = "a" * 64
    meta = key_metadata(key)
    # Ensure raw key is not present in values (except length/metadata properties)
    for k, v in meta.items():
        if k == "key_length":
            assert v == 64
        elif k == "key_present":
            assert v is True
        elif k == "key_type":
            assert v == "captured_64_hex"
        elif k == "key_sha256":
            assert len(v) == 64
        else:
            assert v != key


# ── 6. redact_secret removes key from stdout/stderr ─────────────────────────
def test_redact_secret() -> None:
    key = "abcdef0123456789" * 4
    stdout = f"Error: key {key} was invalid."
    stderr = f"failed to use {key.upper()} key."
    
    assert redact_secret(stdout, key) == "Error: key <REDACTED_KEY> was invalid."
    assert redact_secret(stderr, key) == "failed to use <REDACTED_KEY> key."


# ── 7. is_sqlite_database returns true for file starting with b"SQLite format 3" 
def test_is_sqlite_database_true(tmp_path: Path) -> None:
    db_file = tmp_path / "msgstore.db"
    db_file.write_bytes(b"SQLite format 3\x00xyz")
    assert is_sqlite_database(db_file) is True


# ── 8. is_sqlite_database returns false for random bytes ────────────────────
def test_is_sqlite_database_false(tmp_path: Path) -> None:
    db_file = tmp_path / "msgstore.db"
    db_file.write_bytes(b"Not an sqlite file header")
    assert is_sqlite_database(db_file) is False


# ── 9. decrypt_with_wadecrypt builds subprocess argv without shell=True ─────
@patch("shutil.which")
@patch("subprocess.run")
def test_decrypt_with_wadecrypt_argv(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_which.return_value = "/usr/bin/wadecrypt"
    
    # Mock subprocess completion and output file creation
    def side_effect(*args, **kwargs):
        out_path = Path(args[0][3])
        out_path.write_bytes(b"SQLite format 3\x00test")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Decrypted successfully"
        mock_proc.stderr = ""
        return mock_proc

    mock_run.side_effect = side_effect

    key = "a" * 64
    backup = tmp_path / "msgstore.db.crypt15"
    backup.write_bytes(b"encrypted data")
    output = tmp_path / "msgstore.db"

    res = decrypt_with_wadecrypt(key, backup, output)
    
    assert res["status"] == "success"
    
    # Assert run called with list (shell=False or not specified, check argv)
    mock_run.assert_called_once()
    call_args, call_kwargs = mock_run.call_args
    argv = call_args[0]
    assert argv == ["/usr/bin/wadecrypt", key, str(backup), str(output)]
    assert call_kwargs.get("shell") is not True


# ── 10. decrypt_with_wadecrypt redacts key in command/stdout/stderr ──────────
@patch("shutil.which")
@patch("subprocess.run")
def test_decrypt_with_wadecrypt_redacted(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_which.return_value = "/usr/bin/wadecrypt"
    key = "b" * 64
    
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = f"Command failed using key {key}"
    mock_proc.stderr = f"wadecrypt: error for key {key.upper()}"
    mock_run.return_value = mock_proc

    backup = tmp_path / "msgstore.db.crypt15"
    backup.write_bytes(b"encrypted data")
    output = tmp_path / "msgstore.db"

    res = decrypt_with_wadecrypt(key, backup, output)
    
    assert res["status"] == "failed"
    assert key not in res["stdout_redacted"]
    assert key.upper() not in res["stderr_redacted"]
    assert key not in res["command_redacted"]
    assert "<REDACTED_KEY>" in res["stdout_redacted"]
    assert "<REDACTED_KEY>" in res["stderr_redacted"]
    assert "<REDACTED_KEY>" in res["command_redacted"]


# ── 11–13. Pipeline writes key_metadata, audit.jsonl (redacted), and manifest 
@patch("shutil.which")
@patch("subprocess.run")
@patch("erakshak.part_b.whatsapp_pipeline.capture_whatsapp_backup_key")
def test_whatsapp_pipeline(
    mock_capture: MagicMock,
    mock_run: MagicMock,
    mock_which: MagicMock,
    tmp_path: Path
) -> None:
    mock_which.return_value = "/usr/bin/wadecrypt"
    key = "c" * 64
    mock_capture.return_value = key

    # Mock subprocess completion and SQLite output file creation
    def side_effect(*args, **kwargs):
        out_path = Path(args[0][3])
        out_path.write_bytes(b"SQLite format 3\x00decrypted")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Decrypted successfully"
        mock_proc.stderr = ""
        return mock_proc

    mock_run.side_effect = side_effect

    backup = tmp_path / "msgstore.db.crypt15"
    backup.write_bytes(b"encrypted backup bytes")

    output_dir = tmp_path / "cases"

    res = run_whatsapp_key_capture_and_decrypt(
        case_id="CASE001",
        exhibit_id="EX001",
        encrypted_backup_path=backup,
        output_root=output_dir,
    )

    assert res["status"] == "success"
    exhibit_path = output_dir / "CASE001" / "EX001"

    # 11. Pipeline writes key_metadata.json but not raw key
    meta_file = exhibit_path / "raw" / "apps" / "whatsapp" / "encrypted" / "key_metadata.json"
    assert meta_file.exists()
    meta_content = json.loads(meta_file.read_text())
    assert meta_content["key_present"] is True
    # Verify no raw key is in the metadata file
    assert key not in meta_content.values()

    # 12. Pipeline writes audit.jsonl with redacted command
    audit_file = exhibit_path / "acquisition" / "audit.jsonl"
    assert audit_file.exists()
    audit_lines = [json.loads(line) for line in audit_file.read_text().splitlines()]
    
    # Assert at least one wadecrypt_invoked event with redacted command
    invoked_events = [e for e in audit_lines if e["action"] == "wadecrypt_invoked"]
    assert len(invoked_events) == 1
    details = invoked_events[0]["details"]
    assert "<REDACTED_KEY>" in details["command_redacted"]
    assert key not in details["command_redacted"]

    # 13. Pipeline writes manifest records
    manifest_file = exhibit_path / "acquisition" / "acquisition_manifest.jsonl"
    assert manifest_file.exists()
    manifest_lines = [json.loads(line) for line in manifest_file.read_text().splitlines()]
    classes = [m["artifact_class"] for m in manifest_lines]
    assert "whatsapp_encrypted_backup" in classes
    assert "whatsapp_key_metadata" in classes
    assert "whatsapp_decrypted_msgstore" in classes


# ── 14. failed wadecrypt returns structured failure ─────────────────────────
@patch("shutil.which")
@patch("subprocess.run")
def test_failed_wadecrypt(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_which.return_value = "/usr/bin/wadecrypt"
    key = "d" * 64
    
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = "failed"
    mock_proc.stderr = "invalid key"
    mock_run.return_value = mock_proc

    backup = tmp_path / "msgstore.db.crypt15"
    backup.write_bytes(b"encrypted backup bytes")
    output = tmp_path / "msgstore.db"

    res = decrypt_with_wadecrypt(key, backup, output)
    assert res["status"] == "failed"
    assert res["sqlite_verified"] is False
    assert res["error"] == "Output file was not created by wadecrypt."
