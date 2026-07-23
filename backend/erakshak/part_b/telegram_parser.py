"""Telegram Database Parser — Phase 2 & 3.

Parses acquired Telegram SQLite databases (e.g. ``cache4.db``) safely.
Uses read-only standard SQLite connections to automatically process WAL files
without altering the original evidence.

Dynamically detects supported tables (``users``, ``messages``, ``dialogs``).
Given Telegram's complex internal TDS (Telegram Data Structure) serialization,
this parser focuses on extracting standard SQLite columns reliably (metadata,
timestamps, IDs) and flags fully opaque/binary schemas as unsupported.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any


def _extract_text_from_blob(blob: bytes | str | None) -> str:
    if not blob:
        return ""
    if isinstance(blob, str):
        return blob
    if isinstance(blob, bytes):
        try:
            matches = re.findall(rb'[\x20-\x7e]{3,}', blob)
            cleaned = [
                m.decode('utf-8', errors='ignore').strip()
                for m in matches
                if len(m.decode('utf-8', errors='ignore').strip()) >= 3
                and not re.match(r'^[A-Za-z0-9_\`\^\~\|\+]{1,3}$', m.decode('utf-8', errors='ignore').strip())
            ]
            return " | ".join(cleaned) if cleaned else ""
        except Exception:
            return ""
    return ""


class TelegramParser:
    """Parser for an acquired Telegram SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.supported = False
        self.tables: list[str] = []
        self._conn: sqlite3.Connection | None = None
        self.errors: list[str] = []

    def __enter__(self) -> TelegramParser:
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def open(self) -> None:
        """Open a read-only connection to the database.
        
        Using URI mode ``?mode=ro`` ensures that SQLite will process the WAL file
        (if present alongside the DB) into the active view, but will not write
        any changes back to the filesystem (preventing forensic spoliation).
        """
        if not self.db_path.exists():
            self.errors.append(f"Database not found: {self.db_path}")
            return

        # Ensure absolute path for the URI
        db_uri = self.db_path.absolute().as_uri()
        try:
            # Connect in read-only mode
            self._conn = sqlite3.connect(f"{db_uri}?mode=ro", uri=True)
            self._conn.row_factory = sqlite3.Row
            self._detect_schema()
        except sqlite3.Error as e:
            self.errors.append(f"SQLite connection error: {e}")
            self._conn = None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _detect_schema(self) -> None:
        """Check for known Telegram tables."""
        if not self._conn:
            return

        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            self.tables = [row["name"] for row in cursor.fetchall()]

            # A basic Telegram cache4.db usually has users, messages or messages_v2
            if any(t in self.tables for t in ("users", "messages", "messages_v2", "dialogs")):
                self.supported = True
            else:
                self.supported = False
                self.errors.append("Unrecognized schema: Expected 'users', 'messages', 'messages_v2', or 'dialogs' tables.")
        except sqlite3.Error as e:
            self.errors.append(f"Schema detection failed: {e}")

    def parse_all(self) -> dict[str, Any]:
        """Extract all supported artifacts into a normalized structure."""
        result: dict[str, Any] = {
            "status": "success" if self.supported else "unsupported",
            "db_path": str(self.db_path),
            "users": [],
            "messages": [],
            "dialogs": [],
            "warnings": [],
            "errors": self.errors.copy(),
        }

        if not self.supported or not self._conn:
            return result

        result["users"] = self._parse_users(result["warnings"])
        result["messages"] = self._parse_messages(result["warnings"])
        result["dialogs"] = self._parse_dialogs(result["warnings"])

        return result

    def _parse_users(self, warnings: list[str]) -> list[dict[str, Any]]:
        if "users" not in self.tables or not self._conn:
            return []

        users = []
        try:
            cursor = self._conn.cursor()
            # The schema often includes 'uid', 'name', 'status', 'data' (blob)
            # We select * and extract what is safe to read.
            cursor.execute("SELECT * FROM users LIMIT 10000")
            for row in cursor.fetchall():
                row_dict = dict(row)
                user = {
                    "uid": row_dict.get("uid"),
                    "name": row_dict.get("name", ""),
                    "status": row_dict.get("status"),
                }
                
                # Try to decode name if it's stored as bytes or string
                if isinstance(user["name"], bytes):
                    try:
                        user["name"] = user["name"].decode("utf-8", errors="replace")
                    except Exception:
                        user["name"] = "<binary>"

                users.append(user)
        except sqlite3.Error as e:
            warnings.append(f"Failed to parse users: {e}")

        return users

    def _parse_messages(self, warnings: list[str]) -> list[dict[str, Any]]:
        msg_table = "messages_v2" if "messages_v2" in self.tables else ("messages" if "messages" in self.tables else None)
        if not msg_table or not self._conn:
            return []

        messages = []
        try:
            cursor = self._conn.cursor()
            cursor.execute(f"PRAGMA table_info({msg_table})")
            columns = {col["name"] for col in cursor.fetchall()}

            query_cols = []
            for col_name in ("mid", "uid", "read_state", "send_state", "date", "out", "dialog_id", "ttl", "reply_to_message_id", "data", "message"):
                if col_name in columns:
                    query_cols.append(col_name)

            if not query_cols:
                warnings.append(f"{msg_table} table exists but has no recognizable standard columns.")
                return []

            cursor.execute(f"SELECT {', '.join(query_cols)} FROM {msg_table} LIMIT 50000")
            for row in cursor.fetchall():
                row_dict = dict(row)
                raw_data = row_dict.pop("data", None)
                raw_msg = row_dict.pop("message", None)
                row_dict["text"] = _extract_text_from_blob(raw_data) or _extract_text_from_blob(raw_msg)
                messages.append(row_dict)
        except sqlite3.Error as e:
            warnings.append(f"Failed to parse messages: {e}")

        return messages

    def _parse_dialogs(self, warnings: list[str]) -> list[dict[str, Any]]:
        if "dialogs" not in self.tables or not self._conn:
            return []

        dialogs = []
        try:
            cursor = self._conn.cursor()
            cursor.execute("PRAGMA table_info(dialogs)")
            columns = {col["name"] for col in cursor.fetchall()}

            query_cols = []
            if "did" in columns: query_cols.append("did")
            if "date" in columns: query_cols.append("date")
            if "unread_count" in columns: query_cols.append("unread_count")
            if "last_mid" in columns: query_cols.append("last_mid")
            if "id" in columns: query_cols.append("id") # alternative to did

            if not query_cols:
                warnings.append("dialogs table exists but has no recognizable standard columns.")
                return []

            cursor.execute(f"SELECT {', '.join(query_cols)} FROM dialogs LIMIT 10000")
            for row in cursor.fetchall():
                row_dict = dict(row)
                dialogs.append(row_dict)
        except sqlite3.Error as e:
            warnings.append(f"Failed to parse dialogs: {e}")

        return dialogs
