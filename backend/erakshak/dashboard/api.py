from __future__ import annotations
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from pydantic import BaseModel
from typing import Optional
from .db import DashboardDB
from .dashboard_indexer import build_evidence_index
from .search import search_evidence
from .integrity import verify_case_hashes
from .report_export import export_html_report
import hashlib


import re

class ExaminerInfoPayload(BaseModel):
    name: str
    badge_id: Optional[str] = None
    rank_title: Optional[str] = None
    agency: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

def parse_api_timestamp(ts_val: Any) -> Optional[int]:
    if not ts_val:
        return None
    val_str = str(ts_val).strip()
    if not val_str:
        return None
    # Check if numeric (optionally float/int)
    if re.match(r"^-?\d+(\.\d+)?$", val_str):
        try:
            val_num = float(val_str)
            if val_num > 1e11:  # Milliseconds
                return int(val_num / 1000)
            return int(val_num)
        except Exception:
            pass
    # Otherwise parse as ISO or date formats using time_utils.parse_timestamp
    from erakshak.dashboard.time_utils import parse_timestamp
    dt = parse_timestamp(val_str)
    if dt:
        return int(dt.timestamp())
    return None

def sanitize_and_standardize_event(e: dict, include_raw_json: bool = False) -> dict:
    from erakshak.dashboard.time_utils import parse_timestamp
    raw_ts = e.get("timestamp")
    dt = parse_timestamp(raw_ts)
    if not dt and e.get("timestamp_sort"):
        dt = parse_timestamp(e["timestamp_sort"])
        
    if dt:
        e["timestamp"] = dt.strftime("%d %b %Y, %I:%M:%S %p")
        e["display_date"] = dt.strftime("%d %b %Y")
        e["display_time"] = dt.strftime("%I:%M:%S %p")
    else:
        e["display_date"] = "Not available"
        e["display_time"] = "Not available"

    # Set boolean deleted and recovered status
    e["deleted"] = True if e.get("deleted_status") else False
    e["recovered"] = True if e.get("recovered_status") in ("recovered", "recovered_chat") or e.get("recovered") else False

    # Redact raw_json
    if not include_raw_json:
        e.pop("raw_json", None)
    else:
        raw_json = e.get("raw_json")
        if raw_json and isinstance(raw_json, str):
            try:
                import json
                js = json.loads(raw_json)
                if isinstance(js, dict):
                    # Redact any keys containing key, token, secret, cipher, password
                    js = {k: v for k, v in js.items() if not any(x in k.lower() for x in ["key", "token", "secret", "cipher", "password"])}
                    e["raw_json"] = json.dumps(js, ensure_ascii=False)
            except Exception:
                pass
                
    # Redact any other credentials/keys
    for k, v in list(e.items()):
        if isinstance(v, str) and k != "source_hash":
            if any(x in k.lower() for x in ["key", "token", "secret", "password"]):
                e[k] = "<REDACTED>"

    # Ensure all target keys are present in the response
    schema_keys = [
        "id", "timestamp", "timestamp_sort", "display_date", "display_time",
        "source_app", "source_type", "category", "event_type", "direction",
        "title", "summary", "sender", "receiver", "phone_number", "email",
        "location_lat", "location_lon", "media_path", "thumbnail_path",
        "file_path", "deleted_status", "recovered_status", "confidence",
        "source_file", "source_hash", "parser", "deleted", "recovered"
    ]
    
    result = {}
    for key in schema_keys:
        result[key] = e.get(key)
        
    if include_raw_json:
        result["raw_json"] = e.get("raw_json")
        
    return result

class ChainOfCustodyPayload(BaseModel):
    timestamp: str
    action: str
    performed_by: Optional[str] = None
    received_by: Optional[str] = None
    location: Optional[str] = None
    evidence_condition: Optional[str] = None
    notes: Optional[str] = None

class EvidenceMetadataPayload(BaseModel):
    storage_location: Optional[str] = None
    evidence_bag_tag: Optional[str] = None
    seizure_date: Optional[str] = None
    seizure_location: Optional[str] = None
    seizure_authority: Optional[str] = None
    warrant_number: Optional[str] = None
    acquisition_tool: Optional[str] = None
    acquisition_tool_version: Optional[str] = None
    notes: Optional[str] = None

