from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class CaseDashboardLoader:
    def __init__(self, exhibit_root: Path):
        self.exhibit_root = Path(exhibit_root)
        self.derived_dir = self.exhibit_root / "derived"
        self.raw_dir = self.exhibit_root / "raw"
        self.acquisition_dir = self.exhibit_root / "acquisition"
        self.hashes_dir = self.exhibit_root / "hashes"

    def load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load JSON from {path}: {e}")
        return None

    def load_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        results = []
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                results.append(json.loads(line))
                            except:
                                pass
        except Exception as e:
            logger.warning(f"Failed to load JSONL from {path}: {e}")
        return results

    def load_json_flexible(self, path: Path) -> Any:
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load flexible JSON from {path}: {e}")
        return None

    def _find_jsonl_files(self, base_dir: Path, suffix: str) -> List[Path]:
        if not base_dir.exists():
            return []
        return list(base_dir.rglob(f"*{suffix}"))

    def discover_sources(self) -> Dict[str, Tuple[Path, bool, str]]:
        sources = {
            "device_identity": (self.derived_dir / "device_identity.json", "json"),
            "software_summary": (self.derived_dir / "software_summary.json", "json"),
            "installed_apps": (self.derived_dir / "installed_apps.jsonl", "jsonl"),
            "app_permission_summary": (self.derived_dir / "app_permission_summary.json", "json"),
            "accounts": (self.derived_dir / "accounts.jsonl", "jsonl"),
            "account_email_leads": (self.derived_dir / "account_email_leads.jsonl", "jsonl"),
            "device_timeline_events": (self.derived_dir / "device_timeline_events.jsonl", "jsonl"),
            "app_usage_summary": (self.derived_dir / "app_usage_summary.jsonl", "jsonl"),
            "logcat_events": (self.derived_dir / "logcat_events.jsonl", "jsonl"),
            "network_summary": (self.derived_dir / "network_summary.json", "json"),
            "network_connections": (self.derived_dir / "network_connections.jsonl", "jsonl"),
            "media_index": (self.derived_dir / "media_index.jsonl", "jsonl"),
            "call_logs": (self.derived_dir / "call_logs.jsonl", "jsonl"),
            "sms_messages": (self.derived_dir / "sms_messages.jsonl", "jsonl"),
            "contacts": (self.derived_dir / "contacts.jsonl", "jsonl"),
            "collector_calls": (self.raw_dir / "collector" / "calls.jsonl", "jsonl"),
            "collector_sms": (self.raw_dir / "collector" / "sms.jsonl", "jsonl"),
            "collector_mms": (self.raw_dir / "collector" / "mms.jsonl", "jsonl"),
            "collector_contacts": (self.raw_dir / "collector" / "contacts.jsonl", "jsonl"),
            "collector_media_index": (self.raw_dir / "collector" / "media_index.jsonl", "jsonl"),
            "whatsapp_result": (self.derived_dir / "whatsapp_exporter" / "result.json", "json"),
            "whatsapp_summary": (self.derived_dir / "whatsapp_preview_summary.json", "json"),
            "telegram_summary": (self.derived_dir / "telegram_preview_summary.json", "json"),
            "signal_summary": (self.derived_dir / "signal_preview_summary.json", "json"),
            "manifest": (self.acquisition_dir / "acquisition_manifest.jsonl", "jsonl"),
            "audit": (self.acquisition_dir / "audit.jsonl", "jsonl"),
            "preflight": (self.acquisition_dir / "preflight.json", "json"),
            "sha256sums": (self.hashes_dir / "sha256sums.txt", "text")
        }
        return {k: (v[0], v[0].exists(), v[1]) for k, v in sources.items()}

    def load_device_identity(self): return self.load_json(self.derived_dir / "device_identity.json")
    def load_software_summary(self): return self.load_json(self.derived_dir / "software_summary.json")
    def load_installed_apps(self): return self.load_jsonl(self.derived_dir / "installed_apps.jsonl")
    def load_accounts(self): return self.load_jsonl(self.derived_dir / "accounts.jsonl")
    def load_email_leads(self): return self.load_jsonl(self.derived_dir / "account_email_leads.jsonl")
    def load_device_timeline(self): return self.load_jsonl(self.derived_dir / "device_timeline_events.jsonl")
    def load_app_usage(self): return self.load_jsonl(self.derived_dir / "app_usage_summary.jsonl")
    def load_logcat_events(self): return self.load_jsonl(self.derived_dir / "logcat_events.jsonl")
    def load_network_summary(self): return self.load_json(self.derived_dir / "network_summary.json")
    def load_network_connections(self): return self.load_jsonl(self.derived_dir / "network_connections.jsonl")
    def load_media_index(self): return self.load_jsonl(self.derived_dir / "media_index.jsonl")
    def load_call_logs(self): return self.load_jsonl(self.derived_dir / "call_logs.jsonl")
    def load_sms_messages(self): return self.load_jsonl(self.derived_dir / "sms_messages.jsonl")
    def load_contacts(self): return self.load_jsonl(self.derived_dir / "contacts.jsonl")
    
    def load_collector_calls(self): return self.load_jsonl(self.raw_dir / "collector" / "calls.jsonl")
    def load_collector_sms(self): return self.load_jsonl(self.raw_dir / "collector" / "sms.jsonl")
    def load_collector_contacts(self): return self.load_jsonl(self.raw_dir / "collector" / "contacts.jsonl")
    def load_whatsapp_result(self):
        wa_dir = self.derived_dir / "whatsapp_exporter"
        if wa_dir.exists():
            for p in wa_dir.rglob("result.json"):
                return self.load_json_flexible(p)
        return None
    def load_whatsapp_summary(self): return self.load_json(self.derived_dir / "whatsapp_preview_summary.json")
    def load_telegram_summary(self): return self.load_json(self.derived_dir / "apps" / "telegram" / "telegram_summary.json")
    
    def load_telegram_users(self):
        users = []
        for p in self._find_jsonl_files(self.derived_dir / "apps" / "telegram", "_users.jsonl"):
            users.extend(self.load_jsonl(p))
        return users

    def load_telegram_messages(self):
        msgs = []
        for p in self._find_jsonl_files(self.derived_dir / "apps" / "telegram", "_messages.jsonl"):
            msgs.extend(self.load_jsonl(p))
        return msgs

    def load_signal_summary(self): return self.load_json(self.derived_dir / "apps" / "signal" / "signal_summary.json")
    
    def load_signal_messages(self):
        msgs = []
        for p in self._find_jsonl_files(self.derived_dir / "apps" / "signal", "_messages.jsonl"):
            msgs.extend(self.load_jsonl(p))
        return msgs

    def load_location_evidence(self): return self.load_jsonl(self.derived_dir / "location_evidence.jsonl")
    def load_location_summary(self): return self.load_json(self.derived_dir / "location_summary.json")
    def load_browser_history(self): return self.load_jsonl(self.derived_dir / "browser_history.jsonl")
    def load_browser_searches(self): return self.load_jsonl(self.derived_dir / "browser_searches.jsonl")
    def load_browser_downloads(self): return self.load_jsonl(self.derived_dir / "browser_downloads.jsonl")
    def load_browser_summary(self): return self.load_json(self.derived_dir / "browser_summary.json")

    def load_manifest(self): return self.load_jsonl(self.acquisition_dir / "acquisition_manifest.jsonl")
    def load_audit(self): return self.load_jsonl(self.acquisition_dir / "audit.jsonl")
    def load_preflight(self): return self.load_json(self.acquisition_dir / "preflight.json")
    def load_sha256sums(self) -> List[str]:
        path = self.hashes_dir / "sha256sums.txt"
        lines = []
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.warning(f"Failed to load sha256sums from {path}: {e}")
        return lines
