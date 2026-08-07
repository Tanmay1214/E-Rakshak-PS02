"""Watchlist and Questioning Leads Engine for E-RAKSHAK."""

import os
import json
import hashlib
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Default watchlist configuration
DEFAULT_WATCHLIST = {
    "keywords": [
        "otp", "apk", "payment", "qr", "bank", "loan", "kyc", "mule", "refund", "upi", 
        "screen sharing", "remote access", "anydesk", "teamviewer", "fake", "challan", "pnb", "pm kisan", "rto"
    ],
    "phone_numbers": [],
    "emails": [],
    "package_names": [
        "com.anydesk.anydeskandroid", "com.teamviewer.host.market", "com.teamviewer.quicksupport.market"
    ],
    "domains": [],
    "file_names": [],
    "location_keywords": [
        "varachha", "katargam", "udhna", "limbayat", "pandesara", "adajan", "rander", "athwalines", "vesu", "ring road", "textile market"
    ],
    "payment_keywords": [
        "payment", "qr", "upi", "paytm", "gpay", "phonepe", "bank", "loan", "refund"
    ],
    "apk_keywords": [
        "apk", "install", "sideload", "unknown source"
    ],
    "bad_message_keywords": [
        # Phishing / scam indicators
        "urgent", "account locked", "verify", "click here",
        "prize", "winner", "suspend", "congratulations",
        "act now", "limited time", "expire", "confirm your",
        # Racial / ethnic slurs
        "nigger", "nigga", "chink", "gook", "spic", "kike",
        "wetback", "coon", "darkie", "paki", "beaner",
        "cracker", "honky", "gringo", "raghead", "towelhead",
        "chinky", "negro",
        # Profanity / abuse
        "fuck", "bitch", "asshole", "bastard", "cunt",
        "motherfucker", "dickhead", "whore", "slut",
        "retard", "dumbass", "piece of shit",
        # Threats / violence
        "kill you", "i will kill", "gonna kill",
        "murder", "stab", "shoot you", "beat you",
        "rape", "molest", "assault", "attack you",
        "bomb", "blow up", "burn alive",
        "die", "death threat", "end your life",
        # Harassment / intimidation
        "stalk", "harass", "blackmail", "extort",
        "leak your", "expose you", "ruin your life",
        "send nudes", "nude pics", "revenge porn",
        "doxx", "swat",
        # Hate speech
        "go back to your country", "terrorist",
        "subhuman", "vermin", "filth", "scum",
        "gas chamber", "lynch",
        # Exploitation / grooming
        "don't tell anyone", "keep this secret",
        "send me photos", "how old are you",
        "come alone", "meet me secretly",
        # Substance / illegal
        "drugs", "maal", "ganja", "cocaine", "heroin",
        "meth", "deal", "supply", "contraband"
    ]
}

