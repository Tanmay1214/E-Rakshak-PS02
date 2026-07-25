"""Chromium browser history SQLite parser for E-RAKSHAK.

Parses history databases of Chromium-based browsers (Chrome, Brave, Edge, etc.)
for urls, visits, downloads, and search queries.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Any, Optional, Union


def chrome_time_to_iso(value: Any, timezone_name: str = "Asia/Kolkata") -> Optional[str]:
    """Convert WebKit timestamp (microseconds since 1601-01-01 UTC) to ISO 8601 string."""
    if value is None:
        return None
    try:
        val_int = int(value)
        if val_int <= 0:
            return None
        # WebKit timestamp: microseconds since 1601-01-01 UTC.
        # Unix epoch begins 11,644,473,600 seconds after WebKit epoch.
        unix_epoch_seconds = (val_int / 1_000_000.0) - 11644473600.0
        if unix_epoch_seconds < 0:
            return None
        
        dt_utc = datetime.datetime.fromtimestamp(unix_epoch_seconds, datetime.timezone.utc)
        
        # Convert to target timezone (Asia/Kolkata is default)
        if timezone_name == "Asia/Kolkata":
            tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        else:
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(timezone_name)
            except Exception:
                tz = datetime.timezone.utc
                
        dt_local = dt_utc.astimezone(tz)
        return dt_local.isoformat()
    except Exception:
        return None


def parse_chromium_history(
    db_path: Path,
    browser_name: str,
    package_name: str,
    profile: str = "Default"
) -> dict[str, list[dict[str, Any]]]:
    """Parse Chromium History SQLite DB for visits, keyword searches, and downloads.

    Returns a dict with keys: 'history', 'searches', 'downloads'.
    """
    results: dict[str, list[dict[str, Any]]] = {
        "history": [],
        "searches": [],
        "downloads": []
    }
    
    if not db_path.is_file():
        return results
        
    conn = None
    try:
        # Connect in read-only mode to prevent database modification
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        
        # 1. Parse Visits and URLs
        try:
            # Query joined visits + urls for precise visit-level timestamps
            query = """
                SELECT v.visit_time, u.url, u.title, u.visit_count, u.typed_count, u.last_visit_time
                FROM visits v
                JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
            """
            rows = conn.execute(query).fetchall()
            for r in rows:
                ts = chrome_time_to_iso(r["visit_time"])
                if not ts:
                    ts = chrome_time_to_iso(r["last_visit_time"])
                    
                results["history"].append({
                    "timestamp": ts or "unknown",
                    "browser": browser_name,
                    "package_name": package_name,
                    "profile": profile,
                    "url": r["url"] or "",
                    "title": r["title"] or "",
                    "visit_count": r["visit_count"] or 0,
                    "typed_count": r["typed_count"] or 0,
                    "last_visit_time_raw": r["last_visit_time"] or 0,
                    "source_db": db_path.name,
                    "confidence": "high"
                })
        except Exception:
            # Fall back to urls table alone if visits table has schema issues
            try:
                query = "SELECT url, title, visit_count, typed_count, last_visit_time FROM urls ORDER BY last_visit_time DESC"
                rows = conn.execute(query).fetchall()
                for r in rows:
                    ts = chrome_time_to_iso(r["last_visit_time"])
                    results["history"].append({
                        "timestamp": ts or "unknown",
                        "browser": browser_name,
                        "package_name": package_name,
                        "profile": profile,
                        "url": r["url"] or "",
                        "title": r["title"] or "",
                        "visit_count": r["visit_count"] or 0,
                        "typed_count": r["typed_count"] or 0,
                        "last_visit_time_raw": r["last_visit_time"] or 0,
                        "source_db": db_path.name,
                        "confidence": "medium"
                    })
            except Exception:
                pass
                
        # 2. Parse Keyword Search Terms
        try:
            query = """
                SELECT k.term, u.url, u.last_visit_time
                FROM keyword_search_terms k
                JOIN urls u ON k.url_id = u.id
                ORDER BY u.last_visit_time DESC
            """
            rows = conn.execute(query).fetchall()
            for r in rows:
                ts = chrome_time_to_iso(r["last_visit_time"])
                results["searches"].append({
                    "timestamp": ts or "unknown",
                    "browser": browser_name,
                    "package_name": package_name,
                    "profile": profile,
                    "search_term": r["term"] or "",
                    "url": r["url"] or "",
                    "source_db": db_path.name,
                    "confidence": "high"
                })
        except Exception:
            pass
            
        # 3. Parse Downloads
        try:
            # Modern Chrome schema stores urls inside download_urls mapping table
            # Check if download_urls exists
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='download_urls'")
            has_download_urls = cursor.fetchone() is not None
            
            if has_download_urls:
                query = """
                    SELECT d.target_path, d.start_time, d.received_bytes, d.total_bytes, d.mime_type, du.url
                    FROM downloads d
                    LEFT JOIN download_urls du ON d.id = du.id
                    ORDER BY d.start_time DESC
                """
            else:
                # Older schema stores url inside downloads table
                query = """
                    SELECT target_path, start_time, received_bytes, total_bytes, mime_type, url
                    FROM downloads
                    ORDER BY start_time DESC
                """
                
            rows = conn.execute(query).fetchall()
            for r in rows:
                ts = chrome_time_to_iso(r["start_time"])
                # Note: target_path can be raw path or relative
                # Let's extract clean path
                t_path = r["target_path"] or ""
                # E.g. some might be bytes
                if isinstance(t_path, bytes):
                    t_path = t_path.decode("utf-8", errors="ignore")
                    
                url_val = r["url"] or ""
                if isinstance(url_val, bytes):
                    url_val = url_val.decode("utf-8", errors="ignore")
                    
                results["downloads"].append({
                    "timestamp": ts or "unknown",
                    "browser": browser_name,
                    "package_name": package_name,
                    "profile": profile,
                    "download_url": url_val,
                    "target_path": t_path,
                    "mime_type": r["mime_type"] or "",
                    "received_bytes": r["received_bytes"] or 0,
                    "total_bytes": r["total_bytes"] or 0,
                    "source_db": db_path.name,
                    "confidence": "high"
                })
        except Exception:
            pass
            
    except Exception:
        pass
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
                
    return results
