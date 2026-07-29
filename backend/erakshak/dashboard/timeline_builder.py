from __future__ import annotations
import logging
from pathlib import Path
from datetime import datetime
from .db import DashboardDB
from .case_loader import CaseDashboardLoader
from .normalizer import EvidenceNormalizer
from .models import CaseInfo, DeviceInfo, AuditEvent

logger = logging.getLogger(__name__)

def build_evidence_index(exhibit_root: Path, case_id: str, exhibit_id: str) -> dict:
    """Build or rebuild the evidence_index.db from case folder outputs.

    Idempotent: drops and recreates all tables on each run.
    Never modifies files outside derived/ and reports/.
    """
    exhibit_root = Path(exhibit_root)
    derived_dir = exhibit_root / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    db_path = derived_dir / "evidence_index.db"
    db = DashboardDB(db_path)
    db.clear_all()

    loader = CaseDashboardLoader(exhibit_root)
    norm = EvidenceNormalizer(loader)

    # ── Normalize all sources ─────────────────────────────────────────
    device_info, _ = norm.normalize_device()
    device_info.case_id = case_id
    device_info.exhibit_id = exhibit_id

    apps, app_evs = norm.normalize_apps()
    accounts, acc_evs = norm.normalize_accounts()
    sms, sms_evs = norm.normalize_sms()
    calls, call_evs = norm.normalize_calls()
    contacts, contact_evs = norm.normalize_contacts()
    media, media_evs = norm.normalize_media()
    net_evs, net_timeline = norm.normalize_network()
    sys_evs, sys_timeline = norm.normalize_system()
    wa_msgs, wa_evs = norm.normalize_whatsapp()
    tg_msgs, tg_evs = norm.normalize_telegram()
    sig_msgs, sig_evs = norm.normalize_signal()

    hashes, audits = norm.normalize_integrity()
    locations, loc_evs = norm.normalize_locations()
    browser_hist, browser_srch, browser_dl, browser_evs = norm.normalize_browser_history()

    # Merge all timeline events and messages
    timeline_events = (app_evs + acc_evs + sms_evs + call_evs
                       + contact_evs + media_evs + net_timeline
                       + sys_timeline + wa_evs + tg_evs + sig_evs
                       + loc_evs + browser_evs)
    messages = sms + wa_msgs + tg_msgs + sig_msgs

    # ── Insert into database ──────────────────────────────────────────
    db.insert_batch("apps", [a.__dict__ for a in apps])
    db.insert_batch("accounts", [a.__dict__ for a in accounts])
    db.insert_batch("messages", [m.__dict__ for m in messages])
    db.insert_batch("calls", [c.__dict__ for c in calls])
    db.insert_batch("contacts", [c.__dict__ for c in contacts])
    db.insert_batch("media", [m.__dict__ for m in media])
    db.insert_batch("network_events", [n.__dict__ for n in net_evs])
    db.insert_batch("system_events", [s.__dict__ for s in sys_evs])
    db.insert_batch("locations", [l.__dict__ for l in locations])
    db.insert_batch("browser_history", [h.__dict__ for h in browser_hist])
    db.insert_batch("browser_searches", [s.__dict__ for s in browser_srch])
    db.insert_batch("browser_downloads", [d.__dict__ for d in browser_dl])
    db.insert_batch("timeline_events", [t.__dict__ for t in timeline_events])
    db.insert_batch("hashes", [h.__dict__ for h in hashes])
    db.insert_batch("audit_events", [a.__dict__ for a in audits])

    counts = db.get_counts()

    # ── Case info record ──────────────────────────────────────────────
    case_info = CaseInfo(
        case_id=case_id,
        exhibit_id=exhibit_id,
        case_folder=str(exhibit_root),
        dashboard_indexed_at=datetime.utcnow().isoformat() + "Z",
        total_events=counts.get("timeline_events", 0),
        total_messages=counts.get("messages", 0),
        total_calls=counts.get("calls", 0),
        total_contacts=counts.get("contacts", 0),
        total_media=counts.get("media", 0),
        total_apps=counts.get("apps", 0),
        total_locations=counts.get("locations", 0),
        total_accounts=counts.get("accounts", 0),
    )

    db.insert_record("device_info", device_info.__dict__)
    db.insert_record("case_info", case_info.__dict__)

    # Indexing audit event
    db.insert_record("audit_events", AuditEvent(
        id=norm.generate_id("audit", 0, case_info.dashboard_indexed_at, "indexed"),
        timestamp=case_info.dashboard_indexed_at,
        action="dashboard_index_build",
        result="success",
    ).__dict__)

    logger.info("Evidence index built: %s events, %s messages, %s calls, %s locations, %s browser records",
                counts.get("timeline_events", 0),
                counts.get("messages", 0),
                counts.get("calls", 0),
                counts.get("locations", 0),
                counts.get("browser_history", 0))

    return {
        "status": "success",
        "db_path": str(db_path),
        "counts": counts,
        # Flat keys for CLI/test convenience
        "total_events": counts.get("timeline_events", 0),
        "total_messages": counts.get("messages", 0),
        "total_calls": counts.get("calls", 0),
        "total_contacts": counts.get("contacts", 0),
        "total_media": counts.get("media", 0),
        "total_apps": counts.get("apps", 0),
        "total_locations": counts.get("locations", 0),
        "total_accounts": counts.get("accounts", 0),
        "total_browser_history": counts.get("browser_history", 0),
        "total_browser_searches": counts.get("browser_searches", 0),
        "total_browser_downloads": counts.get("browser_downloads", 0),
    }
