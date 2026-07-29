from __future__ import annotations
from typing import List, Dict, Any
from .db import DashboardDB
import logging

logger = logging.getLogger(__name__)

def search_evidence(db: DashboardDB, keyword: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    keyword = f"%{keyword}%"
    results = []
    
    # messages
    cursor = db.conn.execute("SELECT id, timestamp, 'messages' as result_type, app as source, body as snippet, 'high' as confidence, id as event_id FROM messages WHERE body LIKE ? LIMIT ? OFFSET ?", (keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))

    # timeline_events
    cursor = db.conn.execute("SELECT id, timestamp, 'timeline' as result_type, source_app as source, summary as snippet, confidence, id as event_id FROM timeline_events WHERE summary LIKE ? OR title LIKE ? LIMIT ? OFFSET ?", (keyword, keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))

    # contacts
    cursor = db.conn.execute("SELECT id, last_seen as timestamp, 'contacts' as result_type, source_app as source, name || ' ' || phone || ' ' || email as snippet, 'high' as confidence, id as event_id FROM contacts WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? LIMIT ? OFFSET ?", (keyword, keyword, keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))

    # apps
    cursor = db.conn.execute("SELECT package_name as id, install_time as timestamp, 'apps' as result_type, 'system' as source, app_name || ' ' || package_name as snippet, 'high' as confidence, package_name as event_id FROM apps WHERE package_name LIKE ? OR app_name LIKE ? LIMIT ? OFFSET ?", (keyword, keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))

    # accounts
    cursor = db.conn.execute("SELECT id, '' as timestamp, 'accounts' as result_type, provider_app as source, account_name || ' ' || email as snippet, 'high' as confidence, id as event_id FROM accounts WHERE account_name LIKE ? OR email LIKE ? LIMIT ? OFFSET ?", (keyword, keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))
    
    # media
    cursor = db.conn.execute("SELECT id, timestamp, 'media' as result_type, source_app as source, filename as snippet, 'high' as confidence, id as event_id FROM media WHERE filename LIKE ? LIMIT ? OFFSET ?", (keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))
    
    # system_events
    cursor = db.conn.execute("SELECT id, timestamp, 'system' as result_type, source as source, summary as snippet, 'high' as confidence, id as event_id FROM system_events WHERE summary LIKE ? LIMIT ? OFFSET ?", (keyword, limit, offset))
    for row in cursor.fetchall(): results.append(dict(row))

    # Sort results
    results.sort(key=lambda x: x.get('timestamp') or '', reverse=True)
    return results[:limit]