def create_dashboard_app(db_path: Path, exhibit_root: Path, case_id: str, exhibit_id: str) -> FastAPI:
    app = FastAPI(title="E-RAKSHAK Dashboard API")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8765", "http://127.0.0.1:8765"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    def get_db():
        if not db_path.exists():
            raise HTTPException(status_code=503, detail="Evidence index not found. Run build-dashboard-index first.")
        return DashboardDB(db_path)

    def get_db_for(c_id: str, ex_id: str):
        target_path = exhibit_root.parent.parent / c_id / ex_id / "derived" / "evidence_index.db"
        if not target_path.exists():
            if c_id == case_id and ex_id == exhibit_id and db_path.exists():
                return DashboardDB(db_path)
            raise HTTPException(status_code=404, detail=f"Evidence index not found for case {c_id} exhibit {ex_id}")
        return DashboardDB(target_path)

    def execute_timeline_query(
        db: DashboardDB,
        category: Optional[str] = None,
        source_app: Optional[str] = None,
        source_type: Optional[str] = None,
        confidence: Optional[str] = None,
        include_low: bool = False,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        q: Optional[str] = None,
        deleted: Optional[bool] = None,
        recovered: Optional[bool] = None,
        limit: int = 200,
        offset: int = 0,
        order: str = "desc",
        debug: bool = False
    ) -> dict:
        query_str = "SELECT * FROM timeline_events WHERE 1=1"
        params = []
        
        if category:
            query_str += " AND category = ?"
            params.append(category)
        if source_app:
            query_str += " AND source_app = ?"
            params.append(source_app)
        if source_type:
            query_str += " AND source_type = ?"
            params.append(source_type)
            
        if confidence:
            query_str += " AND confidence = ?"
            params.append(confidence)
        elif not include_low:
            query_str += " AND (confidence IS NULL OR confidence != 'low')"

        start_secs = parse_api_timestamp(from_ts)
        if start_secs is not None:
            query_str += " AND timestamp_sort >= ?"
            params.append(start_secs)
            
        end_secs = parse_api_timestamp(to_ts)
        if end_secs is not None:
            query_str += " AND timestamp_sort <= ?"
            params.append(end_secs)
            
        if deleted is not None:
            if deleted:
                query_str += " AND (deleted_status IS NOT NULL AND deleted_status != '')"
            else:
                query_str += " AND (deleted_status IS NULL OR deleted_status = '')"
                
        if recovered is not None:
            if recovered:
                query_str += " AND (recovered_status = 'recovered' OR recovered_status = 'recovered_chat')"
            else:
                query_str += " AND (recovered_status IS NULL OR recovered_status NOT IN ('recovered', 'recovered_chat'))"

        if q:
            q_like = f"%{q}%"
            query_str += " AND (title LIKE ? OR summary LIKE ? OR sender LIKE ? OR receiver LIKE ? OR phone_number LIKE ? OR email LIKE ? OR source_app LIKE ? OR source_type LIKE ?)"
            params.extend([q_like] * 8)
            
        count_query = query_str.replace("SELECT *", "SELECT COUNT(*)")
        total = db.conn.execute(count_query, tuple(params)).fetchone()[0]
        
        sort_dir = "DESC" if order.lower() == "desc" else "ASC"
        query_str += f" ORDER BY timestamp_sort {sort_dir}, id {sort_dir}"
        
        query_str += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = db.conn.execute(query_str, tuple(params))
        events = [dict(row) for row in cursor.fetchall()]
        
        sanitized = [sanitize_and_standardize_event(e, include_raw_json=debug) for e in events]
        return {"events": sanitized, "total": total}

    @app.get("/")
    def read_root():
        return {
            "message": "E-RAKSHAK Dashboard API is running. Please open the frontend (e.g., http://localhost:5173) to view the dashboard."
        }

    @app.get("/api/case/summary")
    def case_summary():
        with get_db() as db:
            case = db.query("case_info", limit=1)
            dev = db.query("device_info", limit=1)
            counts = db.get_counts()
            case_rec = case[0] if case else {}
            dev_rec = dev[0] if dev else {}
            
            # Read timeline_summary.json for warnings and other details
            warnings_list = []
            missing_sources = []
            summary_file = exhibit_root / "derived" / "timeline_summary.json"
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        sum_data = json.load(f)
                        warnings_list = sum_data.get("warnings", [])
                        missing_sources = sum_data.get("missing_sources", [])
                except Exception as e:
                    logger.warning(f"Failed to read timeline_summary.json: {e}")
            
            return {
                "case_id": case_rec.get("case_id", case_id),
                "exhibit_id": case_rec.get("exhibit_id", exhibit_id),
                "case_info": case_rec,
                "device_info": dev_rec,
                "counts": counts,
                "warnings": warnings_list,
                "missing_sources": missing_sources
            }

    @app.get("/api/device")
    def device_info():
        with get_db() as db:
            dev = db.query("device_info", limit=1)
            return dev[0] if dev else {}

    @app.get("/api/timeline")
    def get_timeline(
        source: Optional[str] = None,
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        confidence: Optional[str] = None,
        include_low: bool = False,
        deleted: Optional[bool] = None,
        recovered: Optional[bool] = None,
        q: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        order: str = "desc",
        debug: bool = False
    ):
        start_ts = from_ts or from_date
        end_ts = to_ts or to_date
        with get_db() as db:
            return execute_timeline_query(
                db=db,
                category=category,
                source_app=source,
                source_type=event_type,
                confidence=confidence,
                include_low=include_low,
                from_ts=start_ts,
                to_ts=end_ts,
                q=q,
                deleted=deleted,
                recovered=recovered,
                limit=limit,
                offset=offset,
                order=order,
                debug=debug
            )

    @app.get("/api/timeline/{event_id}")
    def get_timeline_event(event_id: str, debug: bool = False):
        with get_db() as db:
            event = db.get_record("timeline_events", "id", event_id)
            if not event: raise HTTPException(404, detail="Event not found")
            return sanitize_and_standardize_event(event, include_raw_json=debug)

    @app.get("/api/cases/{case_id}/{exhibit_id}/timeline")
    def get_case_timeline(
        case_id: str,
        exhibit_id: str,
        category: Optional[str] = None,
        source_app: Optional[str] = None,
        source_type: Optional[str] = None,
        confidence: Optional[str] = None,
        include_low: bool = False,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        deleted: Optional[bool] = None,
        recovered: Optional[bool] = None,
        q: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        order: str = "desc",
        debug: bool = False
    ):
        with get_db_for(case_id, exhibit_id) as db:
            return execute_timeline_query(
                db=db,
                category=category,
                source_app=source_app,
                source_type=source_type,
                confidence=confidence,
                include_low=include_low,
                from_ts=from_ts,
                to_ts=to_ts,
                q=q,
                deleted=deleted,
                recovered=recovered,
                limit=limit,
                offset=offset,
                order=order,
                debug=debug
            )

    @app.get("/api/cases/{case_id}/{exhibit_id}/timeline/summary")
    def get_case_timeline_summary(case_id: str, exhibit_id: str):
        sum_path = exhibit_root.parent.parent / case_id / exhibit_id / "derived" / "timeline_summary.json"
        if sum_path.exists():
            try:
                with open(sum_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        with get_db_for(case_id, exhibit_id) as db:
            events = db.query("timeline_events", limit=100000)
            counts_by_category = {}
            counts_by_source_app = {}
            counts_by_source_type = {}
            counts_by_confidence = {}
            counts_by_day = {}
            
            for e in events:
                cat = e.get("category") or "unknown"
                counts_by_category[cat] = counts_by_category.get(cat, 0) + 1
                
                app = e.get("source_app") or "unknown"
                counts_by_source_app[app] = counts_by_source_app.get(app, 0) + 1
                
                stype = e.get("source_type") or "unknown"
                counts_by_source_type[stype] = counts_by_source_type.get(stype, 0) + 1
                
                conf = e.get("confidence") or "high"
                counts_by_confidence[conf] = counts_by_confidence.get(conf, 0) + 1
                
                ts = e.get("timestamp")
                if ts:
                    day_str = ts.split("T")[0]
                    counts_by_day[day_str] = counts_by_day.get(day_str, 0) + 1
            
            return {
                "case_id": case_id,
                "exhibit_id": exhibit_id,
                "total_events": len(events),
                "counts_by_category": counts_by_category,
                "counts_by_source_app": counts_by_source_app,
                "counts_by_source_type": counts_by_source_type,
                "counts_by_confidence": counts_by_confidence,
                "counts_by_day": counts_by_day,
                "dual_lane_sources": {},
                "missing_sources": [],
                "warnings": []
            }

    @app.get("/api/cases/{case_id}/{exhibit_id}/timeline/{event_id}")
    def get_case_timeline_event(case_id: str, exhibit_id: str, event_id: str, debug: bool = False):
        with get_db_for(case_id, exhibit_id) as db:
            event = db.get_record("timeline_events", "id", event_id)
            if not event: raise HTTPException(404, detail="Event not found")
            return sanitize_and_standardize_event(event, include_raw_json=debug)

    @app.get("/api/cases/{case_id}/{exhibit_id}/timeline/{event_id}/context")
    def get_case_timeline_context(
        case_id: str,
        exhibit_id: str,
        event_id: str,
        debug: bool = False
    ):
        with get_db_for(case_id, exhibit_id) as db:
            cursor = db.conn.execute("SELECT * FROM timeline_events WHERE id = ?", (event_id,))
            current_row = cursor.fetchone()
            if not current_row:
                raise HTTPException(status_code=404, detail="Event not found")
            current_event = dict(current_row)
            current_ts_sort = current_event["timestamp_sort"]
            
            prev_cursor = db.conn.execute(
                "SELECT * FROM timeline_events WHERE timestamp_sort < ? OR (timestamp_sort = ? AND id < ?) ORDER BY timestamp_sort DESC, id DESC LIMIT 2",
                (current_ts_sort, current_ts_sort, event_id)
            )
            prev_events = [dict(row) for row in prev_cursor.fetchall()]
            prev_events.reverse()
            
            next_cursor = db.conn.execute(
                "SELECT * FROM timeline_events WHERE timestamp_sort > ? OR (timestamp_sort = ? AND id > ?) ORDER BY timestamp_sort ASC, id ASC LIMIT 2",
                (current_ts_sort, current_ts_sort, event_id)
            )
            next_events = [dict(row) for row in next_cursor.fetchall()]
            
            return {
                "previous": [sanitize_and_standardize_event(e, include_raw_json=debug) for e in prev_events],
                "current": sanitize_and_standardize_event(current_event, include_raw_json=debug),
                "next": [sanitize_and_standardize_event(e, include_raw_json=debug) for e in next_events]
            }

    @app.get("/api/cases/{case_id}/{exhibit_id}/leads")
    def get_case_leads(
        case_id: str,
        exhibit_id: str,
        severity: Optional[str] = None,
        confidence: Optional[str] = None,
        category: Optional[str] = None,
        rule_id: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ):
        with get_db_for(case_id, exhibit_id) as db:
            where_clauses = ["case_id = ?", "exhibit_id = ?"]
            params = [case_id, exhibit_id]
            
            if severity:
                where_clauses.append("severity = ?")
                params.append(severity.lower())
            if confidence:
                where_clauses.append("confidence = ?")
                params.append(confidence.lower())
            if category:
                where_clauses.append("category = ?")
                params.append(category.lower())
            if rule_id:
                where_clauses.append("rule_id = ?")
                params.append(rule_id)
            if q:
                where_clauses.append("(title LIKE ? OR summary LIKE ? OR suggested_question LIKE ?)")
                q_param = f"%{q}%"
                params.extend([q_param, q_param, q_param])
                
            where_sql = " AND ".join(where_clauses)
            query = f"SELECT * FROM questioning_leads WHERE {where_sql} LIMIT ? OFFSET ?"
            cursor = db.conn.execute(query, params + [limit, offset])
            rows = [dict(row) for row in cursor.fetchall()]
            
            for row in rows:
                try:
                    row["source_apps"] = json.loads(row["source_apps"])
                except Exception:
                    row["source_apps"] = []
                try:
                    row["event_ids"] = json.loads(row["event_ids"])
                except Exception:
                    row["event_ids"] = []
                    
            return {"leads": rows}

    @app.get("/api/cases/{case_id}/{exhibit_id}/leads/summary")
    def get_case_leads_summary(case_id: str, exhibit_id: str):
        with get_db_for(case_id, exhibit_id) as db:
            total = db.conn.execute(
                "SELECT COUNT(*) FROM questioning_leads WHERE case_id = ? AND exhibit_id = ?",
                (case_id, exhibit_id)
            ).fetchone()[0]
            
            severity_rows = db.conn.execute(
                "SELECT severity, COUNT(*) FROM questioning_leads WHERE case_id = ? AND exhibit_id = ? GROUP BY severity",
                (case_id, exhibit_id)
            ).fetchall()
            by_severity = {r[0]: r[1] for r in severity_rows}
            
            rule_rows = db.conn.execute(
                "SELECT rule_id, COUNT(*) FROM questioning_leads WHERE case_id = ? AND exhibit_id = ? GROUP BY rule_id",
                (case_id, exhibit_id)
            ).fetchall()
            by_rule = {r[0]: r[1] for r in rule_rows}
            
            cat_rows = db.conn.execute(
                "SELECT category, COUNT(*) FROM questioning_leads WHERE case_id = ? AND exhibit_id = ? GROUP BY category",
                (case_id, exhibit_id)
            ).fetchall()
            by_category = {r[0]: r[1] for r in cat_rows}
            
            critical_count = by_severity.get("critical", 0)
            high_count = by_severity.get("high", 0)
            
            created_row = db.conn.execute(
                "SELECT created_at FROM questioning_leads WHERE case_id = ? AND exhibit_id = ? ORDER BY created_at DESC LIMIT 1",
                (case_id, exhibit_id)
            ).fetchone()
            generated_at = created_row[0] if created_row else datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            return {
                "total": total,
                "by_severity": by_severity,
                "by_rule": by_rule,
                "by_category": by_category,
                "critical_count": critical_count,
                "high_count": high_count,
                "generated_at": generated_at,
                "disclaimer": "Questioning leads are automatically generated investigative prompts based on extracted artifacts. They are not forensic conclusions."
            }

    @app.get("/api/cases/{case_id}/{exhibit_id}/leads/{lead_id}")
    def get_case_lead_detail(case_id: str, exhibit_id: str, lead_id: str):
        with get_db_for(case_id, exhibit_id) as db:
            row = db.conn.execute(
                "SELECT * FROM questioning_leads WHERE case_id = ? AND exhibit_id = ? AND lead_id = ?",
                (case_id, exhibit_id, lead_id)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
                
            row_dict = dict(row)
            try:
                row_dict["source_apps"] = json.loads(row_dict["source_apps"])
            except Exception:
                row_dict["source_apps"] = []
            try:
                row_dict["event_ids"] = json.loads(row_dict["event_ids"])
            except Exception:
                row_dict["event_ids"] = []
                
            return row_dict

    @app.get("/api/cases/{case_id}/{exhibit_id}/leads/{lead_id}/events")
    def get_case_lead_events(case_id: str, exhibit_id: str, lead_id: str):
        with get_db_for(case_id, exhibit_id) as db:
            row = db.conn.execute(
                "SELECT event_ids FROM questioning_leads WHERE case_id = ? AND exhibit_id = ? AND lead_id = ?",
                (case_id, exhibit_id, lead_id)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
                
            try:
                event_ids = json.loads(row[0])
            except Exception:
                event_ids = []
                
            if not event_ids:
                return []
                
            placeholders = ",".join("?" for _ in event_ids)
            query = f"SELECT * FROM timeline_events WHERE id IN ({placeholders})"
            cursor = db.conn.execute(query, event_ids)
            events = [dict(r) for r in cursor.fetchall()]
            
            return [sanitize_and_standardize_event(e, include_raw_json=False) for e in events]

    @app.get("/api/timeline/{event_id}/context")
    def get_timeline_event_context_compat(event_id: str, debug: bool = False):
        return get_case_timeline_context(case_id=case_id, exhibit_id=exhibit_id, event_id=event_id, debug=debug)

    @app.get("/api/messages")
    def get_msgs(
        app_filter: str = Query(None, alias="app"),
        q: str = None, from_date: str = None, to_date: str = None,
        deleted: bool = None, recovered: bool = None,
        limit: int = 100, offset: int = 0,
    ):
        with get_db() as db:
            filters = {}
            if app_filter: filters["app"] = app_filter
            if deleted: filters["deleted_status"] = "deleted_marker"
            if recovered: filters["recovered_status"] = "recovered"
            msgs = db.query("messages", filters=filters, limit=limit, offset=offset)
            if q:
                q_lower = q.lower()
                msgs = [m for m in msgs if q_lower in (m.get("body") or "").lower()]
            total = db.count("messages", filters=filters)
            return {"messages": msgs, "total": total}

    @app.get("/api/calls")
    def get_calls(source: str = None, limit: int = 100, offset: int = 0):
        with get_db() as db:
            filters = {"source": source} if source else {}
            return {"calls": db.query("calls", filters=filters, limit=limit, offset=offset)}

    @app.get("/api/contacts")
    def get_contacts(limit: int = 100, offset: int = 0):
        with get_db() as db:
            return {"contacts": db.query("contacts", limit=limit, offset=offset)}

    @app.get("/api/media")
    def get_media(source_app: str = None, limit: int = 100, offset: int = 0):
        with get_db() as db:
            filters = {"source_app": source_app} if source_app else {}
            return {"media": db.query("media", filters=filters, limit=limit, offset=offset)}

    @app.get("/api/locations")
    def get_locations(limit: int = 100, offset: int = 0):
        with get_db() as db:
            return {"locations": db.query("locations", limit=limit, offset=offset),
                    "total": db.count("locations")}

    @app.get("/api/apps")
    def get_apps(limit: int = 100, offset: int = 0):
        with get_db() as db:
            return {"apps": db.query("apps", limit=limit, offset=offset, order_by="app_name ASC"),
                    "total": db.count("apps")}

    @app.get("/api/accounts")
    def get_accounts(limit: int = 100, offset: int = 0):
        with get_db() as db:
            return {"accounts": db.query("accounts", limit=limit, offset=offset),
                    "total": db.count("accounts")}

    @app.get("/api/network")
    def get_network(limit: int = 100, offset: int = 0):
        with get_db() as db:
            return {"network_events": db.query("network_events", limit=limit, offset=offset),
                    "total": db.count("network_events")}

    @app.get("/api/system")
    def get_system(severity: str = None, limit: int = 100, offset: int = 0):
        with get_db() as db:
            filters = {"severity": severity} if severity else {}
            return {"system_events": db.query("system_events", filters=filters, limit=limit, offset=offset),
                    "total": db.count("system_events", filters=filters if filters else None)}

    @app.get("/api/integrity")
    def get_integrity():
        with get_db() as db:
            return {"hashes": db.query("hashes", limit=1000), "audits": db.query("audit_events", limit=1000)}

    @app.get("/api/browser-history")
    def get_browser_history(browser: str = None, limit: int = 100, offset: int = 0):
        with get_db() as db:
            filters = {"browser": browser} if browser else {}
            return {
                "history": db.query("browser_history", filters=filters if filters else None, limit=limit, offset=offset),
                "total": db.count("browser_history", filters=filters if filters else None)
            }

    @app.get("/api/browser-searches")
    def get_browser_searches(browser: str = None, limit: int = 100, offset: int = 0):
        with get_db() as db:
            filters = {"browser": browser} if browser else {}
            return {
                "searches": db.query("browser_searches", filters=filters if filters else None, limit=limit, offset=offset),
                "total": db.count("browser_searches", filters=filters if filters else None)
            }

    @app.get("/api/browser-downloads")
    def get_browser_downloads(browser: str = None, limit: int = 100, offset: int = 0):
        with get_db() as db:
            filters = {"browser": browser} if browser else {}
            return {
                "downloads": db.query("browser_downloads", filters=filters if filters else None, limit=limit, offset=offset),
                "total": db.count("browser_downloads", filters=filters if filters else None)
            }

    @app.get("/api/search")
    def search_all(q: str):
        with get_db() as db:
            return {"results": search_evidence(db, q)}

    @app.post("/api/export-report")
    def export_report():
        with get_db() as db:
            path = export_html_report(db, exhibit_root, case_id, exhibit_id)
            return {"status": "success", "path": str(path)}

    @app.post("/api/verify-hashes")
    def verify_hashes_endpoint():
        return verify_case_hashes(exhibit_root)

    # ── Intake & Examiner Metadata Endpoints ──

    @app.get("/api/intake-status")
    def intake_status():
        with get_db() as db:
            count = db.count("examiner_info")
            return {"complete": count > 0}

    @app.get("/api/examiner")
    def get_examiner():
        with get_db() as db:
            rows = db.query("examiner_info", limit=1)
            return rows[0] if rows else {}

    @app.put("/api/examiner")
    def update_examiner(payload: ExaminerInfoPayload):
        with get_db() as db:
            now = datetime.utcnow().isoformat() + "Z"
            record = {
                "id": "examiner_primary",
                "name": payload.name,
                "badge_id": payload.badge_id,
                "rank_title": payload.rank_title,
                "agency": payload.agency,
                "email": payload.email,
                "phone": payload.phone,
                "notes": payload.notes,
                "updated_at": now,
            }
            db.insert_record("examiner_info", record)
            return {"status": "saved", "updated_at": now}

    @app.get("/api/chain-of-custody")
    def get_chain_of_custody():
        with get_db() as db:
            rows = db.query("chain_of_custody", limit=1000, order_by="entry_index ASC")
            return {"entries": rows, "total": db.count("chain_of_custody")}

    @app.post("/api/chain-of-custody")
    def add_chain_of_custody(payload: ChainOfCustodyPayload):
        with get_db() as db:
            now = datetime.utcnow().isoformat() + "Z"
            existing_count = db.count("chain_of_custody")
            entry_id = hashlib.sha256(f"coc:{existing_count}:{now}".encode()).hexdigest()[:16]
            record = {
                "id": entry_id,
                "entry_index": existing_count + 1,
                "timestamp": payload.timestamp,
                "action": payload.action,
                "performed_by": payload.performed_by,
                "received_by": payload.received_by,
                "location": payload.location,
                "evidence_condition": payload.evidence_condition,
                "notes": payload.notes,
                "created_at": now,
            }
            db.insert_record("chain_of_custody", record)
            return {"status": "added", "id": entry_id, "entry_index": existing_count + 1}

    @app.delete("/api/chain-of-custody/{entry_id}")
    def delete_chain_of_custody(entry_id: str):
        with get_db() as db:
            existing = db.get_record("chain_of_custody", "id", entry_id)
            if not existing:
                raise HTTPException(404, "Chain of custody entry not found")
            db.delete_record("chain_of_custody", "id", entry_id)
            return {"status": "deleted", "id": entry_id}

    @app.get("/api/evidence-metadata")
    def get_evidence_metadata():
        with get_db() as db:
            rows = db.query("evidence_metadata", limit=1)
            return rows[0] if rows else {}

    @app.put("/api/evidence-metadata")
    def update_evidence_metadata(payload: EvidenceMetadataPayload):
        with get_db() as db:
            now = datetime.utcnow().isoformat() + "Z"
            record = {
                "id": "evidence_primary",
                "storage_location": payload.storage_location,
                "evidence_bag_tag": payload.evidence_bag_tag,
                "seizure_date": payload.seizure_date,
                "seizure_location": payload.seizure_location,
                "seizure_authority": payload.seizure_authority,
                "warrant_number": payload.warrant_number,
                "acquisition_tool": payload.acquisition_tool,
                "acquisition_tool_version": payload.acquisition_tool_version,
                "notes": payload.notes,
                "updated_at": now,
            }
            db.insert_record("evidence_metadata", record)
            return {"status": "saved", "updated_at": now}
        
    return app
