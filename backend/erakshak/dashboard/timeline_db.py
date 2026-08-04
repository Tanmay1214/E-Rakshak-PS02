"""Database interaction for E-RAKSHAK timeline builder."""

import sqlite3
from pathlib import Path
from typing import List
from erakshak.dashboard.timeline_models import TimelineEvent


def init_timeline_db(db_path: Path) -> None:
    """Create the SQLite database and the timeline_events table with indexes if it does not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id TEXT PRIMARY KEY,
            case_id TEXT,
            exhibit_id TEXT,
            timestamp TEXT,
            timestamp_sort INTEGER,
            bucket_15m TEXT,
            bucket_1h TEXT,
            source_app TEXT,
            source_type TEXT,
            category TEXT,
            event_type TEXT,
            direction TEXT,
            title TEXT,
            summary TEXT,
            actor TEXT,
            sender TEXT,
            receiver TEXT,
            phone_number TEXT,
            email TEXT,
            location_lat REAL,
            location_lon REAL,
            location_accuracy REAL,
            media_path TEXT,
            thumbnail_path TEXT,
            file_path TEXT,
            deleted_status TEXT,
            recovered_status TEXT,
            confidence TEXT,
            source_file TEXT,
            source_hash TEXT,
            parser TEXT,
            raw_ref TEXT,
            raw_json TEXT
        )
    """)

    # Create required indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_timeline_timestamp_sort ON timeline_events(timestamp_sort)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_source_app ON timeline_events(source_app)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_source_type ON timeline_events(source_type)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_category ON timeline_events(category)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_event_type ON timeline_events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_confidence ON timeline_events(confidence)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_deleted_status ON timeline_events(deleted_status)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_recovered_status ON timeline_events(recovered_status)",
    ]
    for idx in indexes:
        cursor.execute(idx)

    conn.commit()
    conn.close()



def save_events_to_db(
    db_path: Path,
    events: List[TimelineEvent],
    rebuild: bool = False,
    case_id: str = "",
    exhibit_id: str = ""
) -> None:
    """Save parsed timeline events to the SQLite database. Overwrite on rebuild."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    if rebuild:
        cursor.execute("DELETE FROM timeline_events")

    query = """
        INSERT OR REPLACE INTO timeline_events (
            id, case_id, exhibit_id, timestamp, timestamp_sort, bucket_15m, bucket_1h,
            source_app, source_type, category, event_type, direction, title, summary,
            actor, sender, receiver, phone_number, email, location_lat, location_lon,
            location_accuracy, media_path, thumbnail_path, file_path, deleted_status,
            recovered_status, confidence, source_file, source_hash, parser, raw_ref, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = []
    for e in events:
        data.append((
            e.id, e.case_id, e.exhibit_id, e.timestamp, e.timestamp_sort, e.bucket_15m, e.bucket_1h,
            e.source_app, e.source_type, e.category, e.event_type, e.direction, e.title, e.summary,
            e.actor, e.sender, e.receiver, e.phone_number, e.email, e.location_lat, e.location_lon,
            e.location_accuracy, e.media_path, e.thumbnail_path, e.file_path, e.deleted_status,
            e.recovered_status, e.confidence, e.source_file, e.source_hash, e.parser, e.raw_ref, e.raw_json
        ))

    cursor.executemany(query, data)
    conn.commit()
    conn.close()
