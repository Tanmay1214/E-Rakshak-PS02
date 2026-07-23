"""Tests for Signal Android path registry and parser."""
from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from erakshak.part_b.signal_parser import SignalParser
from erakshak.part_b.signal_paths import (
    SIGNAL_PROFILES,
    SQLITE_SIDECAR_EXTENSIONS,
    SignalDbGroup,
    SignalProfile,
    get_profile,
)


def test_signal_db_group_immutability() -> None:
    group = SignalDbGroup("databases/signal.db", "Test DB")
    with pytest.raises(FrozenInstanceError):
        group.relative_path = "changed"  # type: ignore[misc]


def test_signal_profile_immutability() -> None:
    profile = SignalProfile(
        package="test.signal",
        display_name="Signal Test",
        private_data_root="/data/data/test.signal",
        db_groups=(),
        shared_media_roots=(),
    )
    with pytest.raises(FrozenInstanceError):
        profile.package = "changed"  # type: ignore[misc]


def test_get_profile_known_packages() -> None:
    for profile in SIGNAL_PROFILES:
        res = get_profile(profile.package)
        assert res is not None
        assert res.package == profile.package


def test_signal_profile_fields_valid() -> None:
    for profile in SIGNAL_PROFILES:
        assert profile.package
        assert profile.private_data_root.startswith("/")
        assert profile.db_groups
        for db_group in profile.db_groups:
            assert db_group.relative_path
            assert not db_group.relative_path.startswith("/")
        for root in profile.shared_media_roots:
            assert root.startswith("/")
    assert set(SQLITE_SIDECAR_EXTENSIONS) == {"-wal", "-shm", "-journal"}


@pytest.fixture
def synthetic_signal_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "signal.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE recipient (_id INTEGER PRIMARY KEY, phone TEXT, system_display_name TEXT)")
    cur.execute("CREATE TABLE thread (_id INTEGER PRIMARY KEY, recipient_id INTEGER, date INTEGER, message_count INTEGER, snippet TEXT)")
    cur.execute("CREATE TABLE sms (_id INTEGER PRIMARY KEY, thread_id INTEGER, recipient_id INTEGER, date INTEGER, date_sent INTEGER, date_received INTEGER, body TEXT, type INTEGER, read INTEGER)")
    cur.execute("INSERT INTO recipient (_id, phone, system_display_name) VALUES (1, '+15550001', 'Alice')")
    cur.execute("INSERT INTO thread (_id, recipient_id, date, message_count, snippet) VALUES (10, 1, 1600000000, 1, 'hello')")
    cur.execute("INSERT INTO sms (_id, thread_id, recipient_id, date, date_sent, date_received, body, type, read) VALUES (100, 10, 1, 1600000000000, 1600000001000, 1600000002000, 'hello from signal', 10485783, 1)")
    conn.commit()
    conn.close()
    return db_path


def test_signal_parser_supported(synthetic_signal_db: Path) -> None:
    with SignalParser(synthetic_signal_db) as parser:
        assert parser.supported is True
        data = parser.parse_all()
    assert data["status"] == "success"
    assert len(data["recipients"]) == 1
    assert len(data["threads"]) == 1
    assert len(data["messages"]) == 1
    assert data["messages"][0] == {
        "date": "2020-09-13 12:26:41 UTC",
        "contact_name": "Alice",
        "received": False,
        "sent": True,
        "message": "hello from signal",
    }


def test_signal_parser_unsupported_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "unsupported.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    with SignalParser(db_path) as parser:
        assert parser.supported is False
        data = parser.parse_all()
    assert data["status"] == "unsupported"
    assert "Unrecognized Signal schema" in data["errors"][0]