def load_watchlist(case_folder: Path, custom_path: Optional[str] = None) -> Dict[str, List[str]]:
    """Load custom watchlist or create/use default configuration."""
    watchlist_dir = case_folder / "config"
    watchlist_file = watchlist_dir / "watchlist.json"
    
    if custom_path:
        custom_p = Path(custom_path)
        if custom_p.is_file():
            try:
                with open(custom_p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    if watchlist_file.is_file():
        try:
            with open(watchlist_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
            
    # Ensure config dir exists and write default watchlist
    watchlist_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(watchlist_file, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_WATCHLIST, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
        
    return DEFAULT_WATCHLIST

def generate_lead_id(case_id: str, exhibit_id: str, rule_id: str, event_ids: List[str], title: str) -> str:
    """Generate stable lead ID using SHA-256."""
    sorted_events = ",".join(sorted(event_ids))
    norm_title = title.strip().lower()
    input_str = f"{case_id}:{exhibit_id}:{rule_id}:{sorted_events}:{norm_title}"
    sha256 = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
    return f"lead_{sha256[:16]}"

def run_leads_engine(
    case_folder_path: str,
    case_id: str,
    exhibit_id: str,
    recent_days: int = 7,
    from_datetime: Optional[str] = None,
    to_datetime: Optional[str] = None,
    watchlist_path: Optional[str] = None,
    min_severity: str = "medium",
    rebuild: bool = False,
    flag_mode: str = "exact",
    ai_model: str = "all-MiniLM-L6-v2"
) -> Dict[str, Any]:
    """Execute the Level 2 questioning leads rules engine and save leads."""
    case_folder = Path(case_folder_path).resolve()
    db_path = case_folder / "derived" / "evidence_index.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"evidence_index.db not found at {db_path}")

    # Load watchlist
    watchlist = load_watchlist(case_folder, watchlist_path)
    
    # 1. Fetch timeline events
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Resolve timeline range limits
    from erakshak.dashboard.time_utils import resolve_timeline_range
    range_info = resolve_timeline_range(
        recent_days=recent_days,
        from_date=None,
        to_date=None,
        timezone_name="Asia/Kolkata",
        from_datetime=from_datetime,
        to_datetime=to_datetime
    )
    
    from_secs = int(range_info["from_dt"].timestamp() * 1000)
    to_secs = int(range_info["to_dt"].timestamp() * 1000)
    
    query = "SELECT * FROM timeline_events WHERE timestamp_sort >= ? AND timestamp_sort <= ?"
    events_raw = conn.execute(query, (from_secs, to_secs)).fetchall()
    events = [dict(row) for row in events_raw]
    
    leads: List[Dict[str, Any]] = []
    
    # Define severity ranking to filter out low severities
    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    min_rank = severity_rank.get(min_severity.lower(), 2)
    
    # helper to check if text contains watchlist term
    def contains_any(text: Optional[str], terms: List[str]) -> Tuple[bool, Optional[str]]:
        if not text:
            return False, None
        text_lower = text.lower()
        for term in terms:
            if term.lower() in text_lower:
                return True, term
        return False, None

    # Normalization helper for phone numbers
    def normalize_phone(num: Optional[str]) -> Optional[str]:
        if not num:
            return None
        # Remove common characters
        clean = "".join(c for c in num if c.isdigit())
        if len(clean) > 10:
            clean = clean[-10:] # get last 10 digits
        return clean if clean else None

    # Pre-filter lists of events for optimization
    call_events = [e for e in events if e.get("event_type") == "phone_call" or (e.get("source_app") or "").lower() in ("phone", "calls")]
    message_events = [e for e in events if e.get("category") == "messages" or (e.get("source_app") or "").lower() in ("sms", "whatsapp", "telegram", "signal")]
    location_events = [e for e in events if e.get("category") == "locations" or e.get("event_type") == "location_update"]
    media_events = [e for e in events if e.get("category") == "media" or e.get("event_type") == "media_captured" or e.get("media_path")]
    browser_events = [e for e in events if e.get("category") == "browser" or (e.get("source_app") or "").lower() in ("chrome", "browser")]

    # -------------------------------------------------------------
    # RULE 1: deleted_message_near_call (Severity: high)
    # -------------------------------------------------------------
    deleted_msgs = [e for e in message_events if e.get("deleted_status") or e.get("deleted") or (e.get("summary") and "This message was deleted" in e["summary"])]
    if deleted_msgs and call_events:
        for call in call_events:
            call_time = call["timestamp_sort"]
            matched_msgs = [m for m in deleted_msgs if abs(m["timestamp_sort"] - call_time) <= 15 * 60 * 1000]
            if matched_msgs:
                event_ids = [call["id"]] + [m["id"] for m in matched_msgs]
                title = "Deleted Message Near Call Activity"
                time_starts = min(e["timestamp_sort"] for e in matched_msgs + [call])
                time_ends = max(e["timestamp_sort"] for e in matched_msgs + [call])
                
                leads.append({
                    "rule_id": "deleted_message_near_call",
                    "severity": "high",
                    "confidence": "high",
                    "title": title,
                    "summary": f"Deleted message detected within 15 minutes of call with {call.get('sender') or call.get('receiver') or 'unknown'}.",
                    "suggested_question": "Ask why this message was deleted around the time of the call.",
                    "category": "communication",
                    "source_apps": list(set([call["source_app"]] + [m["source_app"] for m in matched_msgs])),
                    "event_ids": event_ids,
                    "evidence_count": len(event_ids),
                    "time_window_start": time_starts,
                    "time_window_end": time_ends
                })

    # -------------------------------------------------------------
    # RULE 2: otp_near_payment_or_media (Severity: high)
    # -------------------------------------------------------------
    # Filter OTP messages
    otp_terms = ["otp", "one time password", "verification code", "code:"]
    otp_msgs = []
    for m in message_events:
        matched, _ = contains_any(m.get("summary"), otp_terms)
        if matched:
            otp_msgs.append(m)
            
    # Filter payment / media / browser events
    payment_terms = watchlist.get("payment_keywords", DEFAULT_WATCHLIST["payment_keywords"])
    qr_terms = ["qr", "payment_qr"]
    
    art_events = []
    for e in events:
        is_pay, _ = contains_any(e.get("summary") or e.get("title"), payment_terms)
        is_qr, _ = contains_any(e.get("summary") or e.get("title") or e.get("file_path"), qr_terms)
        if is_pay or is_qr or e.get("category") == "browser" or e.get("event_type") == "media_captured":
            art_events.append(e)
            
    if otp_msgs and art_events:
        for otp in otp_msgs:
            otp_time = otp["timestamp_sort"]
            matched_arts = [a for a in art_events if abs(a["timestamp_sort"] - otp_time) <= 30 * 60 * 1000 and a["id"] != otp["id"]]
            if matched_arts:
                event_ids = [otp["id"]] + [a["id"] for a in matched_arts]
                title = "OTP Near Payment or Artifact Activity"
                time_starts = min(e["timestamp_sort"] for e in matched_arts + [otp])
                time_ends = max(e["timestamp_sort"] for e in matched_arts + [otp])
                
                leads.append({
                    "rule_id": "otp_near_payment_or_media",
                    "severity": "high",
                    "confidence": "high",
                    "title": title,
                    "summary": f"One-Time Password (OTP) received within 30 minutes of payment, browser, or media activity.",
                    "suggested_question": "Ask what transaction or verification this OTP was used for.",
                    "category": "financial",
                    "source_apps": list(set([otp["source_app"]] + [a["source_app"] for a in matched_arts])),
                    "event_ids": event_ids,
                    "evidence_count": len(event_ids),
                    "time_window_start": time_starts,
                    "time_window_end": time_ends
                })

    # -------------------------------------------------------------
    # RULE 3: suspicious_apk_discussion (Severity: high)
    # -------------------------------------------------------------
    apk_terms = watchlist.get("apk_keywords", DEFAULT_WATCHLIST["apk_keywords"])
    apk_pkgs = watchlist.get("package_names", DEFAULT_WATCHLIST["package_names"])
    matched_apk_evs = []
    
    for e in events:
        matched_term, _ = contains_any(e.get("summary") or e.get("title") or e.get("file_path") or e.get("source_file"), apk_terms)
        matched_pkg = False
        if e.get("source_app") in apk_pkgs or e.get("event_type") in apk_pkgs:
            matched_pkg = True
        if matched_term or matched_pkg:
            matched_apk_evs.append(e)
            
    if matched_apk_evs:
        # Group all matched APK events to prevent noise
        event_ids = [e["id"] for e in matched_apk_evs]
        title = "Suspicious APK Installation or Discussion"
        time_starts = min(e["timestamp_sort"] for e in matched_apk_evs)
        time_ends = max(e["timestamp_sort"] for e in matched_apk_evs)
        
        leads.append({
            "rule_id": "suspicious_apk_discussion",
            "severity": "high",
            "confidence": "high",
            "title": title,
            "summary": f"Discussion, download, or execution of application files (.apk) or screen-sharing packages detected.",
            "suggested_question": "Ask about the source and purpose of this APK/application.",
            "category": "application",
            "source_apps": list(set([e["source_app"] for e in matched_apk_evs])),
            "event_ids": event_ids,
            "evidence_count": len(event_ids),
            "time_window_start": time_starts,
            "time_window_end": time_ends
        })

    # -------------------------------------------------------------
    # RULE 4: repeated_contact_cross_source (Severity: medium/high)
    # -------------------------------------------------------------
    contact_map: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        for field in ["sender", "receiver", "phone_number"]:
            val = e.get(field)
            if val and val != "Me" and any(c.isdigit() for c in val):
                norm = normalize_phone(val)
                if norm and len(norm) >= 10:
                    if norm not in contact_map:
                        contact_map[norm] = []
                    contact_map[norm].append(e)
                    
    for phone, linked_evs in contact_map.items():
        unique_apps = list(set(e["source_app"] for e in linked_evs))
        if len(unique_apps) >= 2:
            event_ids = [e["id"] for e in linked_evs]
            severity = "high" if len(unique_apps) >= 3 else "medium"
            time_starts = min(e["timestamp_sort"] for e in linked_evs)
            time_ends = max(e["timestamp_sort"] for e in linked_evs)
            
            leads.append({
                "rule_id": "repeated_contact_cross_source",
                "severity": severity,
                "confidence": "high",
                "title": f"Contact Active Across Channels: {phone}",
                "summary": f"Phone contact {phone} appeared across multiple source applications: {', '.join(unique_apps)}.",
                "suggested_question": "Ask the relationship with this contact and why it appears across multiple channels.",
                "category": "communication",
                "source_apps": unique_apps,
                "event_ids": event_ids,
                "evidence_count": len(event_ids),
                "time_window_start": time_starts,
                "time_window_end": time_ends
            })

    # -------------------------------------------------------------
    # RULE 5: browser_to_chat_sequence (Severity: medium)
    # -------------------------------------------------------------
    # Match suspicious browser events (matching watchlist keywords or domains) followed by chat within 30 mins
    kw_terms = watchlist.get("keywords", DEFAULT_WATCHLIST["keywords"])
    suspicious_browsers = []
    for b in browser_events:
        matched, _ = contains_any(b.get("summary") or b.get("title"), kw_terms)
        if matched:
            suspicious_browsers.append(b)
            
    if suspicious_browsers and message_events:
        for b in suspicious_browsers:
            b_time = b["timestamp_sort"]
            matched_chats = [m for m in message_events if 0 <= m["timestamp_sort"] - b_time <= 30 * 60 * 1000]
            if matched_chats:
                event_ids = [b["id"]] + [m["id"] for m in matched_chats]
                title = "Suspicious Browser to Chat Sequence"
                time_starts = min(e["timestamp_sort"] for e in matched_chats + [b])
                time_ends = max(e["timestamp_sort"] for e in matched_chats + [b])
                
                leads.append({
                    "rule_id": "browser_to_chat_sequence",
                    "severity": "medium",
                    "confidence": "medium",
                    "title": title,
                    "summary": f"Visited suspicious page followed by active chat communication within 30 minutes.",
                    "suggested_question": "Ask why this web activity was followed by communication activity.",
                    "category": "behavioral",
                    "source_apps": list(set([b["source_app"]] + [m["source_app"] for m in matched_chats])),
                    "event_ids": event_ids,
                    "evidence_count": len(event_ids),
                    "time_window_start": time_starts,
                    "time_window_end": time_ends
                })

    # -------------------------------------------------------------
    # RULE 6: location_near_surat_locality (Severity: medium)
    # -------------------------------------------------------------
    loc_terms = watchlist.get("location_keywords", DEFAULT_WATCHLIST["location_keywords"])
    locality_groups: Dict[str, List[Dict[str, Any]]] = {}
    
    for l in location_events:
        matched, term = contains_any(l.get("summary") or l.get("title"), loc_terms)
        if matched and term:
            norm_term = term.capitalize()
            if norm_term not in locality_groups:
                locality_groups[norm_term] = []
            locality_groups[norm_term].append(l)
            
    for locality, matched_locs in locality_groups.items():
        event_ids = [e["id"] for e in matched_locs]
        time_starts = min(e["timestamp_sort"] for e in matched_locs)
        time_ends = max(e["timestamp_sort"] for e in matched_locs)
        
        leads.append({
            "rule_id": "location_near_surat_locality",
            "severity": "medium",
            "confidence": "high",
            "title": f"Location Activity Near {locality}",
            "summary": f"Device registered GPS coordinates or location markers near the {locality} region.",
            "suggested_question": "Ask why the device was active near this locality at this time.",
            "category": "geographical",
            "source_apps": list(set(e["source_app"] for e in matched_locs)),
            "event_ids": event_ids,
            "evidence_count": len(event_ids),
            "time_window_start": time_starts,
            "time_window_end": time_ends
        })

    # -------------------------------------------------------------
    # RULE 7: late_night_activity_burst (Severity: medium)
    # -------------------------------------------------------------
    # Detect 5 or more events between 11 PM and 5 AM local time, merged overlapping windows
    # Since timestamp in DB is formatted or can be parsed, let's parse using parse_timestamp
    from erakshak.dashboard.time_utils import parse_timestamp
    late_night_evs = []
    for e in events:
        dt = parse_timestamp(e["timestamp"])
        if dt:
            # check hour
            if dt.hour >= 23 or dt.hour < 5:
                late_night_evs.append(e)
                
    # Sort chronologically
    late_night_evs.sort(key=lambda x: x["timestamp_sort"])
    
    # Merge overlapping bursts
    bursts = []
    current_burst = []
    for ev in late_night_evs:
        if not current_burst:
            current_burst.append(ev)
        else:
            # If current event timestamp is within 30 minutes of the start of the current burst
            if ev["timestamp_sort"] - current_burst[0]["timestamp_sort"] <= 30 * 60 * 1000:
                current_burst.append(ev)
            else:
                if len(current_burst) >= 5:
                    bursts.append(current_burst)
                current_burst = [ev]
    if len(current_burst) >= 5:
        bursts.append(current_burst)
        
    for burst in bursts:
        event_ids = [e["id"] for e in burst]
        time_starts = min(e["timestamp_sort"] for e in burst)
        time_ends = max(e["timestamp_sort"] for e in burst)
        
        leads.append({
            "rule_id": "late_night_activity_burst",
            "severity": "medium",
            "confidence": "high",
            "title": "Late Night Activity Burst",
            "summary": f"Detected a burst of {len(event_ids)} device activities between 11 PM and 5 AM within a 30-minute window.",
            "suggested_question": "Ask about the reason for this unusual late-night activity burst.",
            "category": "behavioral",
            "source_apps": list(set(e["source_app"] for e in burst)),
            "event_ids": event_ids,
            "evidence_count": len(event_ids),
            "time_window_start": time_starts,
            "time_window_end": time_ends
        })

    # -------------------------------------------------------------
    # RULE 8: deleted_or_recovered_media (Severity: high)
    # -------------------------------------------------------------
    del_rec_media = [e for e in media_events if e.get("deleted_status") or e.get("deleted") or e.get("recovered_status") or e.get("recovered")]
    if del_rec_media:
        event_ids = [e["id"] for e in del_rec_media]
        time_starts = min(e["timestamp_sort"] for e in del_rec_media)
        time_ends = max(e["timestamp_sort"] for e in del_rec_media)
        
        leads.append({
            "rule_id": "deleted_or_recovered_media",
            "severity": "high",
            "confidence": "high",
            "title": "Deleted or Recovered Media Files",
            "summary": f"Detected {len(event_ids)} media or capture logs that were deleted or recovered.",
            "suggested_question": "Ask about the deleted or recovered media/file and its relevance.",
            "category": "artifact",
            "source_apps": list(set(e["source_app"] for e in del_rec_media)),
            "event_ids": event_ids,
            "evidence_count": len(event_ids),
            "time_window_start": time_starts,
            "time_window_end": time_ends
        })

    # -------------------------------------------------------------
    # RULE 9: same_keyword_multi_source (Severity: medium/high)
    # -------------------------------------------------------------
    for kw in kw_terms:
        matched_kw_evs = []
        for e in events:
            # Look for exact word boundary match or containment
            summary_lower = (e.get("summary") or "").lower()
            title_lower = (e.get("title") or "").lower()
            if kw.lower() in summary_lower or kw.lower() in title_lower:
                matched_kw_evs.append(e)
                
        if matched_kw_evs:
            unique_apps = list(set(e["source_app"] for e in matched_kw_evs))
            if len(unique_apps) >= 2:
                event_ids = [e["id"] for e in matched_kw_evs]
                severity = "high" if len(unique_apps) >= 3 else "medium"
                time_starts = min(e["timestamp_sort"] for e in matched_kw_evs)
                time_ends = max(e["timestamp_sort"] for e in matched_kw_evs)
                
                leads.append({
                    "rule_id": "same_keyword_multi_source",
                    "severity": severity,
                    "confidence": "high",
                    "title": f"Keyword Reference Across Sources: '{kw}'",
                    "summary": f"Watchlist keyword '{kw}' appeared across multiple applications: {', '.join(unique_apps)}.",
                    "suggested_question": "Ask about repeated references to this keyword across multiple sources.",
                    "category": "intelligence",
                    "source_apps": unique_apps,
                    "event_ids": event_ids,
                    "evidence_count": len(event_ids),
                    "time_window_start": time_starts,
                    "time_window_end": time_ends
                })

    # -------------------------------------------------------------
    # RULE 10: high_confidence_fraud_cluster (Severity: critical)
    # -------------------------------------------------------------
    # Sort all events chronologically
    sorted_evs = sorted(events, key=lambda x: x["timestamp_sort"])
    clusters = []
    
    for i, start_ev in enumerate(sorted_evs):
        cluster_evs = [start_ev]
        for next_ev in sorted_evs[i+1:]:
            if next_ev["timestamp_sort"] - start_ev["timestamp_sort"] <= 30 * 60 * 1000:
                cluster_evs.append(next_ev)
            else:
                break
                
        # Validate cluster criteria
        has_msg = any(e.get("category") == "messages" or (e.get("source_app") or "").lower() in ("sms", "whatsapp", "telegram", "signal") for e in cluster_evs)
        has_call_or_sms = any(e.get("event_type") in ("phone_call", "sms_message") for e in cluster_evs)
        
        # Payment keyword matching inside cluster
        has_payment_keyword = False
        for e in cluster_evs:
            is_pay, _ = contains_any(e.get("summary") or e.get("title"), payment_terms)
            is_qr, _ = contains_any(e.get("summary") or e.get("title") or e.get("file_path"), qr_terms)
            if is_pay or is_qr or e.get("category") == "browser" or e.get("event_type") == "media_captured":
                has_payment_keyword = True
                break
                
        if has_msg and has_call_or_sms and has_payment_keyword:
            clusters.append(cluster_evs)
            
    # Merge overlapping clusters
    merged_clusters = []
    for c in clusters:
        if not merged_clusters:
            merged_clusters.append(c)
        else:
            prev = merged_clusters[-1]
            # If the start of current cluster lies before the end of the previous cluster
            if c[0]["timestamp_sort"] <= prev[-1]["timestamp_sort"]:
                # Merge lists, deduplicating events by ID
                seen_ids = set(e["id"] for e in prev)
                for e in c:
                    if e["id"] not in seen_ids:
                        prev.append(e)
                # Resort just to keep it clean
                prev.sort(key=lambda x: x["timestamp_sort"])
            else:
                merged_clusters.append(c)
                
    for cluster in merged_clusters:
        event_ids = [e["id"] for e in cluster]
        time_starts = min(e["timestamp_sort"] for e in cluster)
        time_ends = max(e["timestamp_sort"] for e in cluster)
        
        leads.append({
            "rule_id": "high_confidence_fraud_cluster",
            "severity": "critical",
            "confidence": "high",
            "title": "High Confidence Fraud Cluster",
            "summary": f"Detected a sequence of chat messages, phone/sms activity, and payment or artifact activity within 30 minutes.",
            "suggested_question": "Ask the suspect to explain this sequence of communication, verification, and artifact activity.",
            "category": "intelligence",
            "source_apps": list(set(e["source_app"] for e in cluster)),
            "event_ids": event_ids,
            "evidence_count": len(event_ids),
            "time_window_start": time_starts,
            "time_window_end": time_ends
        })

    # -------------------------------------------------------------
    # RULE 11: advanced_message_flagging (Severity: high)
    # Dual-mode message flagging: exact, fuzzy, or ai semantic
    # -------------------------------------------------------------
    bad_keywords = watchlist.get("bad_message_keywords", DEFAULT_WATCHLIST.get("bad_message_keywords", []))
    if bad_keywords and message_events:
        if flag_mode == "fuzzy":
            # Fuzzy matching via rapidfuzz
            try:
                from rapidfuzz import fuzz
            except ImportError:
                fuzz = None
            if fuzz:
                for msg in message_events:
                    body = msg.get("summary") or msg.get("title") or ""
                    if not body:
                        continue
                    for kw in bad_keywords:
                        score = fuzz.partial_ratio(kw.lower(), body.lower())
                        if score > 85:
                            leads.append({
                                "rule_id": "advanced_message_flagging",
                                "severity": "high",
                                "confidence": "high",
                                "title": f"Suspicious Message (Fuzzy Match: '{kw}')",
                                "summary": f"Message fuzzy-matched suspicious keyword '{kw}' with score {score}. Body preview: {body[:120]}",
                                "suggested_question": f"Ask about the context of this message containing content similar to '{kw}'.",
                                "category": "communication",
                                "source_apps": [msg.get("source_app", "unknown")],
                                "event_ids": [msg["id"]],
                                "evidence_count": 1,
                                "time_window_start": msg["timestamp_sort"],
                                "time_window_end": msg["timestamp_sort"]
                            })
                            break  # One match per message is enough

        elif flag_mode == "ai":
            # AI semantic embedding matching via sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer, util as st_util
                model = SentenceTransformer(ai_model)

                # Compute embeddings for suspicious concepts
                concept_embeddings = model.encode(bad_keywords, convert_to_tensor=True)

                for msg in message_events:
                    body = msg.get("summary") or msg.get("title") or ""
                    if not body or len(body.strip()) < 5:
                        continue
                    msg_embedding = model.encode(body, convert_to_tensor=True)
                    cosine_scores = st_util.cos_sim(msg_embedding, concept_embeddings)[0]
                    max_score = float(cosine_scores.max())
                    best_idx = int(cosine_scores.argmax())
                    if max_score > 0.45:
                        matched_concept = bad_keywords[best_idx]
                        leads.append({
                            "rule_id": "advanced_message_flagging",
                            "severity": "high",
                            "confidence": "high" if max_score > 0.7 else ("medium" if max_score > 0.55 else "low"),
                            "title": f"Suspicious Message (AI Semantic: '{matched_concept}')",
                            "summary": f"Message semantically matched concept '{matched_concept}' with similarity {max_score:.2f}. Body preview: {body[:120]}",
                            "suggested_question": f"Investigate the intent behind this message which semantically relates to '{matched_concept}'.",
                            "category": "communication",
                            "source_apps": [msg.get("source_app", "unknown")],
                            "event_ids": [msg["id"]],
                            "evidence_count": 1,
                            "time_window_start": msg["timestamp_sort"],
                            "time_window_end": msg["timestamp_sort"]
                        })
            except ImportError:
                leads.append({
                    "rule_id": "advanced_message_flagging",
                    "severity": "low",
                    "confidence": "low",
                    "title": "AI Semantic Analysis Unavailable",
                    "summary": "sentence-transformers or torch is not installed. Install them to use AI mode.",
                    "suggested_question": "N/A",
                    "category": "engine",
                    "source_apps": [],
                    "event_ids": [],
                    "evidence_count": 0,
                    "time_window_start": 0,
                    "time_window_end": 0
                })
            except Exception as e:
                leads.append({
                    "rule_id": "advanced_message_flagging",
                    "severity": "low",
                    "confidence": "low",
                    "title": "AI Semantic Analysis Failed",
                    "summary": f"AI analysis encountered an error: {str(e)[:200]}",
                    "suggested_question": "N/A",
                    "category": "engine",
                    "source_apps": [],
                    "event_ids": [],
                    "evidence_count": 0,
                    "time_window_start": 0,
                    "time_window_end": 0
                })

        else:
            # Exact substring match (default behavior)
            for msg in message_events:
                body = msg.get("summary") or msg.get("title") or ""
                if not body:
                    continue
                matched, matched_kw = contains_any(body, bad_keywords)
                if matched:
                    leads.append({
                        "rule_id": "advanced_message_flagging",
                        "severity": "high",
                        "confidence": "high",
                        "title": f"Suspicious Message (Exact Match: '{matched_kw}')",
                        "summary": f"Message contains suspicious keyword '{matched_kw}'. Body preview: {body[:120]}",
                        "suggested_question": f"Ask about the context of this message containing '{matched_kw}'.",
                        "category": "communication",
                        "source_apps": [msg.get("source_app", "unknown")],
                        "event_ids": [msg["id"]],
                        "evidence_count": 1,
                        "time_window_start": msg["timestamp_sort"],
                        "time_window_end": msg["timestamp_sort"]
                    })

    # -------------------------------------------------------------
    # Post-filtering, stable ID generation, disclaimer mapping
    # -------------------------------------------------------------
    final_leads = []
    seen_lead_ids = set()
    
    for lead in leads:
        # 1. Filter out severity less than threshold
        if severity_rank.get(lead["severity"], 2) < min_rank:
            continue
            
        # 2. Skip if event_ids is empty (Rule 11 compliance)
        if not lead["event_ids"]:
            continue
            
        # 3. Generate stable ID (Rule 2 compliance)
        l_id = generate_lead_id(case_id, exhibit_id, lead["rule_id"], lead["event_ids"], lead["title"])
        if l_id in seen_lead_ids:
            continue
        seen_lead_ids.add(l_id)
        
        # 4. Populate mandatory metadata
        lead["lead_id"] = l_id
        lead["case_id"] = case_id
        lead["exhibit_id"] = exhibit_id
        lead["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # 5. Build raw_json safe schema (Rule 7 compliance)
        # Never store bodies or raw secret credentials.
        lead["raw_json"] = json.dumps({
            "rule_explanation": f"Generated by questioning leads rule engine running {lead['rule_id']}.",
            "matched_keywords": [kw for kw in watchlist.get("keywords", []) if contains_any(lead["summary"], [kw])[0]],
            "time_window_start": lead["time_window_start"],
            "time_window_end": lead["time_window_end"],
            "disclaimer": "Questioning leads are automatically generated investigative prompts based on extracted artifacts. They are not forensic conclusions."
        }, ensure_ascii=False)
        
        final_leads.append(lead)

    # -------------------------------------------------------------
    # Save to SQLite db (rebuild / upsert behavior)
    # -------------------------------------------------------------
    if rebuild:
        conn.execute("DELETE FROM questioning_leads WHERE case_id = ? AND exhibit_id = ?", (case_id, exhibit_id))
        
    for lead in final_leads:
        conn.execute("""
            INSERT OR REPLACE INTO questioning_leads (
                lead_id, case_id, exhibit_id, rule_id, severity, confidence, title, summary,
                suggested_question, category, source_apps, event_ids, evidence_count,
                time_window_start, time_window_end, created_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["lead_id"], lead["case_id"], lead["exhibit_id"], lead["rule_id"], lead["severity"], lead["confidence"],
            lead["title"], lead["summary"], lead["suggested_question"], lead["category"],
            json.dumps(lead["source_apps"]), json.dumps(lead["event_ids"]), lead["evidence_count"],
            lead["time_window_start"], lead["time_window_end"], lead["created_at"], lead["raw_json"]
        ))
        
    conn.commit()
    conn.close()

    # -------------------------------------------------------------
    # Export derived JSON and JSONL files
    # -------------------------------------------------------------
    derived_dir = case_folder / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = derived_dir / "questioning_leads.json"
    jsonl_path = derived_dir / "questioning_leads.jsonl"
    
    # Write JSON list
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_leads, f, indent=2, ensure_ascii=False)
        
    # Write JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for lead in final_leads:
            f.write(json.dumps(lead, ensure_ascii=False) + "\n")
            
    return {
        "status": "success",
        "total_generated": len(final_leads),
        "json_path": str(json_path),
        "jsonl_path": str(jsonl_path)
    }
