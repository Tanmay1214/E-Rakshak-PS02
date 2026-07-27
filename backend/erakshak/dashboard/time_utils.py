"""Time and timestamp utilities for E-RAKSHAK dashboard timeline."""

import datetime
import re
from typing import Any, Optional


def resolve_timeline_range(
    recent_days: int,
    from_date: Optional[str],
    to_date: Optional[str],
    timezone_name: str = "Asia/Kolkata"
) -> dict[str, Any]:
    """Resolve the start and end datetime limits for the timeline window."""
    # Resolve target timezone
    if timezone_name == "Asia/Kolkata":
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    else:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = datetime.timezone.utc

    now = datetime.datetime.now(tz)
    
    if from_date or to_date:
        mode = "explicit"
        if from_date:
            from_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
            from_dt = from_dt.replace(tzinfo=tz)
        else:
            # only to_date is provided
            to_dt_temp = datetime.datetime.strptime(to_date, "%Y-%m-%d")
            from_dt = to_dt_temp - datetime.timedelta(days=recent_days)
            from_dt = from_dt.replace(tzinfo=tz)

        if to_date:
            to_dt = datetime.datetime.strptime(to_date, "%Y-%m-%d")
            to_dt = to_dt.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz)
        else:
            to_dt = now
    else:
        mode = "recent_days"
        from_dt = now - datetime.timedelta(days=recent_days)
        to_dt = now

    return {
        "mode": mode,
        "from": from_dt.isoformat(),
        "to": to_dt.isoformat(),
        "from_dt": from_dt,
        "to_dt": to_dt,
        "tz": tz
    }


def to_epoch_ms(dt: datetime.datetime) -> int:
    """Convert timezone-aware datetime to epoch milliseconds."""
    return int(dt.timestamp() * 1000)


def to_iso(dt: datetime.datetime) -> str:
    """Convert datetime to ISO 8601 string."""
    return dt.isoformat()


def bucket_time(dt: datetime.datetime, minutes: int) -> str:
    """Round down datetime to nearest bucket (15 minutes or 1 hour)."""
    if minutes == 60:
        bucket = dt.replace(minute=0, second=0, microsecond=0)
    else:
        bucket_min = (dt.minute // minutes) * minutes
        bucket = dt.replace(minute=bucket_min, second=0, microsecond=0)
    return bucket.isoformat()


def parse_timestamp(value: Any, timezone_name: str = "Asia/Kolkata") -> Optional[datetime.datetime]:
    """Parse raw timestamp (ISO string, epoch ms, WebKit) to a timezone-aware datetime."""
    if value is None:
        return None

    if timezone_name == "Asia/Kolkata":
        tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    else:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = datetime.timezone.utc

    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz)
        return value.astimezone(tz)

    val_str = str(value).strip()
    if not val_str:
        return None

    # Check for numeric format (digits only, optionally float)
    if re.match(r"^-?\d+(\.\d+)?$", val_str):
        try:
            val_num = float(val_str)
            if val_num <= 0:
                return None
                
            # Heuristics:
            # 1. WebKit timestamp: 17 digits (microseconds since 1601)
            # 2. Epoch milliseconds: 13 digits (since 1970)
            # 3. Epoch seconds: 10 digits
            if val_num > 10_000_000_000_000_000:
                unix_epoch = (val_num / 1_000_000.0) - 11644473600.0
                dt = datetime.datetime.fromtimestamp(unix_epoch, datetime.timezone.utc)
                return dt.astimezone(tz)
            elif val_num > 10_000_000_000:
                dt = datetime.datetime.fromtimestamp(val_num / 1000.0, datetime.timezone.utc)
                return dt.astimezone(tz)
            else:
                dt = datetime.datetime.fromtimestamp(val_num, datetime.timezone.utc)
                return dt.astimezone(tz)
        except Exception:
            return None

    # Clean timezone indicators
    if val_str.endswith("Z"):
        val_str = val_str[:-1] + "+00:00"

    # Predefined formatting patterns
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S UTC",
        "%Y-%m-%d %H:%M:%S %Z",
    ]

    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(val_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            else:
                dt = dt.astimezone(tz)
            return dt
        except ValueError:
            continue

    return None
