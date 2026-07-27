"""Stable event ID generation for E-RAKSHAK timeline."""

import hashlib


def make_event_id(
    case_id: str,
    exhibit_id: str,
    source_file: str,
    row_index: int,
    timestamp: str,
    event_type: str,
    summary: str
) -> str:
    """Generate a stable event ID using SHA-256."""
    c = str(case_id or "")
    ex = str(exhibit_id or "")
    sf = str(source_file or "")
    ri = str(row_index)
    ts = str(timestamp or "")
    et = str(event_type or "")
    sm = str(summary or "")

    payload = f"{c}|{ex}|{sf}|{ri}|{ts}|{et}|{sm}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"evt_{h}"
