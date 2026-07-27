"""Pure-Python SQLCipher 3 decryptor for Signal Android databases.

Signal Android uses SQLCipher 3 with the following configuration:
  - Raw key: 32 bytes (64 hex chars) — no PBKDF2, no salt derivation
  - Page size: 4096 bytes
  - KDF iterations: 1 (effectively none; raw key mode)
  - Cipher: AES-256-CBC
  - HMAC: HMAC-SHA1 (32 bytes at end of every page)
  - IV: first 16 bytes of cipher payload on each page
  - Page 1: first 16 bytes are the SQLCipher salt (not part of cipher payload)

This module does NOT use sqlcipher3/pysqlcipher3.
It only requires pycryptodome (already installed in the E-RAKSHAK environment).

Reference:
  https://www.zetetic.net/sqlcipher/sqlcipher-api/
  SQLCipher 3 default settings
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from pathlib import Path
from typing import Optional

SQLCIPHER3_PAGE_SIZE = 4096
SQLCIPHER3_HMAC_SIZE = 32   # HMAC-SHA1 padded to 32 bytes (20 + 12 zeros)
SQLCIPHER3_IV_SIZE   = 16   # AES-CBC IV
SQLCIPHER3_SALT_SIZE = 16   # Salt in page 1 header
# Reserved bytes per page = IV(16) + HMAC(32) = 48 bytes at end of each page
SQLCIPHER3_RESERVED  = SQLCIPHER3_IV_SIZE + SQLCIPHER3_HMAC_SIZE
SQLITE_HEADER = b"SQLite format 3\x00"


def _derive_keys(raw_key_hex: str, salt: bytes) -> tuple[bytes, bytes]:
    """Derive AES key and HMAC key from the raw Signal DB key.

    Signal with kdf_iter=1 uses:
        key_material = PBKDF2-HMAC-SHA1(passphrase=raw_key, salt=salt, iterations=1, dklen=64)
    Then:
        enc_key  = key_material[:32]
        hmac_key = PBKDF2-HMAC-SHA1(passphrase=key_material[32:], salt=salt, iterations=2, dklen=32)
    """
    raw_key = bytes.fromhex(raw_key_hex)
    # kdf_iter = 1 in SQLCipher 3
    key_material = hashlib.pbkdf2_hmac("sha1", raw_key, salt, 1, dklen=64)
    enc_key  = key_material[:32]
    hmac_key = hashlib.pbkdf2_hmac("sha1", key_material[32:], salt, 2, dklen=32)
    return enc_key, hmac_key


def _decrypt_page(enc_page: bytes, enc_key: bytes, page_number: int) -> Optional[bytes]:
    """Decrypt one SQLCipher 3 page.

    Page layout (each page = SQLCIPHER3_PAGE_SIZE bytes):
      [content_enc: PAGE_SIZE - RESERVED][IV: 16][HMAC: 32]

    For page 1, the first 16 bytes are the unencrypted salt, so:
      actual encrypted content starts at byte 16.

    Returns decrypted plaintext bytes (PAGE_SIZE) or None on failure.
    """
    try:
        from Crypto.Cipher import AES
    except ImportError:
        raise RuntimeError("pycryptodome is required: pip install pycryptodome")

    page_size = len(enc_page)
    reserved  = SQLCIPHER3_RESERVED

    # The ciphertext + reserved block layout:
    # [0 .. page_size-reserved-1] = encrypted content
    # [page_size-reserved .. page_size-reserved+IV_SIZE-1] = IV
    # [page_size-reserved+IV_SIZE .. page_size-1] = HMAC (32 bytes)

    content_end = page_size - reserved
    iv_start    = content_end
    iv          = enc_page[iv_start : iv_start + SQLCIPHER3_IV_SIZE]
    cipher_text = enc_page[:content_end]

    if page_number == 1:
        # First 16 bytes are the unencrypted salt header — skip them in decryption
        salt_part   = enc_page[:SQLCIPHER3_SALT_SIZE]
        cipher_text = enc_page[SQLCIPHER3_SALT_SIZE:content_end]
        iv          = enc_page[iv_start : iv_start + SQLCIPHER3_IV_SIZE]

    cipher = AES.new(enc_key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(cipher_text)

    if page_number == 1:
        # Reconstruct page 1: prepend the SQLite header (overwrite salt area)
        # The decrypted content starts after the salt in the original, so we prepend zeros
        # that will be replaced by the SQLite header we stitch in later.
        plaintext = (b"\x00" * SQLCIPHER3_SALT_SIZE) + plaintext

    return plaintext


def decrypt_signal_db(
    encrypted_db_path: Path,
    raw_key_hex: str,
    output_path: Path,
) -> dict:
    """Decrypt a SQLCipher 3 Signal database to a plain SQLite file.

    Parameters
    ----------
    encrypted_db_path:
        Path to the encrypted ``signal.db`` file.
    raw_key_hex:
        64-character hex string (the raw 32-byte AES key, as returned by
        ``extract_signal_db_key``). May be prefixed with ``raw:`` which
        will be stripped.
    output_path:
        Where to write the decrypted plain SQLite database.

    Returns
    -------
    dict
        Keys: ``status`` ("success" / "failed"), ``error`` (str), ``pages`` (int).
    """
    raw_key_hex = raw_key_hex.strip()
    if raw_key_hex.lower().startswith("raw:"):
        raw_key_hex = raw_key_hex[4:].strip()

    if len(raw_key_hex) != 64 or not all(c in "0123456789abcdefABCDEF" for c in raw_key_hex):
        return {"status": "failed", "error": f"Invalid key: expected 64 hex chars, got {len(raw_key_hex)}", "pages": 0}

    try:
        data = encrypted_db_path.read_bytes()
    except OSError as exc:
        return {"status": "failed", "error": f"Cannot read encrypted DB: {exc}", "pages": 0}

    if len(data) < SQLCIPHER3_PAGE_SIZE:
        return {"status": "failed", "error": "File too small to be a SQLCipher database", "pages": 0}

    # Salt is the first 16 bytes of the file
    salt = data[:SQLCIPHER3_SALT_SIZE]

    try:
        enc_key, _ = _derive_keys(raw_key_hex, salt)
    except Exception as exc:
        return {"status": "failed", "error": f"Key derivation failed: {exc}", "pages": 0}

    total_pages = len(data) // SQLCIPHER3_PAGE_SIZE
    decrypted_pages: list[bytes] = []

    for page_num in range(1, total_pages + 1):
        offset = (page_num - 1) * SQLCIPHER3_PAGE_SIZE
        enc_page = data[offset : offset + SQLCIPHER3_PAGE_SIZE]
        try:
            plain_page = _decrypt_page(enc_page, enc_key, page_num)
        except Exception as exc:
            return {"status": "failed", "error": f"Decryption failed on page {page_num}: {exc}", "pages": page_num - 1}
        if plain_page is None:
            return {"status": "failed", "error": f"Decryption returned None on page {page_num}", "pages": page_num - 1}
        decrypted_pages.append(plain_page)

    # Stitch the SQLite header into page 1
    # Plain SQLite page 1 starts with "SQLite format 3\x00" (16 bytes)
    # followed by page_size (2 bytes big-endian), etc.
    # We overwrite the first 100 bytes of the decrypted page 1 partially:
    # just the header magic + page size (bytes 16-17) from page 1 plaintext are already correct.
    if decrypted_pages:
        p1 = bytearray(decrypted_pages[0])
        # Overwrite the salt placeholder with the SQLite header
        p1[:len(SQLITE_HEADER)] = SQLITE_HEADER
        # Page size at offset 16 (big-endian uint16)
        struct.pack_into(">H", p1, 16, SQLCIPHER3_PAGE_SIZE)
        decrypted_pages[0] = bytes(p1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_path, "wb") as fh:
            for page in decrypted_pages:
                fh.write(page)
    except OSError as exc:
        return {"status": "failed", "error": f"Cannot write decrypted DB: {exc}", "pages": 0}

    # Quick validation: check SQLite magic
    try:
        import sqlite3
        conn = sqlite3.connect(f"{output_path.absolute().as_uri()}?mode=ro", uri=True)
        conn.execute("SELECT count(*) FROM sqlite_master")
        conn.close()
    except Exception as exc:
        return {"status": "failed", "error": f"Decrypted file failed SQLite validation: {exc}", "pages": total_pages}

    return {"status": "success", "error": "", "pages": total_pages}
