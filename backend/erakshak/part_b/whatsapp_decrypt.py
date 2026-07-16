"""WhatsApp Backup Decryption Module for E-RAKSHAK.

Wraps the 'wa-crypt-tools' CLI tool (wadecrypt) to decrypt WhatsApp backups
using the captured or manually provided 64-character hex key.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def validate_hex_key(hex_key: str) -> str:
    """Accepts only 64 hex characters, returns lowercase.

    Never prints or logs the key. Raises ValueError if invalid.
    """
    if not isinstance(hex_key, str):
        raise ValueError("Key must be a string.")
    
    clean_key = hex_key.strip().lower()
    if not re.match(r"^[0-9a-f]{64}$", clean_key):
        raise ValueError("Invalid WhatsApp backup key format. Must be a 64-character hexadecimal string.")
    return clean_key


def key_metadata(hex_key: str) -> dict[str, Any]:
    """Generates non-sensitive metadata identification for a backup key."""
    validated = validate_hex_key(hex_key)
    # Use lowercase key for SHA-256 computation to ensure consistency
    key_hash = hashlib.sha256(validated.encode("utf-8")).hexdigest()
    return {
        "key_present": True,
        "key_type": "captured_64_hex",
        "key_length": 64,
        "key_sha256": key_hash,
    }


def is_sqlite_database(path: Path) -> bool:
    """Checks the magic bytes of a file to verify if it is a SQLite 3 database."""
    if not path.exists() or not path.is_file():
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        return header.startswith(b"SQLite format 3")
    except Exception:
        return False


def ensure_wadecrypt_available() -> str:
    """Ensures 'wadecrypt' is installed and returns its executable path."""
    exe_path = shutil.which("wadecrypt")
    if not exe_path:
        raise RuntimeError("wadecrypt not found. Install wa-crypt-tools with: pip install wa-crypt-tools")
    return exe_path


def redact_secret(text: str, secret: str) -> str:
    """Case-insensitively replaces occurrences of a secret with '<REDACTED_KEY>'."""
    if not text or not secret:
        return text
    # Avoid matching empty secret
    pattern = re.escape(secret)
    return re.sub(pattern, "<REDACTED_KEY>", text, flags=re.IGNORECASE)


def decrypt_with_wadecrypt(
    hex_key: str,
    encrypted_backup: Path,
    output_db: Path,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Invokes 'wadecrypt' CLI to decrypt an encrypted WhatsApp backup.

    Performs full redaction on command, stdout, and stderr to prevent secret leakage.
    """
    # 1. Validation
    validated_key = validate_hex_key(hex_key)
    
    if not encrypted_backup.exists():
        return {
            "status": "failed",
            "error": f"Encrypted backup file not found: {encrypted_backup}",
            "sqlite_verified": False,
        }
        
    # Create parent output directory if needed
    output_db.parent.mkdir(parents=True, exist_ok=True)
    
    # 2. Check wadecrypt executable
    try:
        wadecrypt_path = ensure_wadecrypt_available()
    except RuntimeError as e:
        return {
            "status": "failed",
            "error": str(e),
            "sqlite_verified": False,
        }

    # Redacted command template
    command_redacted = f"wadecrypt <REDACTED_KEY> {encrypted_backup} {output_db}"

    # Delete existing target first to prevent stale verification
    if output_db.exists():
        try:
            os.remove(output_db)
        except Exception:
            pass

    # 3. Subprocess execution
    try:
        result = subprocess.run(
            [wadecrypt_path, validated_key, str(encrypted_backup), str(output_db)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        
        # Redact secrets
        stdout_redacted = redact_secret(result.stdout, validated_key)
        stderr_redacted = redact_secret(result.stderr, validated_key)
        return_code = result.returncode

    except subprocess.TimeoutExpired as e:
        stdout_redacted = redact_secret(e.stdout or "", validated_key)
        stderr_redacted = f"Decryption timed out after {timeout_seconds}s. " + redact_secret(e.stderr or "", validated_key)
        return {
            "status": "failed",
            "return_code": -1,
            "stdout_redacted": stdout_redacted,
            "stderr_redacted": stderr_redacted,
            "command_redacted": command_redacted,
            "output_db": str(output_db),
            "sqlite_verified": False,
            "error": "TimeoutExpired",
        }
    except Exception as e:
        return {
            "status": "failed",
            "return_code": -2,
            "stdout_redacted": "",
            "stderr_redacted": str(e),
            "command_redacted": command_redacted,
            "output_db": str(output_db),
            "sqlite_verified": False,
            "error": str(e),
        }

    # 4. Result validation
    if not output_db.exists():
        return {
            "status": "failed",
            "return_code": return_code,
            "stdout_redacted": stdout_redacted,
            "stderr_redacted": stderr_redacted,
            "command_redacted": command_redacted,
            "output_db": str(output_db),
            "sqlite_verified": False,
            "error": "Output file was not created by wadecrypt.",
        }

    # Check if the decrypted file is a valid SQLite DB
    sqlite_ok = is_sqlite_database(output_db)
    
    if not sqlite_ok:
        return {
            "status": "failed",
            "return_code": return_code,
            "stdout_redacted": stdout_redacted,
            "stderr_redacted": stderr_redacted,
            "command_redacted": command_redacted,
            "output_db": str(output_db),
            "sqlite_verified": False,
            "error": "wrong_key_or_unsupported_backup",
        }

    return {
        "status": "success",
        "return_code": return_code,
        "stdout_redacted": stdout_redacted,
        "stderr_redacted": stderr_redacted,
        "command_redacted": command_redacted,
        "output_db": str(output_db),
        "sqlite_verified": True,
    }
