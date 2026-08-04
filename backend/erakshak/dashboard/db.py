from __future__ import annotations
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class DashboardDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._connect()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def create_tables(self):
        schemas = {
            "case_info": '''
                CREATE TABLE IF NOT EXISTS case_info (
                    case_id TEXT, exhibit_id TEXT, case_folder TEXT,
                    acquisition_status TEXT, acquisition_started_at TEXT,
                    acquisition_completed_at TEXT, dashboard_indexed_at TEXT,
                    total_events INTEGER, total_messages INTEGER, total_calls INTEGER,
                    total_contacts INTEGER, total_media INTEGER, total_apps INTEGER,
                    total_locations INTEGER, total_accounts INTEGER, total_files INTEGER,
                    notes TEXT
                )
            ''',
            "device_info": '''
                CREATE TABLE IF NOT EXISTS device_info (
                    case_id TEXT, exhibit_id TEXT, manufacturer TEXT,
                    brand TEXT, model TEXT, device TEXT, android_version TEXT,
                    sdk_level TEXT, security_patch TEXT, build_fingerprint TEXT,
                    serial TEXT, imei TEXT, root_access TEXT, acquisition_method TEXT,
                    raw_json TEXT
                )
            ''',
            "timeline_events": '''
                CREATE TABLE IF NOT EXISTS timeline_events (
                    id TEXT PRIMARY KEY, case_id TEXT, exhibit_id TEXT, timestamp TEXT, timestamp_sort INTEGER,
                    bucket_15m TEXT, bucket_1h TEXT,
                    source_app TEXT, source_type TEXT, event_type TEXT, category TEXT,
                    direction TEXT, title TEXT, summary TEXT, actor TEXT, sender TEXT, receiver TEXT,
                    phone_number TEXT, email TEXT, location_lat REAL, location_lon REAL,
                    location_accuracy REAL, media_path TEXT, thumbnail_path TEXT,
                    file_path TEXT, deleted_status TEXT, recovered_status TEXT,
                    confidence TEXT, source_file TEXT, source_hash TEXT, parser TEXT,
                    raw_ref TEXT, raw_json TEXT
                )
            ''',
            "messages": '''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    app TEXT, platform TEXT, chat_id TEXT, chat_name TEXT, direction TEXT,
                    sender TEXT, receiver TEXT, body TEXT, message_type TEXT,
                    deleted_status TEXT, recovered_status TEXT, media_path TEXT,
                    source_file TEXT, source_hash TEXT, parser TEXT, raw_json TEXT
                )
            ''',
            "calls": '''
                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    source TEXT, call_type TEXT, direction TEXT, from_number TEXT,
                    to_number TEXT, contact_name TEXT, duration_seconds INTEGER,
                    app TEXT, source_file TEXT, raw_json TEXT
                )
            ''',
            "contacts": '''
                CREATE TABLE IF NOT EXISTS contacts (
                    id TEXT PRIMARY KEY, name TEXT, phone TEXT, email TEXT,
                    source_app TEXT, apps_seen_in TEXT, message_count INTEGER,
                    call_count INTEGER, last_seen TEXT, raw_json TEXT
                )
            ''',
            "media": '''
                CREATE TABLE IF NOT EXISTS media (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    filename TEXT, mime_type TEXT, source_app TEXT, path TEXT,
                    thumbnail_path TEXT, size_bytes INTEGER, sha256 TEXT,
                    linked_event_id TEXT, raw_json TEXT
                )
            ''',
            "locations": '''
                CREATE TABLE IF NOT EXISTS locations (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    latitude REAL, longitude REAL, accuracy REAL, source TEXT,
                    linked_event_id TEXT, raw_json TEXT
                )
            ''',
            "apps": '''
                CREATE TABLE IF NOT EXISTS apps (
                    package_name TEXT PRIMARY KEY, app_name TEXT, version_name TEXT,
                    version_code TEXT, apk_path TEXT, install_time TEXT,
                    last_update_time TEXT, uid TEXT, is_system_app INTEGER,
                    permissions TEXT, raw_json TEXT
                )
            ''',
            "accounts": '''
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, account_name TEXT, account_type TEXT,
                    email TEXT, provider_app TEXT, sync_provider TEXT,
                    source_file TEXT, raw_json TEXT
                )
            ''',
            "network_events": '''
                CREATE TABLE IF NOT EXISTS network_events (
                    id TEXT PRIMARY KEY, timestamp TEXT, type TEXT, source TEXT,
                    ip TEXT, ssid TEXT, carrier TEXT, vpn_state TEXT, dns TEXT,
                    raw_json TEXT
                )
            ''',
            "system_events": '''
                CREATE TABLE IF NOT EXISTS system_events (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    event_type TEXT, source TEXT, severity TEXT, title TEXT,
                    summary TEXT, raw_json TEXT
                )
            ''',
            "parser_outputs": '''
                CREATE TABLE IF NOT EXISTS parser_outputs (
                    id TEXT PRIMARY KEY, parser TEXT, app TEXT, status TEXT,
                    input_path TEXT, output_path TEXT, generated_file_count INTEGER,
                    summary_json TEXT
                )
            ''',
            "hashes": '''
                CREATE TABLE IF NOT EXISTS hashes (
                    id TEXT PRIMARY KEY, file_path TEXT, sha256 TEXT,
                    size_bytes INTEGER, status TEXT, source TEXT
                )
            ''',
            "audit_events": '''
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY, timestamp TEXT, action TEXT,
                    result TEXT, details_json TEXT
                )
            ''',
            "browser_history": '''
                CREATE TABLE IF NOT EXISTS browser_history (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    browser TEXT, package_name TEXT, profile TEXT,
                    url TEXT, title TEXT, visit_count INTEGER, typed_count INTEGER,
                    confidence TEXT, raw_json TEXT
                )
            ''',
            "browser_searches": '''
                CREATE TABLE IF NOT EXISTS browser_searches (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    browser TEXT, package_name TEXT, profile TEXT,
                    search_term TEXT, url TEXT, confidence TEXT, raw_json TEXT
                )
            ''',
            "browser_downloads": '''
                CREATE TABLE IF NOT EXISTS browser_downloads (
                    id TEXT PRIMARY KEY, timestamp TEXT, timestamp_sort INTEGER,
                    browser TEXT, package_name TEXT, profile TEXT,
                    download_url TEXT, target_path TEXT, mime_type TEXT,
                    received_bytes INTEGER, total_bytes INTEGER,
                    confidence TEXT, raw_json TEXT
                )
            ''',
            "examiner_info": '''
                CREATE TABLE IF NOT EXISTS examiner_info (
                    id TEXT PRIMARY KEY, name TEXT, badge_id TEXT,
                    rank_title TEXT, agency TEXT, email TEXT, phone TEXT,
                    notes TEXT, updated_at TEXT
                )
            ''',
            "chain_of_custody": '''
                CREATE TABLE IF NOT EXISTS chain_of_custody (
                    id TEXT PRIMARY KEY, entry_index INTEGER, timestamp TEXT,
                    action TEXT, performed_by TEXT, received_by TEXT,
                    location TEXT, evidence_condition TEXT, notes TEXT,
                    created_at TEXT
                )
            ''',
            "evidence_metadata": '''
                CREATE TABLE IF NOT EXISTS evidence_metadata (
                    id TEXT PRIMARY KEY, storage_location TEXT,
                    evidence_bag_tag TEXT, seizure_date TEXT,
                    seizure_location TEXT, seizure_authority TEXT,
                    warrant_number TEXT, acquisition_tool TEXT,
                    acquisition_tool_version TEXT, notes TEXT,
                    updated_at TEXT
                )
            ''',
            "questioning_leads": '''
                CREATE TABLE IF NOT EXISTS questioning_leads (
                    lead_id TEXT PRIMARY KEY,
                    case_id TEXT,
                    exhibit_id TEXT,
                    rule_id TEXT,
                    severity TEXT,
                    confidence TEXT,
                    title TEXT,
                    summary TEXT,
                    suggested_question TEXT,
                    category TEXT,
                    source_apps TEXT,
                    event_ids TEXT,
                    evidence_count INTEGER,
                    time_window_start INTEGER,
                    time_window_end INTEGER,
                    created_at TEXT,
                    raw_json TEXT
                )
            '''
        }
        for query in schemas.values():
            self.conn.execute(query)
        self.conn.commit()

    def create_indexes(self):
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_timeline_ts ON timeline_events(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_app ON timeline_events(source_app)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_cat ON timeline_events(category)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_type ON timeline_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_messages_app ON messages(app)",
            "CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_media_ts ON media(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_locations_ts ON locations(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_leads_rule ON questioning_leads(rule_id)",
            "CREATE INDEX IF NOT EXISTS idx_leads_severity ON questioning_leads(severity)",
            "CREATE INDEX IF NOT EXISTS idx_leads_confidence ON questioning_leads(confidence)",
            "CREATE INDEX IF NOT EXISTS idx_leads_category ON questioning_leads(category)",
            "CREATE INDEX IF NOT EXISTS idx_browser_history_ts ON browser_history(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_browser_searches_ts ON browser_searches(timestamp_sort)",
            "CREATE INDEX IF NOT EXISTS idx_browser_downloads_ts ON browser_downloads(timestamp_sort)"
        ]
        for idx in indexes:
            self.conn.execute(idx)
        self.conn.commit()

    def clear_all(self):
        # Only clear auto-generated evidence tables; preserve examiner-entered data
        tables = [
            "case_info", "device_info", "timeline_events", "messages", "calls",
            "contacts", "media", "locations", "apps", "accounts", "network_events",
            "system_events", "parser_outputs", "hashes", "audit_events",
            "browser_history", "browser_searches", "browser_downloads"
        ]
        for table in tables:
            self.conn.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.commit()
        self.create_tables()
        self.create_indexes()

    def delete_record(self, table: str, id_field: str, id_value: str):
        self.conn.execute(f"DELETE FROM {table} WHERE {id_field} = ?", (id_value,))
        self.conn.commit()

    def insert_record(self, table: str, record_dict: Dict[str, Any]):
        keys = ', '.join(record_dict.keys())
        placeholders = ', '.join(['?'] * len(record_dict))
        query = f"INSERT OR REPLACE INTO {table} ({keys}) VALUES ({placeholders})"
        self.conn.execute(query, tuple(record_dict.values()))
        self.conn.commit()

    def insert_batch(self, table: str, records_list: List[Dict[str, Any]]):
        if not records_list:
            return
        keys = ', '.join(records_list[0].keys())
        placeholders = ', '.join(['?'] * len(records_list[0]))
        query = f"INSERT OR REPLACE INTO {table} ({keys}) VALUES ({placeholders})"
        data = [tuple(r.values()) for r in records_list]
        self.conn.executemany(query, data)
        self.conn.commit()

    def query(self, table: str, filters: Dict[str, Any] = None, limit: int = 100, offset: int = 0, order_by: str = 'timestamp_sort DESC') -> List[Dict[str, Any]]:
        query_str = f"SELECT * FROM {table}"
        params = []
        if filters:
            conditions = []
            for k, v in filters.items():
                if v is not None:
                    conditions.append(f"{k} = ?")
                    params.append(v)
            if conditions:
                query_str += " WHERE " + " AND ".join(conditions)
        
        if order_by and "timestamp_sort" in [c[1] for c in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]:
             query_str += f" ORDER BY {order_by}"
        elif order_by and table not in ["case_info", "device_info"]:
             query_str += " ORDER BY rowid DESC"

        query_str += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.execute(query_str, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def count(self, table: str, filters: Dict[str, Any] = None) -> int:
        query_str = f"SELECT COUNT(*) FROM {table}"
        params = []
        if filters:
            conditions = []
            for k, v in filters.items():
                if v is not None:
                    conditions.append(f"{k} = ?")
                    params.append(v)
            if conditions:
                query_str += " WHERE " + " AND ".join(conditions)
        cursor = self.conn.execute(query_str, tuple(params))
        return cursor.fetchone()[0]

    def search_text(self, keyword: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        # This will be implemented in search.py instead, or handled generically
        return []

    def get_record(self, table: str, id_field: str, id_value: Any) -> Optional[Dict[str, Any]]:
        query = f"SELECT * FROM {table} WHERE {id_field} = ?"
        cursor = self.conn.execute(query, (id_value,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_counts(self) -> Dict[str, int]:
        tables = ["timeline_events", "messages", "calls", "contacts", "media", "apps", "locations", "accounts",
                  "browser_history", "browser_searches", "browser_downloads", "network_events", "system_events"]
        counts = {}
        for table in tables:
            counts[table] = self.count(table)
        return counts
