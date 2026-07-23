"""Signal Android database parser.

This parser is intentionally conservative. Signal Android databases are usually
SQLCipher-encrypted; when a pulled DB is encrypted or uses an unknown schema,
the parser reports ``unsupported``. If a decrypted/plain SQLite database is
provided from an authorized root/import lane, common tables are normalized.
"""

from __future__ import annotations

import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SignalParser:
    """Parser for an acquired Signal SQLite database."""

    def __init__(self, db_path: Path, db_key: str | None = None):
        self.db_path = db_path
        self.db_key = db_key
        self.supported = False
        self.tables: list[str] = []
        self.errors: list[str] = []
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "SignalParser":
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def open(self) -> None:
        if not self.db_path.exists():
            self.errors.append(f"Database not found: {self.db_path}")
            return
        try:
            self._conn = self._connect()
            if not self.db_key:
                self._conn.row_factory = sqlite3.Row
            self._detect_schema()
        except Exception as exc:
            self.errors.append(f"SQLite connection error: {exc}. Database may be SQLCipher-encrypted.")
            self._conn = None

    def _connect(self) -> Any:
        """Open the DB using SQLCipher when a key is supplied, else sqlite3."""
        if not self.db_key:
            return sqlite3.connect(f"{self.db_path.absolute().as_uri()}?mode=ro", uri=True)

        try:
            from sqlcipher3 import dbapi2 as sqlcipher_dbapi
        except ImportError:
            try:
                from pysqlcipher3 import dbapi2 as sqlcipher_dbapi  # type: ignore[no-redef]
            except ImportError as exc:
                raise sqlite3.DatabaseError(
                    "SQLCipher support is not installed. Install sqlcipher3-wheels or pysqlcipher3."
                ) from exc

        conn = sqlcipher_dbapi.connect(str(self.db_path))
        conn.execute("PRAGMA cipher_default_kdf_iter = 1")
        conn.execute("PRAGMA cipher_default_page_size = 4096")
        key_expr = self._sqlcipher_key_expression(self.db_key)
        conn.execute(f"PRAGMA key = {key_expr}")
        conn.execute("PRAGMA cipher_compatibility = 3")
        conn.execute("PRAGMA kdf_iter = 1")
        conn.execute("PRAGMA cipher_page_size = 4096")
        conn.execute("SELECT count(*) FROM sqlite_master")
        return conn

    @staticmethod
    def _sqlcipher_key_expression(key: str) -> str:
        clean = key.strip()
        if clean.lower().startswith("raw:"):
            raw = clean[4:].strip()
            if re.fullmatch(r"[0-9a-fA-F]+", raw):
                return f"\"x'{raw.lower()}'\""
        return "'" + clean.replace("'", "''") + "'"

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _detect_schema(self) -> None:
        if not self._conn:
            return
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            self.tables = [row["name"] if hasattr(row, "keys") else row[0] for row in cur.fetchall()]
            if any(table in self.tables for table in ("sms", "mms", "thread", "recipient", "message")):
                self.supported = True
            else:
                self.errors.append("Unrecognized Signal schema: expected sms, mms, thread, recipient, or message tables.")
        except sqlite3.DatabaseError as exc:
            self.errors.append(f"Schema detection failed: {exc}")

    def parse_all(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "success" if self.supported else "unsupported",
            "db_path": str(self.db_path),
            "recipients": [],
            "threads": [],
            "messages": [],
            "warnings": [],
            "errors": self.errors.copy(),
        }
        if not self.supported or not self._conn:
            return result
        result["recipients"] = self._parse_recipients(result["warnings"])
        result["threads"] = self._parse_threads(result["warnings"])
        result["messages"] = self._parse_messages(result["warnings"], result["recipients"])
        return result

    def _columns(self, table: str) -> set[str]:
        if not self._conn:
            return set()
        cur = self._conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        names = set()
        for row in cur.fetchall():
            names.add(row["name"] if hasattr(row, "keys") else row[1])
        return names

    def _select_existing(self, table: str, candidates: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
        if not self._conn or table not in self.tables:
            return []
        columns = self._columns(table)
        selected = [col for col in candidates if col in columns]
        if not selected:
            return []
        cur = self._conn.cursor()
        cur.execute(f"SELECT {', '.join(selected)} FROM {table} LIMIT {limit}")
        column_names = [desc[0] for desc in cur.description]
        rows = []
        for row in cur.fetchall():
            if hasattr(row, "keys"):
                rows.append(dict(row))
            else:
                rows.append(dict(zip(column_names, row)))
        return rows

    def _parse_recipients(self, warnings: list[str]) -> list[dict[str, Any]]:
        try:
            return self._select_existing(
                "recipient",
                ("_id", "id", "uuid", "aci", "phone", "e164", "system_display_name", "profile_given_name", "profile_family_name", "group_id"),
                20000,
            )
        except sqlite3.DatabaseError as exc:
            warnings.append(f"Failed to parse recipients: {exc}")
            return []

    def _parse_threads(self, warnings: list[str]) -> list[dict[str, Any]]:
        try:
            return self._select_existing(
                "thread",
                ("_id", "id", "recipient_id", "date", "message_count", "snippet", "read", "archived"),
                20000,
            )
        except sqlite3.DatabaseError as exc:
            warnings.append(f"Failed to parse threads: {exc}")
            return []

    def _parse_messages(self, warnings: list[str], recipients: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        recipient_names = self._recipient_names(recipients)
        table_candidates = [table for table in ("message", "sms", "mms") if table in self.tables]
        for table in table_candidates:
            try:
                rows = self._select_existing(
                    table,
                    ("_id", "id", "thread_id", "recipient_id", "from_recipient_id", "date", "date_sent", "date_received", "body", "type", "read", "expires_in", "expire_started"),
                    50000,
                )
                for row in rows:
                    messages.append(self._normalize_message(row, recipient_names))
            except sqlite3.DatabaseError as exc:
                warnings.append(f"Failed to parse {table}: {exc}")
        return messages

    @staticmethod
    def _recipient_names(recipients: list[dict[str, Any]]) -> dict[Any, str]:
        names: dict[Any, str] = {}
        for recipient in recipients:
            recipient_id = recipient.get("_id") or recipient.get("id")
            given = recipient.get("profile_given_name") or recipient.get("system_display_name")
            family = recipient.get("profile_family_name")
            name = " ".join(part for part in (given, family) if part).strip()
            contact = name or recipient.get("phone") or recipient.get("e164") or recipient.get("uuid") or recipient.get("aci")
            if recipient_id is not None and contact:
                names[recipient_id] = str(contact)
        return names

    @staticmethod
    def _normalize_message(row: dict[str, Any], recipient_names: dict[Any, str]) -> dict[str, Any]:
        contact_id = row.get("from_recipient_id") or row.get("recipient_id")
        sent_by_phone, received_by_phone = SignalParser._message_direction(row.get("type"))
        sent_time = SignalParser._timestamp_to_display(row.get("date_sent"))
        received_time = SignalParser._timestamp_to_display(row.get("date_received"))
        date = sent_time or received_time or SignalParser._timestamp_to_display(row.get("date"))
        return {
            "date": date,
            "contact_name": recipient_names.get(contact_id, "Unknown"),
            "received": received_by_phone,
            "sent": sent_by_phone,
            "message": row.get("body") or "",
        }

    @staticmethod
    def _message_direction(message_type: Any) -> tuple[bool, bool]:
        try:
            base_type = int(message_type) & 0xFF
        except (TypeError, ValueError):
            return False, False
        if base_type in {23, 24, 25}:
            return True, False
        if base_type in {20, 21, 22}:
            return False, True
        return False, False

    @staticmethod
    def _timestamp_to_display(value: Any) -> str | None:
        if value in (None, ""):
            return None
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return None
        if timestamp <= 0:
            return None
        seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (OSError, OverflowError, ValueError):
            return None
