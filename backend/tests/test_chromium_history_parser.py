"""Tests for Chromium history SQLite database parser in E-RAKSHAK."""

import sqlite3
from pathlib import Path
from erakshak.parsers.chromium_history import chrome_time_to_iso, parse_chromium_history


def test_chrome_timestamp_conversion() -> None:
    # 2023-06-05 12:00:00 UTC = 13330363200000000 WebKit microseconds
    iso_str = chrome_time_to_iso(13330363200000000, timezone_name="UTC")
    assert iso_str is not None
    assert iso_str.startswith("2023-06-04T14:40:00")

    # Null/invalid checks
    assert chrome_time_to_iso(None) is None
    assert chrome_time_to_iso(0) is None
    assert chrome_time_to_iso(-10) is None


def test_parse_chromium_history_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "History"
    # Create empty db
    conn = sqlite3.connect(db_path)
    conn.close()

    res = parse_chromium_history(db_path, "Chrome", "com.android.chrome")
    assert res["history"] == []
    assert res["searches"] == []
    assert res["downloads"] == []


def test_parse_chromium_history_valid_db(tmp_path: Path) -> None:
    db_path = tmp_path / "History"
    conn = sqlite3.connect(db_path)
    
    # Create tables
    conn.execute("""
        CREATE TABLE urls (
            id INTEGER PRIMARY KEY,
            url TEXT,
            title TEXT,
            visit_count INTEGER,
            typed_count INTEGER,
            last_visit_time INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE visits (
            id INTEGER PRIMARY KEY,
            url INTEGER,
            visit_time INTEGER,
            from_visit INTEGER,
            transition INTEGER,
            segment_id INTEGER,
            visit_duration INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE keyword_search_terms (
            keyword_id INTEGER,
            url_id INTEGER,
            lower_term TEXT,
            term TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE downloads (
            id INTEGER PRIMARY KEY,
            guid TEXT,
            current_path TEXT,
            target_path TEXT,
            start_time INTEGER,
            received_bytes INTEGER,
            total_bytes INTEGER,
            state INTEGER,
            opened INTEGER,
            last_access_time INTEGER,
            transient INTEGER,
            referrer TEXT,
            site_url TEXT,
            embedder_download_data TEXT,
            mime_type TEXT,
            url TEXT
        )
    """)
    
    # Insert mock values
    # Time: 13330363200000000 (2023-06-05 12:00:00 UTC)
    conn.execute("INSERT INTO urls VALUES (1, 'https://google.com', 'Google', 2, 1, 13330363200000000)")
    conn.execute("INSERT INTO visits VALUES (1, 1, 13330363200000000, 0, 0, 0, 0)")
    conn.execute("INSERT INTO keyword_search_terms VALUES (1, 1, 'cyber forensics', 'cyber forensics')")
    conn.execute("INSERT INTO downloads VALUES (1, 'guid', '/downloads/test.pdf', '/downloads/test.pdf', 13330363200000000, 100, 100, 1, 1, 0, 0, '', '', '', 'application/pdf', 'https://google.com/test.pdf')")
    
    conn.commit()
    conn.close()

    res = parse_chromium_history(db_path, "Chrome", "com.android.chrome")
    
    # Assert URLs/Visits
    assert len(res["history"]) == 1
    assert res["history"][0]["url"] == "https://google.com"
    assert res["history"][0]["title"] == "Google"
    assert res["history"][0]["visit_count"] == 2
    
    # Assert Search Terms
    assert len(res["searches"]) == 1
    assert res["searches"][0]["search_term"] == "cyber forensics"
    assert res["searches"][0]["url"] == "https://google.com"

    # Assert Downloads
    assert len(res["downloads"]) == 1
    assert res["downloads"][0]["download_url"] == "https://google.com/test.pdf"
    assert res["downloads"][0]["target_path"] == "/downloads/test.pdf"
    assert res["downloads"][0]["mime_type"] == "application/pdf"
    assert res["downloads"][0]["total_bytes"] == 100
