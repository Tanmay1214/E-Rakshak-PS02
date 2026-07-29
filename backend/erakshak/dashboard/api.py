from __future__ import annotations
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from .db import DashboardDB
from .timeline_builder import build_evidence_index
from .search import search_evidence
from .integrity import verify_case_hashes
from .report_export import export_html_report
import hashlib


class ExaminerInfoPayload(BaseModel):
    name: str
    badge_id: Optional[str] = None
    rank_title: Optional[str] = None
    agency: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

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
            return {
                "case_id": case_rec.get("case_id", case_id),
                "exhibit_id": case_rec.get("exhibit_id", exhibit_id),
                "case_info": case_rec,
                "device_info": dev_rec,
                "counts": counts,
            }

    @app.get("/api/device")
    def device_info():
        with get_db() as db:
            dev = db.query("device_info", limit=1)
            return dev[0] if dev else {}

    @app.get("/api/timeline")
    def get_timeline(
        source: str = None, category: str = None, event_type: str = None,
        from_date: str = None, to_date: str = None,
        deleted: bool = None, recovered: bool = None,
        q: str = None, limit: int = 100, offset: int = 0,
    ):
        with get_db() as db:
            filters = {}
            if source: filters["source_app"] = source
            if category: filters["category"] = category
            if event_type: filters["event_type"] = event_type
            if deleted: filters["deleted_status"] = "deleted_marker"
            if recovered: filters["recovered_status"] = "recovered"
            events = db.query("timeline_events", filters=filters, limit=limit, offset=offset)
            # Additional text filter on q
            if q:
                q_lower = q.lower()
                events = [e for e in events if q_lower in (e.get("summary") or "").lower()
                          or q_lower in (e.get("title") or "").lower()]
            total = db.count("timeline_events", filters=filters)
            return {"events": events, "total": total}

    @app.get("/api/timeline/{event_id}")
    def get_timeline_event(event_id: str):
        with get_db() as db:
            event = db.get_record("timeline_events", "id", event_id)
            if not event: raise HTTPException(404)
            return event

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
