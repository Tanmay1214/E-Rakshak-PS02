"""Network timeline adapter for E-RAKSHAK."""

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
    """Load network observations and connection logs from derived outputs."""
    events: List[TimelineEvent] = []
    warnings: List[str] = []

    derived_dir = case_folder / "derived"

    # 1. derived/network_connections.jsonl
    conn_file = derived_dir / "network_connections.jsonl"
    if conn_file.is_file():
        try:
            row_idx = 0
            with open(conn_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        conn = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in derived/network_connections.jsonl: {e}. Skipped.")
                        continue

                    raw_ts = conn.get("timestamp") or conn.get("date")
                    if not raw_ts:
                        row_idx += 1
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    proto = conn.get("protocol") or "TCP"
                    local = conn.get("local_address") or "0.0.0.0"
                    foreign = conn.get("foreign_address") or "0.0.0.0"
                    state = conn.get("state") or "ESTABLISHED"
                    summary = f"Network connection: {proto} {local} -> {foreign} ({state})"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(conn_file.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="network_connection",
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
                        source_type="network",
                        category="network",
                        event_type="network_connection",
                        title=f"Network Connection ({proto})",
                        summary=summary,
                        confidence="medium",
                        source_file=str(conn_file.relative_to(case_folder)),
                        parser="NetstatParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing derived/network_connections.jsonl: {e}")
    else:
        warnings.append("derived/network_connections.jsonl not found.")

    # 2. derived/cell_observations.jsonl
    cell_file = derived_dir / "cell_observations.jsonl"
    if cell_file.is_file():
        try:
            row_idx = 0
            with open(cell_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cell = json.loads(line)
                    except Exception as e:
                        warnings.append(f"Malformed JSON line in derived/cell_observations.jsonl: {e}. Skipped.")
                        continue

                    raw_ts = cell.get("timestamp") or cell.get("date")
                    if not raw_ts:
                        row_idx += 1
                        continue

                    dt = parse_timestamp(raw_ts, timezone)
                    if not dt:
                        row_idx += 1
                        continue

                    ts_iso = to_iso(dt)
                    ts_sort = to_epoch_ms(dt)

                    mcc = cell.get("mcc") or ""
                    mnc = cell.get("mnc") or ""
                    lac = cell.get("lac") or cell.get("tac") or ""
                    cid = cell.get("cid") or cell.get("nci") or ""
                    tech = cell.get("type") or "LTE"
                    summary = f"Observed Cell Tower: MCC={mcc}, MNC={mnc}, LAC={lac}, CID={cid} ({tech})"

                    evt_id = make_event_id(
                        case_id=case_id,
                        exhibit_id=exhibit_id,
                        source_file=str(cell_file.relative_to(case_folder)),
                        row_index=row_idx,
                        timestamp=ts_iso,
                        event_type="cell_tower_observed",
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
                        source_type="cell_tower",
                        category="network",
                        event_type="cell_tower_observed",
                        title=f"Cell Registration observed ({tech})",
                        summary=summary,
                        confidence="medium",
                        source_file=str(cell_file.relative_to(case_folder)),
                        parser="TelephonyRegistryParser",
                        raw_json=line
                    ))
                    row_idx += 1
        except Exception as e:
            warnings.append(f"Failed parsing derived/cell_observations.jsonl: {e}")
    else:
        warnings.append("derived/cell_observations.jsonl not found.")

    return events, warnings
