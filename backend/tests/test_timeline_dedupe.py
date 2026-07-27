"""Unit tests for timeline deduplication and IDs."""

from erakshak.dashboard.timeline_models import TimelineEvent
from erakshak.dashboard.timeline_ids import make_event_id
from erakshak.dashboard.timeline_dedupe import dedupe_events


def test_stable_event_id() -> None:
    id1 = make_event_id("C1", "E1", "sms.jsonl", 0, "2026-07-25T12:00:00", "sms_message", "hello")
    id2 = make_event_id("C1", "E1", "sms.jsonl", 0, "2026-07-25T12:00:00", "sms_message", "hello")
    # IDs must be stable across rebuilds
    assert id1 == id2
    assert id1.startswith("evt_")


def test_dedupe_sms_duplicate_lanes() -> None:
    # Build two events representing the same SMS from direct content provider and collector
    e1 = TimelineEvent(
        id="evt_1",
        case_id="CASE001",
        exhibit_id="EX001",
        timestamp="2026-07-25T12:00:00+05:30",
        timestamp_sort=1721890000000,
        bucket_15m="2026-07-25T12:00:00+05:30",
        bucket_1h="2026-07-25T12:00:00+05:30",
        source_app="SMS",
        source_type="adb_content_provider",
        category="messages",
        event_type="sms_message",
        direction="incoming",
        phone_number="+919876543210",
        summary="Hello world!",
        confidence="medium"
    )

    e2 = TimelineEvent(
        id="evt_2",
        case_id="CASE001",
        exhibit_id="EX001",
        timestamp="2026-07-25T12:00:00+05:30",
        timestamp_sort=1721890000000,
        bucket_15m="2026-07-25T12:00:00+05:30",
        bucket_1h="2026-07-25T12:00:00+05:30",
        source_app="SMS",
        source_type="collector_app_import",
        category="messages",
        event_type="sms_message",
        direction="incoming",
        phone_number="+919876543210",
        summary="Hello world!",
        confidence="high"
    )

    # Deduping should favor collector_app_import (priority 2) over adb_content_provider (priority 3)
    events = [e1, e2]
    deduped, stats = dedupe_events(events)

    assert len(deduped) == 1
    assert deduped[0].source_type == "collector_app_import"
    assert stats["sms"]["deduplicated"] == 1


def test_dedupe_call_duplicate_lanes() -> None:
    # Build two events representing the same call
    e1 = TimelineEvent(
        id="evt_call_1",
        case_id="CASE001",
        exhibit_id="EX001",
        timestamp="2026-07-25T14:30:00+05:30",
        timestamp_sort=1721899000000,
        bucket_15m="2026-07-25T14:30:00+05:30",
        bucket_1h="2026-07-25T14:00:00+05:30",
        source_app="Phone",
        source_type="normalized_derived",
        category="calls",
        event_type="phone_call",
        direction="incoming",
        phone_number="+919876543210",
        summary="Call with +919876543210. Duration: 45s",
        confidence="high"
    )

    e2 = TimelineEvent(
        id="evt_call_2",
        case_id="CASE001",
        exhibit_id="EX001",
        timestamp="2026-07-25T14:30:00+05:30",
        timestamp_sort=1721899000000,
        bucket_15m="2026-07-25T14:30:00+05:30",
        bucket_1h="2026-07-25T14:00:00+05:30",
        source_app="Phone",
        source_type="adb_content_provider",
        category="calls",
        event_type="phone_call",
        direction="incoming",
        phone_number="+919876543210",
        summary="Call with +919876543210. Duration: 45s",
        confidence="medium"
    )

    # Deduping should favor normalized_derived (priority 1) over adb_content_provider (priority 3)
    events = [e1, e2]
    deduped, stats = dedupe_events(events)

    assert len(deduped) == 1
    assert deduped[0].source_type == "normalized_derived"
    assert stats["calls"]["deduplicated"] == 1
