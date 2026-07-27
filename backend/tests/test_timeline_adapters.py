"""Unit tests for timeline adapters."""

import json
from pathlib import Path
from erakshak.dashboard.timeline_adapters import (
    whatsapp_adapter,
    telegram_adapter,
    signal_adapter,
    sms_adapter,
    calls_adapter,
    media_adapter,
    apps_adapter,
    accounts_adapter,
    browser_adapter,
    location_adapter,
    network_adapter,
    system_adapter
)


def test_missing_files_do_not_crash(tmp_path: Path) -> None:
    # Running adapters on an empty folder should not crash and should return warnings
    adapters = [
        whatsapp_adapter,
        telegram_adapter,
        signal_adapter,
        sms_adapter,
        calls_adapter,
        media_adapter,
        apps_adapter,
        accounts_adapter,
        browser_adapter,
        location_adapter,
        network_adapter,
        system_adapter
    ]
    for adapter in adapters:
        events, warnings = adapter.load_events(tmp_path, "CASE", "EXHIBIT")
        assert isinstance(events, list)
        assert isinstance(warnings, list)
        # Should gracefully return warnings for missing files
        assert len(warnings) > 0


def test_whatsapp_adapter_parses_json(tmp_path: Path) -> None:
    wa_dir = tmp_path / "derived" / "whatsapp_exporter"
    wa_dir.mkdir(parents=True)
    
    # Create result.json mock
    result_data = {
        "+919876543210@s.whatsapp.net": [
            {
                "timestamp": "2026-07-25T12:00:00+05:30",
                "message": "hello WhatsApp!",
                "from_me": False,
                "sender": "Alice"
            }
        ]
    }
    with open(wa_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f)
        
    events, warnings = whatsapp_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].source_app == "WhatsApp"
    assert events[0].summary == "hello WhatsApp!"


def test_telegram_adapter_parses_jsonl(tmp_path: Path) -> None:
    tg_dir = tmp_path / "derived" / "apps" / "telegram" / "org.telegram.messenger"
    tg_dir.mkdir(parents=True)

    # Create users mock
    with open(tg_dir / "cache4_users.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"uid": 123, "name": "Bob"}) + "\n")
        
    # Create messages mock
    with open(tg_dir / "cache4_messages.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"date": 1721890000, "text": "hello Telegram!", "uid": 123, "out": 0}) + "\n")

    events, warnings = telegram_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].source_app == "Telegram"
    assert events[0].summary == "hello Telegram!"
    assert events[0].sender == "Bob"


def test_signal_adapter_parses_jsonl(tmp_path: Path) -> None:
    sig_dir = tmp_path / "derived" / "apps" / "signal" / "org.thoughtcrime.securesms"
    sig_dir.mkdir(parents=True)

    with open(sig_dir / "databases_signal_messages.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"date": "2026-07-25 12:00:00 UTC", "message": "hello Signal!", "contact_name": "Charlie", "sent": False, "received": True}) + "\n")

    events, warnings = signal_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].source_app == "Signal"
    assert events[0].summary == "hello Signal!"
    assert events[0].sender == "Charlie"


def test_sms_adapter_various(tmp_path: Path) -> None:
    # 1. Derived SMS
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True)
    with open(derived_dir / "sms_messages.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "body": "derived sms", "address": "+919876543210", "type": 1}) + "\n")

    # 2. Raw content SMS
    raw_sys = tmp_path / "raw" / "system"
    raw_sys.mkdir(parents=True)
    with open(raw_sys / "content_sms.txt", "w", encoding="utf-8") as f:
        f.write("Row: 0 _id=1, address=+919876543210, date=1721890000000, type=2, body=raw sms\n")

    # 3. Collector SMS
    raw_coll = tmp_path / "raw" / "collector"
    raw_coll.mkdir(parents=True)
    with open(raw_coll / "sms.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "body": "collector sms", "address": "+919876543210", "type": 1}) + "\n")

    events, warnings = sms_adapter.load_events(tmp_path, "C1", "E1")
    # Should find all three
    assert len(events) == 3
    sources = [e.source_type for e in events]
    assert "normalized_derived" in sources
    assert "adb_content_provider" in sources
    assert "collector_app_import" in sources


def test_calls_adapter_various(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "call_logs.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "number": "+919876543210", "duration": 30, "type": 1}) + "\n")

    raw_sys = tmp_path / "raw" / "system"
    raw_sys.mkdir(parents=True, exist_ok=True)
    with open(raw_sys / "content_call_log.txt", "w", encoding="utf-8") as f:
        f.write("Row: 0 _id=1, number=+919876543210, date=1721890000000, duration=45, type=2\n")

    raw_coll = tmp_path / "raw" / "collector"
    raw_coll.mkdir(parents=True, exist_ok=True)
    with open(raw_coll / "calls.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "number": "+919876543210", "duration": 15, "type": 3}) + "\n")

    events, warnings = calls_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 3
    directions = [e.direction for e in events]
    assert "incoming" in directions
    assert "outgoing" in directions
    assert "missed" in directions


def test_media_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "media_index.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"date_taken": "2026-07-25T12:00:00+05:30", "file_path": "/sdcard/DCIM/photo.jpg", "mime_type": "image/jpeg"}) + "\n")

    events, warnings = media_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].category == "media"
    assert events[0].event_type == "image_captured"


def test_apps_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "installed_apps.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"package_name": "com.android.chrome", "first_install_time": "2026-07-25T12:00:00+05:30", "last_update_time": "2026-07-26T12:00:00+05:30", "version_name": "120.0"}) + "\n")

    events, warnings = apps_adapter.load_events(tmp_path, "C1", "E1")
    # Creates both install and update events
    assert len(events) == 2
    types = [e.event_type for e in events]
    assert "app_installed" in types
    assert "app_updated" in types


def test_accounts_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "accounts.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "name": "alice@gmail.com", "type": "com.google"}) + "\n")

    events, warnings = accounts_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].category == "accounts"
    assert events[0].email == "alice@gmail.com"


def test_browser_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "browser_history.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "url": "https://google.com", "title": "Google", "browser": "Chrome"}) + "\n")

    events, warnings = browser_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].category == "browser"
    assert events[0].event_type == "browser_visit"


def test_location_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "location_evidence.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "source_type": "media_exif", "latitude": 21.1702, "longitude": 72.8311, "nearest_locality": "Varachha", "confidence": "high"}) + "\n")

    events, warnings = location_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].category == "locations"
    assert events[0].location_lat == 21.1702
    assert "Varachha" in events[0].summary


def test_network_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "network_connections.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "protocol": "TCP", "local_address": "127.0.0.1:80", "foreign_address": "127.0.0.1:443", "state": "ESTABLISHED"}) + "\n")

    events, warnings = network_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].category == "network"
    assert events[0].event_type == "network_connection"


def test_system_adapter_parses(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    with open(derived_dir / "logcat_events.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "2026-07-25T12:00:00+05:30", "tag": "ActivityManager", "message": "START activity"}) + "\n")

    events, warnings = system_adapter.load_events(tmp_path, "C1", "E1")
    assert len(events) == 1
    assert events[0].category == "system"
    assert events[0].event_type == "logcat_event"
