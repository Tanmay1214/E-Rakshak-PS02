"""Accounts timeline adapter for E-RAKSHAK."""

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any
from erakshak.dashboard.timeline_models import TimelineEvent
from erakshak.dashboard.timeline_ids import make_event_id
from erakshak.dashboard.time_utils import parse_timestamp, to_epoch_ms, to_iso, bucket_time


def load_events(
    case_folder: Path,
    case_id: str,
    exhibit_id: str,
    timezone: str = "Asia/Kolkata"
) -> Tuple[List[TimelineEvent], List[str]]:
    """Load system account observations from derived accounts and email lead files."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    # 1. derived/accounts.jsonl
    accounts_file = case_folder / "derived" / "accounts.jsonl"
    if accounts_file.is_file():
        try:
            row_idx = 0
            with open(accounts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        acc = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in derived/accounts.jsonl: {e}. Skipped.")
                        continue

                    # Extract timestamp (dumpsys account might not have time, default to file creation or system time if missing)
                    # Let's check if the record has a timestamp or default to now/epoch 0
                    raw_ts = acc.get("timestamp") or acc.get("date")
                    dt = parse_timestamp(raw_ts, timezone) if raw_ts else None
                    if not dt:
                        # Skip if there's no timestamp at all, as per rules: "Missing timestamp is skipped + warning"
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    name = acc.get("name") or "Unknown"
                    acc_type = acc.get("type") or "unknown"
                    summary = f"Account Observed: {name} (Type: {acc_type})"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(accounts_file.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="account_observed",
                        summary=summary
                    )

                    events.append(TimelineEvent(
                        id=evt_id,
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        timestamp=ts_iso,
                        timestamp_sort=ts_sort,
                        bucket_15m=bucket_time(dt, 15),
                        bucket_1h=bucket_time(dt, 60),
                        source_app="Android",
                        source_type="dumpsys_account",
                        category="accounts",
                        event_type="account_observed",
                        title=f"User Account Registered: {name}",
                        summary=summary,
                        actor=name,
                        email=name if "@" in name else None,
                        confidence="medium",
                        source_file=str(accounts_file.relative_to(case_folder)),
                        parser="AccountParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing derived/accounts.jsonl: {e}")
    else:
        warnings.append("derived/accounts.jsonl not found.")

    # 2. derived/account_email_leads.jsonl
    email_file = case_folder / "derived" / "account_email_leads.jsonl"
    if email_file.is_file():
        try:
            row_idx = 0
            with open(email_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        lead = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in derived/account_email_leads.jsonl: {e}. Skipped.")
                        continue

                    raw_ts = lead.get("timestamp") or lead.get("date")
                    dt = parse_timestamp(raw_ts, timezone) if raw_ts else None
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    email = lead.get("email") or "unknown"
                    source_detail = lead.get("source_file") or "dumpsys"
                    summary = f"Email Lead Identified: {email} (Found in {source_detail})"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(email_file.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="email_lead_observed",
                        summary=summary
                    )

                    events.append(TimelineEvent(
                        id=evt_id,
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        timestamp=ts_iso,
                        timestamp_sort=ts_sort,
                        bucket_15m=bucket_time(dt, 15),
                        bucket_1h=bucket_time(dt, 60),
                        source_app="Android",
                        source_type="dumpsys_account",
                        category="accounts",
                        event_type="email_lead_observed",
                        title=f"Email Identifier Lead: {email}",
                        summary=summary,
                        email=email,
                        confidence="medium",
                        source_file=str(email_file.relative_to(case_folder)),
                        parser="AccountParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing derived/account_email_leads.jsonl: {e}")

    return events, warnings
