from __future__ import annotations
import hashlib
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
from .models import (DeviceInfo, App, Account, Message, Call, Contact, Media,
                     NetworkEvent, SystemEvent, TimelineEvent, Hash, AuditEvent,
                     Location, BrowserHistory, BrowserSearch, BrowserDownload)
from .case_loader import CaseDashboardLoader

logger = logging.getLogger(__name__)

class EvidenceNormalizer:
    def __init__(self, loader: CaseDashboardLoader):
        self.loader = loader

    def generate_id(self, source_file: str, row_index: int, timestamp: str, summary: str) -> str:
        s = f"{source_file}:{row_index}:{timestamp}:{summary}"
        return hashlib.sha256(s.encode()).hexdigest()[:16]

    def parse_timestamp(self, ts: Any) -> int:
        if not ts: return 0
        if isinstance(ts, (int, float)):
            # guess epoch
            if ts > 1e11: return int(ts / 1000)
            return int(ts)
        ts_str = str(ts)
        try:
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except ValueError:
            pass
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            return int(dt.timestamp())
        except ValueError:
            pass
        return 0

    def redact_secrets(self, value: str) -> str:
        if not value: return value
        # Pattern for 64-char hex strings
        pattern = re.compile(r'^[0-9a-fA-F]{64}$')
        if pattern.match(value):
            return "<REDACTED>"
        return value

    def normalize_device(self) -> Tuple[DeviceInfo, List[TimelineEvent]]:
        d = DeviceInfo()
        dev_id = self.loader.load_device_identity() or {}
        sw_sum = self.loader.load_software_summary() or {}
        pref = self.loader.load_preflight() or {}

        d.manufacturer = dev_id.get("manufacturer")
        d.brand = dev_id.get("brand")
        d.model = dev_id.get("model")
        d.device = dev_id.get("device")
        d.android_version = sw_sum.get("android_release")
        d.sdk_level = str(sw_sum.get("sdk_level")) if sw_sum.get("sdk_level") else None
        d.security_patch = sw_sum.get("security_patch")
        d.root_access = str(pref.get("root_available")) if "root_available" in pref else None
        d.acquisition_method = pref.get("acquisition_method")
        
        return d, []

    def normalize_apps(self) -> Tuple[List[App], List[TimelineEvent]]:
        apps = []
        events = []
        raw_apps = self.loader.load_installed_apps()
        for i, a in enumerate(raw_apps):
            app = App(
                package_name=a.get("package_name"),
                app_name=a.get("app_name"),
                version_name=a.get("version_name"),
                version_code=str(a.get("version_code")),
                apk_path=a.get("apk_path"),
                install_time=a.get("install_time"),
                last_update_time=a.get("last_update_time"),
                uid=str(a.get("uid")),
                is_system_app=1 if a.get("is_system_app") else 0,
                permissions=json.dumps(a.get("granted_permissions", []))
            )
            apps.append(app)
            if app.install_time:
                events.append(TimelineEvent(
                    id=self.generate_id("apps", i, app.install_time, f"Installed {app.app_name}"),
                    timestamp=app.install_time,
                    timestamp_sort=self.parse_timestamp(app.install_time),
                    source_app=app.package_name,
                    category="apps",
                    event_type="app_installed",
                    title=f"Installed {app.app_name}",
                    confidence="high"
                ))
        return apps, events

    def normalize_accounts(self) -> Tuple[List[Account], List[TimelineEvent]]:
        accounts = []
        raw = self.loader.load_accounts()
        for i, a in enumerate(raw):
            acc = Account(
                id=self.generate_id("accounts", i, "", a.get("name", "")),
                account_name=a.get("name"),
                account_type=a.get("type")
            )
            accounts.append(acc)
        return accounts, []

    def normalize_sms(self) -> Tuple[List[Message], List[TimelineEvent]]:
        messages = []
        events = []
        raw = self.loader.load_sms_messages()
        if not raw:
            raw = self.loader.load_collector_sms()
        
        for i, m in enumerate(raw):
            is_incoming = str(m.get("type")) == "1"
            msg = Message(
                id=self.generate_id("sms", i, str(m.get("date")), m.get("body", "")),
                timestamp=str(m.get("date")),
                timestamp_sort=self.parse_timestamp(m.get("date")),
                app="sms",
                direction="incoming" if is_incoming else "outgoing",
                sender=m.get("address") if is_incoming else "Me",
                receiver="Me" if is_incoming else m.get("address"),
                body=m.get("body")
            )
            if "This message was deleted" in (msg.body or ""):
                msg.deleted_status = "deleted_marker"
                
            messages.append(msg)
            events.append(TimelineEvent(
                id=msg.id,
                timestamp=msg.timestamp,
                timestamp_sort=msg.timestamp_sort,
                source_app="sms",
                category="messages",
                event_type="sms_message",
                direction=msg.direction,
                title=f"SMS {msg.direction}",
                summary=msg.body,
                sender=msg.sender,
                receiver=msg.receiver,
                confidence="high"
            ))
        return messages, events

    def normalize_calls(self) -> Tuple[List[Call], List[TimelineEvent]]:
        calls = []
        events = []
        raw = self.loader.load_call_logs()
        if not raw:
            raw = self.loader.load_collector_calls()
        for i, c in enumerate(raw):
            t = str(c.get("type"))
            direction = "incoming" if t == "1" else "outgoing" if t == "2" else "missed" if t == "3" else "unknown"
            call = Call(
                id=self.generate_id("calls", i, str(c.get("date")), c.get("number", "")),
                timestamp=str(c.get("date")),
                timestamp_sort=self.parse_timestamp(c.get("date")),
                call_type="voice",
                direction=direction,
                from_number=c.get("number") if direction in ("incoming", "missed") else "Me",
                to_number="Me" if direction in ("incoming", "missed") else c.get("number"),
                contact_name=c.get("name"),
                duration_seconds=c.get("duration"),
                app="phone"
            )
            calls.append(call)
            
            # Format display name for timeline events
            display_contact = f"{c.get('name')} ({c.get('number')})" if c.get("name") else c.get("number")
            sender = display_contact if direction in ("incoming", "missed") else "Me"
            receiver = "Me" if direction in ("incoming", "missed") else display_contact
            
            if direction == "incoming":
                title = f"Call from {display_contact}"
            elif direction == "outgoing":
                title = f"Call to {display_contact}"
            elif direction == "missed":
                title = f"Missed call from {display_contact}"
            else:
                title = f"Call {direction}"
                
            events.append(TimelineEvent(
                id=call.id,
                timestamp=call.timestamp,
                timestamp_sort=call.timestamp_sort,
                source_app="phone",
                category="calls",
                event_type="phone_call",
                direction=call.direction,
                title=title,
                summary=f"Duration: {call.duration_seconds}s",
                phone_number=c.get("number"),
                sender=sender,
                receiver=receiver,
                confidence="high"
            ))
        return calls, events

    def normalize_contacts(self) -> Tuple[List[Contact], List[TimelineEvent]]:
        contacts = []
        raw = self.loader.load_contacts()
        if not raw:
            raw = self.loader.load_collector_contacts()
        for i, c in enumerate(raw):
            contact = Contact(
                id=self.generate_id("contacts", i, "", c.get("display_name", "")),
                name=c.get("display_name"),
                phone=c.get("phone") or c.get("number"),
                email=c.get("email"),
                source_app="contacts"
            )
            contacts.append(contact)
        return contacts, []

    def normalize_media(self) -> Tuple[List[Media], List[TimelineEvent]]:
        medias = []
        events = []
        raw = self.loader.load_media_index()
        for i, m in enumerate(raw):
            media = Media(
                id=self.generate_id("media", i, str(m.get("modified_time")), m.get("filename", "")),
                timestamp=str(m.get("modified_time")),
                timestamp_sort=self.parse_timestamp(m.get("modified_time")),
                filename=m.get("filename"),
                mime_type=m.get("mime_type"),
                path=m.get("source_path"),
                size_bytes=m.get("size"),
                sha256=m.get("sha256")
            )
            medias.append(media)
            events.append(TimelineEvent(
                id=media.id,
                timestamp=media.timestamp,
                timestamp_sort=media.timestamp_sort,
                category="media",
                event_type="media_captured",
                title="Media File",
                summary=media.filename,
                media_path=media.path,
                confidence="high"
            ))
        return medias, events

    def normalize_network(self) -> Tuple[List[NetworkEvent], List[TimelineEvent]]:
        events = []
        timeline = []
        raw_sum = self.loader.load_network_summary() or {}
        
        # Create a snapshot event from the network summary
        if raw_sum:
            net_event = NetworkEvent(
                id=self.generate_id("net", 0, "", "network_snapshot"),
                timestamp=None,
                type="network_snapshot",
                source="network_summary",
                ip=raw_sum.get("current_ip"),
                ssid=raw_sum.get("wifi_ssid"),
                carrier=raw_sum.get("mobile_operator"),
                vpn_state=str(raw_sum.get("vpn_active")) if "vpn_active" in raw_sum else None,
                dns=json.dumps(raw_sum.get("dns_servers")) if raw_sum.get("dns_servers") else None,
                raw_json=json.dumps(raw_sum)
            )
            events.append(net_event)
        
        # Parse individual network connections
        raw_conns = self.loader.load_network_connections()
        for i, c in enumerate(raw_conns):
            conn_event = NetworkEvent(
                id=self.generate_id("netconn", i, "", c.get("foreign_address", "")),
                timestamp=None,
                type=c.get("state", "unknown"),
                source=c.get("protocol", "unknown"),
                ip=c.get("foreign_address"),
                raw_json=json.dumps(c)
            )
            events.append(conn_event)
        
        return events, timeline

    def normalize_system(self) -> Tuple[List[SystemEvent], List[TimelineEvent]]:
        sys_events = []
        timeline = []
        raw = self.loader.load_logcat_events()
        for i, e in enumerate(raw):
            sys_e = SystemEvent(
                id=self.generate_id("sys", i, str(e.get("timestamp")), e.get("message", "")),
                timestamp=str(e.get("timestamp")),
                timestamp_sort=self.parse_timestamp(e.get("timestamp")),
                event_type=e.get("category"),
                severity=e.get("log_level"),
                title=e.get("tag"),
                summary=e.get("message")
            )
            sys_events.append(sys_e)
            timeline.append(TimelineEvent(
                id=sys_e.id,
                timestamp=sys_e.timestamp,
                timestamp_sort=sys_e.timestamp_sort,
                category="system",
                event_type=sys_e.event_type,
                title=sys_e.title,
                summary=sys_e.summary,
                confidence="low"
            ))
        return sys_events, timeline

    def normalize_whatsapp(self) -> Tuple[List[Message], List[TimelineEvent]]:
        messages = []
        events = []
        raw = self.loader.load_whatsapp_result()
        if raw and isinstance(raw, dict):
            for chat_id, chat_data in raw.items():
                if isinstance(chat_data, dict) and "messages" in chat_data:
                    msgs = chat_data["messages"]
                    contact_name = chat_data.get("name") or chat_id
                    if isinstance(msgs, dict):
                        for m_id, m in msgs.items():
                            is_from_me = m.get("from_me", False)
                            
                            is_group = "@g.us" in chat_id
                            if is_group:
                                if is_from_me:
                                    sender = "Me"
                                    receiver = contact_name
                                    title = f"WhatsApp Group Message to {contact_name}"
                                else:
                                    actual_sender = m.get("sender") or "Unknown"
                                    sender = f"{actual_sender} ({contact_name})"
                                    receiver = "Me"
                                    title = f"WhatsApp Group Message from {actual_sender} in {contact_name}"
                            else:
                                sender = "Me" if is_from_me else contact_name
                                receiver = contact_name if is_from_me else "Me"
                                title = f"WhatsApp Message from {sender}" if not is_from_me else f"WhatsApp Message to {receiver}"

                            direction = "outgoing" if is_from_me else "incoming"
                            ts = m.get("timestamp") or m.get("date")
                            
                            msg = Message(
                                id=self.generate_id("wa", int(m_id) if m_id.isdigit() else 0, str(ts), m.get("data") or m.get("body") or ""),
                                timestamp=str(ts),
                                timestamp_sort=self.parse_timestamp(ts),
                                app="WhatsApp",
                                chat_id=chat_id,
                                direction=direction,
                                sender=sender,
                                receiver=receiver,
                                body=m.get("data") or m.get("body")
                            )
                            if "[DELETED MESSAGE RECOVERED]" in (msg.body or ""):
                                msg.deleted_status = "recovered"
                                
                            messages.append(msg)
                            events.append(TimelineEvent(
                                id=msg.id,
                                timestamp=msg.timestamp,
                                timestamp_sort=msg.timestamp_sort,
                                source_app="WhatsApp",
                                category="messages",
                                event_type="whatsapp_message",
                                direction=msg.direction,
                                title=title,
                                summary=msg.body,
                                sender=msg.sender,
                                receiver=msg.receiver,
                                confidence="high"
                            ))
        return messages, events

    def normalize_telegram(self) -> Tuple[List[Message], List[TimelineEvent]]:
        messages = []
        events = []
        raw_users = self.loader.load_telegram_users()
        user_map = {str(u.get("uid")): u.get("name", "Unknown") for u in raw_users if "uid" in u}
        
        raw_chats = self.loader.load_telegram_chats()
        chats_map = {str(c.get("uid")): c.get("name", "Unknown Group") for c in raw_chats if "uid" in c}
        
        raw_msgs = self.loader.load_telegram_messages()
        for i, m in enumerate(raw_msgs):
            if "date" not in m: continue
            
            is_out = str(m.get("out")) == "1" or m.get("out") is True
            direction = "outgoing" if is_out else "incoming"
            
            uid = str(m.get("uid", ""))
            
            is_group = uid.startswith("-") or uid in chats_map or uid.replace("-", "") in chats_map
            
            if is_group:
                group_id_abs = uid.replace("-", "")
                group_name = chats_map.get(group_id_abs) or chats_map.get(uid) or f"Group_{uid}"
                if is_out:
                    sender = "Me"
                    receiver = group_name
                    title = f"Telegram Group Message to {group_name}"
                else:
                    sender = group_name
                    receiver = "Me"
                    title = f"Telegram Group Message from {group_name}"
            else:
                contact_name = user_map.get(uid, uid or "Unknown")
                sender = "Me" if is_out else contact_name
                receiver = contact_name if is_out else "Me"
                title = f"Telegram Message from {sender}" if not is_out else f"Telegram Message to {receiver}"

            body = m.get("text") or ""
            
            msg = Message(
                id=self.generate_id("telegram", i, str(m.get("date")), body),
                timestamp=str(m.get("date")),
                timestamp_sort=self.parse_timestamp(m.get("date")),
                app="Telegram",
                direction=direction,
                sender=sender,
                receiver=receiver,
                body=body
            )
            messages.append(msg)
            events.append(TimelineEvent(
                id=msg.id,
                timestamp=msg.timestamp,
                timestamp_sort=msg.timestamp_sort,
                source_app="Telegram",
                category="messages",
                event_type="telegram_message",
                direction=msg.direction,
                title=title,
                summary=msg.body,
                sender=msg.sender,
                receiver=msg.receiver,
                confidence="high"
            ))
        return messages, events

    def normalize_signal(self) -> Tuple[List[Message], List[TimelineEvent]]:
        messages = []
        events = []
        raw_msgs = self.loader.load_signal_messages()
        for i, m in enumerate(raw_msgs):
            if "date" not in m: continue
            
            direction = "outgoing" if m.get("sent") else "incoming"
            contact_name = m.get("contact_name", "Unknown")
            sender = "Me" if direction == "outgoing" else contact_name
            receiver = contact_name if direction == "outgoing" else "Me"
            body = m.get("message") or ""
            
            title = f"Signal Message from {sender}" if direction == "incoming" else f"Signal Message to {receiver}"
            
            msg = Message(
                id=self.generate_id("signal", i, str(m.get("date")), body),
                timestamp=str(m.get("date")),
                timestamp_sort=self.parse_timestamp(m.get("date")),
                app="Signal",
                direction=direction,
                sender=sender,
                receiver=receiver,
                body=body
            )
            messages.append(msg)
            events.append(TimelineEvent(
                id=msg.id,
                timestamp=msg.timestamp,
                timestamp_sort=msg.timestamp_sort,
                source_app="Signal",
                category="messages",
                event_type="signal_message",
                direction=msg.direction,
                title=title,
                summary=msg.body,
                sender=msg.sender,
                receiver=msg.receiver,
                confidence="high"
            ))
        return messages, events


    def normalize_locations(self) -> Tuple[List[Location], List[TimelineEvent]]:
        locations = []
        events = []
        raw = self.loader.load_location_evidence()
        for i, loc in enumerate(raw):
            ts = loc.get("timestamp", "")
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            if lat is None or lon is None:
                continue
            
            source_type = loc.get("source_type", "unknown")
            locality = loc.get("nearest_locality")
            notes = loc.get("notes", "")
            summary_parts = []
            if locality:
                summary_parts.append(locality)
            summary_parts.append(f"{lat:.6f}, {lon:.6f}")
            if notes:
                summary_parts.append(notes)
            
            location = Location(
                id=self.generate_id("loc", i, str(ts), f"{lat},{lon}"),
                timestamp=str(ts) if ts else None,
                timestamp_sort=self.parse_timestamp(ts),
                latitude=float(lat),
                longitude=float(lon),
                accuracy=loc.get("accuracy_meters"),
                source=source_type
            )
            locations.append(location)
            events.append(TimelineEvent(
                id=location.id,
                timestamp=location.timestamp,
                timestamp_sort=location.timestamp_sort,
                source_app=source_type,
                category="locations",
                event_type="location_recorded",
                title=f"Location ({source_type})",
                summary=" — ".join(summary_parts),
                location_lat=location.latitude,
                location_lon=location.longitude,
                location_accuracy=location.accuracy,
                confidence=loc.get("confidence", "medium")
            ))
        return locations, events

    def normalize_browser_history(self) -> Tuple[List[BrowserHistory], List[BrowserSearch], List[BrowserDownload], List[TimelineEvent]]:
        history_records = []
        search_records = []
        download_records = []
        events = []
        
        # Browser history
        raw_history = self.loader.load_browser_history()
        for i, h in enumerate(raw_history):
            ts = h.get("timestamp", "")
            rec = BrowserHistory(
                id=self.generate_id("bh", i, str(ts), h.get("url", "")),
                timestamp=str(ts) if ts else None,
                timestamp_sort=self.parse_timestamp(ts),
                browser=h.get("browser"),
                package_name=h.get("package_name"),
                profile=h.get("profile"),
                url=h.get("url"),
                title=h.get("title"),
                visit_count=h.get("visit_count"),
                typed_count=h.get("typed_count"),
                confidence=h.get("confidence")
            )
            history_records.append(rec)
            events.append(TimelineEvent(
                id=rec.id,
                timestamp=rec.timestamp,
                timestamp_sort=rec.timestamp_sort,
                source_app=rec.browser or "Browser",
                category="browser",
                event_type="page_visit",
                title=rec.title or "Page Visit",
                summary=rec.url,
                confidence=rec.confidence or "medium"
            ))
        
        # Browser searches
        raw_searches = self.loader.load_browser_searches()
        for i, s in enumerate(raw_searches):
            ts = s.get("timestamp", "")
            rec = BrowserSearch(
                id=self.generate_id("bs", i, str(ts), s.get("search_term", "")),
                timestamp=str(ts) if ts else None,
                timestamp_sort=self.parse_timestamp(ts),
                browser=s.get("browser"),
                package_name=s.get("package_name"),
                profile=s.get("profile"),
                search_term=s.get("search_term"),
                url=s.get("url"),
                confidence=s.get("confidence")
            )
            search_records.append(rec)
            events.append(TimelineEvent(
                id=rec.id,
                timestamp=rec.timestamp,
                timestamp_sort=rec.timestamp_sort,
                source_app=rec.browser or "Browser",
                category="browser",
                event_type="browser_search",
                title=f"Searched: {rec.search_term}",
                summary=rec.url,
                confidence=rec.confidence or "medium"
            ))
        
        # Browser downloads
        raw_downloads = self.loader.load_browser_downloads()
        for i, d in enumerate(raw_downloads):
            ts = d.get("timestamp", "")
            rec = BrowserDownload(
                id=self.generate_id("bd", i, str(ts), d.get("download_url", "")),
                timestamp=str(ts) if ts else None,
                timestamp_sort=self.parse_timestamp(ts),
                browser=d.get("browser"),
                package_name=d.get("package_name"),
                profile=d.get("profile"),
                download_url=d.get("download_url"),
                target_path=d.get("target_path"),
                mime_type=d.get("mime_type"),
                received_bytes=d.get("received_bytes"),
                total_bytes=d.get("total_bytes"),
                confidence=d.get("confidence")
            )
            download_records.append(rec)
            events.append(TimelineEvent(
                id=rec.id,
                timestamp=rec.timestamp,
                timestamp_sort=rec.timestamp_sort,
                source_app=rec.browser or "Browser",
                category="browser",
                event_type="browser_download",
                title=f"Downloaded: {rec.target_path or rec.download_url}",
                summary=rec.download_url,
                confidence=rec.confidence or "medium"
            ))
        
        return history_records, search_records, download_records, events

    def normalize_integrity(self) -> Tuple[List[Hash], List[AuditEvent]]:
        hashes = []
        audits = []
        lines = self.loader.load_sha256sums()
        for i, line in enumerate(lines):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                hashes.append(Hash(
                    id=self.generate_id("hash", i, "", parts[1]),
                    file_path=parts[1],
                    sha256=self.redact_secrets(parts[0]),
                    source="sha256sums.txt"
                ))
        # Audit events from acquisition/audit.jsonl
        raw_audits = self.loader.load_audit()
        for i, a in enumerate(raw_audits):
            # Redact any potential keys in command fields
            details = {k: v for k, v in a.items() if k not in ("timestamp", "action", "result")}
            for k, v in details.items():
                if isinstance(v, str):
                    details[k] = self.redact_secrets(v)
            audits.append(AuditEvent(
                id=self.generate_id("audit", i, str(a.get("timestamp", "")), str(a.get("action", ""))),
                timestamp=str(a.get("timestamp")) if a.get("timestamp") else None,
                action=str(a.get("action")) if a.get("action") is not None else None,
                result=str(a.get("result")) if a.get("result") is not None else None,
                details_json=json.dumps(details)
            ))
        return hashes, audits
