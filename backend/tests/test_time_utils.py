"""Unit tests for time_utils."""

import datetime
from erakshak.dashboard.time_utils import (
    resolve_timeline_range,
    parse_timestamp,
    to_epoch_ms,
    to_iso,
    bucket_time
)


def test_resolve_timeline_range_recent_days() -> None:
    # Default recent days
    res = resolve_timeline_range(recent_days=7, from_date=None, to_date=None)
    assert res["mode"] == "recent_days"
    assert res["from"] is not None
    assert res["to"] is not None
    
    # Calculate difference
    delta = res["to_dt"] - res["from_dt"]
    # Should be approximately 7 days (exact because delta is 7 days)
    assert abs(delta.days - 7) <= 1


def test_resolve_timeline_range_explicit_both() -> None:
    res = resolve_timeline_range(recent_days=7, from_date="2026-07-20", to_date="2026-07-25")
    assert res["mode"] == "explicit"
    assert res["from"].startswith("2026-07-20T00:00:00")
    # should cover the whole end day
    assert "2026-07-25T23:59:59" in res["to"]


def test_resolve_timeline_range_only_from() -> None:
    res = resolve_timeline_range(recent_days=7, from_date="2026-07-20", to_date=None)
    assert res["mode"] == "explicit"
    assert res["from"].startswith("2026-07-20")
    # to_date is close to now
    now = datetime.datetime.now(res["tz"])
    assert (res["to_dt"] - now).total_seconds() < 5


def test_resolve_timeline_range_only_to() -> None:
    res = resolve_timeline_range(recent_days=5, from_date=None, to_date="2026-07-25")
    assert res["mode"] == "explicit"
    # from should be 2026-07-25 minus 5 days = 2026-07-20
    assert res["from"].startswith("2026-07-20")
    assert "2026-07-25T23:59:59" in res["to"]


def test_parse_timestamp_various() -> None:
    # 1. ISO format with tz
    dt = parse_timestamp("2026-07-24T18:56:28.909006+05:30")
    assert dt is not None
    assert dt.year == 2026
    assert dt.hour == 18

    # 2. ISO UTC
    dt = parse_timestamp("2026-07-24T13:26:28Z")
    assert dt is not None
    # Converts to target (default Asia/Kolkata +5:30)
    # 13:26:28 UTC is 18:56:28 Kolkata
    assert dt.hour == 18

    # 3. Epoch milliseconds
    dt = parse_timestamp(1721827588000) # 2024-07-24
    assert dt is not None
    assert dt.year == 2024

    # 4. Epoch seconds
    dt = parse_timestamp(1721827588)
    assert dt is not None
    assert dt.year == 2024

    # 5. WebKit timestamp (chrome microseconds)
    # e.g., 13330363200000000
    dt = parse_timestamp(13330363200000000)
    assert dt is not None
    # 13330363200000000 is 2023-06-03
    assert dt.year == 2023


def test_bucket_time_calculations() -> None:
    # 15m bucket
    dt = datetime.datetime(2026, 7, 24, 18, 56, 28)
    b15 = bucket_time(dt, 15)
    assert "18:45:00" in b15

    # 1h bucket
    b1h = bucket_time(dt, 60)
    assert "18:00:00" in b1h
