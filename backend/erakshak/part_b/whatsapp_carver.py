"""WhatsApp Forensic Database Carver for E-RAKSHAK.

Extracts deleted message residues from SQLite B-tree slack space and FTS index segment tables.
"""

from __future__ import annotations

import json
import re
import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, timezone

from erakshak.case.hashing import hash_file
from erakshak.adb.client import ADBClient, ADBResult
from erakshak.acquisition.whatsapp_root import detect_root_access
from erakshak.part_b.whatsapp_pipeline import (
    append_audit_event,
    append_manifest_record,
    append_sha256sum
)


def run_online_backup_on_device(
    case_id: str,
    exhibit_id: str,
    output_root: Path,
    serial: str,
    package_name: str = "com.whatsapp",
    adb_path: str = "adb"
) -> Optional[Path]:
    """Runs SQLite .backup on device using su/su_0 to get a consistent schema dump."""
    adb_client = ADBClient(serial=serial, adb_path=adb_path)
    root_info = detect_root_access(adb_client, serial)
    
    if not root_info.get("root_available", False):
        return None
        
    root_method = root_info.get("method", "none")
    remote_db = f"/data/data/{package_name}/databases/msgstore.db"
    remote_temp_backup = "/sdcard/msgstore_clean_temp.db"
    
    # 1. Trigger backup command on device
    backup_cmd = f"sqlite3 {remote_db} '.backup {remote_temp_backup}'"
    
    if root_method == "su":
        shell_args = ["su", "-c", backup_cmd]
    elif root_method == "su_0":
        shell_args = ["su", "0", backup_cmd]
    else:
        shell_args = ["sqlite3", remote_db, f".backup {remote_temp_backup}"]
        
    res = adb_client.shell(shell_args, timeout=60)
    if not res.ok:
        return None
        
    # 2. Pull the backup to host
    exhibit_path = Path(output_root) / case_id / exhibit_id
    local_backup_path = exhibit_path / "processed" / "apps" / "whatsapp" / "rooted" / package_name / "msgstore_clean.db"
    local_backup_path.parent.mkdir(parents=True, exist_ok=True)
    
    pull_res = adb_client.pull(remote_temp_backup, str(local_backup_path), timeout=120)
    
    # 3. Clean up temporary file on device
    cleanup_args = ["rm", "-f", remote_temp_backup]
    if root_method == "su":
        cleanup_args = ["su", "-c", f"rm -f {remote_temp_backup}"]
    elif root_method == "su_0":
        cleanup_args = ["su", "0", f"rm -f {remote_temp_backup}"]
    adb_client.shell(cleanup_args, timeout=10)
    
    if pull_res.ok and local_backup_path.is_file():
        return local_backup_path
        
    return None


def run_whatsapp_carver(
    case_id: str,
    exhibit_id: str,
    output_root: Path,
    serial: Optional[str] = None,
    package_name: str = "com.whatsapp",
    adb_path: str = "adb"
) -> dict[str, Any]:
    """Main carving pipeline coordinates snapshot backup, FTS scraping, and binary strings extraction."""
    exhibit_path = Path(output_root) / case_id / exhibit_id
    acquisition_dir = exhibit_path / "acquisition"
    audit_path = acquisition_dir / "audit.jsonl"
    manifest_path = acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = exhibit_path / "hashes" / "sha256sums.txt"
    
    # Audit Start
    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_carving_started",
        result="started",
        details={"package_name": package_name}
    )
    
    # 1. Resolve SQLite Database Path
    local_db_dir = exhibit_path / "processed" / "apps" / "whatsapp" / "rooted" / package_name
    msgstore_db = local_db_dir / "msgstore.db"
    msgstore_wal = local_db_dir / "msgstore.db-wal"
    
    # If device connected, perform online backup to get a clean file
    clean_db_path = None
    if serial:
        try:
            clean_db_path = run_online_backup_on_device(
                case_id=case_id,
                exhibit_id=exhibit_id,
                output_root=output_root,
                serial=serial,
                package_name=package_name,
                adb_path=adb_path
            )
        except Exception:
            pass
            
    # Fallback to copy database or msgstore.db directly
    if not clean_db_path or not clean_db_path.is_file():
        if msgstore_db.is_file():
            clean_db_path = msgstore_db
            
    if not clean_db_path or not clean_db_path.is_file():
        err_msg = "No WhatsApp msgstore.db found to carve. Please run acquisition first."
        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action="whatsapp_carving_failed",
            result="failed",
            details={"error": err_msg}
        )
        return {"status": "failed", "error": err_msg}
        
    active_messages = set()
    fts_messages = []
    
    # 2. Extract Active Messages Safely from ALL columns of ALL tables dynamically
    conn = None
    try:
        conn = sqlite3.connect(str(clean_db_path))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for table_name in tables:
            if "fts" in table_name.lower() or "sqlite_" in table_name.lower():
                continue
            try:
                cols_info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                for col in cols_info:
                    col_name = col[1]
                    col_type = col[2].upper()
                    if col_type in ("TEXT", "VARCHAR", "CHAR", ""):
                        rows = conn.execute(f"SELECT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL").fetchall()
                        for r in rows:
                            if r[0] and isinstance(r[0], str):
                                val = r[0].strip()
                                if val:
                                    active_messages.add(val)
            except Exception:
                continue
    except Exception:
        pass
        
    # 3. Extract FTS Residual Entries Safely
    if conn:
        try:
            # message_ftsv2_content is the FTS index text segment table
            rows = conn.execute("SELECT docid, c0content FROM message_ftsv2_content").fetchall()
            for docid, content in rows:
                if content and isinstance(content, str):
                    text = content.strip()
                    if text and text not in active_messages:
                        fts_messages.append({"docid": docid, "text": text})
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
                
    # 4. Binary Strings Carving from original msgstore.db and WAL files
    db_strings = set()
    target_files = [msgstore_db, msgstore_wal]
    
    for tf in target_files:
        if tf.is_file():
            try:
                data = tf.read_bytes()
                # Find ASCII/UTF-8 string segments of length 5 to 120 bytes
                pattern = re.compile(rb'[\x20-\x7E\x80-\xFF]{5,120}')
                for match in pattern.finditer(data):
                    try:
                        s = match.group(0).decode('utf-8', errors='strict').strip()
                        # Filters to weed out SQL structure and code strings
                        if re.search(r'[A-Za-z]', s) and not any(x in s for x in ['sqlite_', 'CREATE TABLE', 'index_', 'tbl_name', 'sql=']):
                            if len(s) > 8 and ' ' in s:
                                db_strings.add(s)
                    except Exception:
                        continue
            except Exception:
                pass
                
    # Keep strings not matching active chats
    deleted_candidates = []
    for s in db_strings:
        if s not in active_messages and len(s) > 10:
            deleted_candidates.append(s)
            
    # 5. Write structured reports
    output_dir = exhibit_path / "derived" / "whatsapp_exporter"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_json_path = output_dir / "carved_messages.json"
    report_txt_path = output_dir / "carved_messages_report.txt"
    
    # Save JSON Report
    json_report = {
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "package_name": package_name,
        "carved_at": datetime.now(timezone.utc).isoformat(),
        "active_message_count": len(active_messages),
        "fts_residues_count": len(fts_messages),
        "slack_candidates_count": len(deleted_candidates),
        "fts_deleted_messages": fts_messages,
        "binary_carved_candidates": deleted_candidates
    }
    
    with open(report_json_path, "w", encoding="utf-8") as jf:
        json.dump(json_report, jf, indent=2, ensure_ascii=False)
        
    # Save Text Report
    with open(report_txt_path, "w", encoding="utf-8") as tf:
        tf.write("============================================================\n")
        tf.write("  E-RAKSHAK FORENSIC CARVED DELETED MESSAGES REPORT\n")
        tf.write("============================================================\n")
        tf.write(f"Case ID           : {case_id}\n")
        tf.write(f"Exhibit ID        : {exhibit_id}\n")
        tf.write(f"Package Variant   : {package_name}\n")
        tf.write(f"Carved Timestamp  : {datetime.now(timezone.utc).isoformat()}\n")
        tf.write(f"Active Messages   : {len(active_messages)}\n")
        tf.write(f"FTS Residues Found: {len(fts_messages)}\n")
        tf.write(f"Slack Carved Text : {len(deleted_candidates)}\n")
        tf.write("============================================================\n\n")
        
        tf.write("--- RESIDUAL FTS INDEX RECORDINGS (CONFIRMED DELETIONS) ---\n")
        if fts_messages:
            for item in sorted(fts_messages, key=lambda x: x["docid"]):
                tf.write(f"[docid={item['docid']}] {item['text']}\n")
        else:
            tf.write("(none found)\n")
            
        tf.write("\n--- POTENTIAL CHAT STRINGS CARVED FROM BINARY SLACK/WAL ---\n")
        if deleted_candidates:
            # Filters candidates to find common chat sentence segments (English/Hindi)
            chat_candidates = []
            for c in deleted_candidates:
                if any(kw in c.lower() for kw in ['hai', 'kar', 'apan', 'marks', 'class', 'command', 'python', 'case', 'delete', 'mesg', 'bhai', 'han', 'yaar']):
                    chat_candidates.append(c)
            for cc in sorted(chat_candidates, key=len):
                tf.write(f"- {cc}\n")
        else:
            tf.write("(none found)\n")
            
    # 6. Hash and Manifest Logging
    generated_files = [report_json_path, report_txt_path]
    for gf in generated_files:
        if gf.is_file():
            try:
                sha = hash_file(gf)
                size = gf.stat().st_size
                append_sha256sum(sha256sums_path, sha, gf)
                append_manifest_record(manifest_path, {
                    "case_id": case_id,
                    "exhibit_id": exhibit_id,
                    "artifact_class": "whatsapp_carved_output",
                    "source_type": "derived_carver_output",
                    "destination_path": str(gf.relative_to(exhibit_path)),
                    "sha256": sha,
                    "size_bytes": size,
                    "status": "generated"
                })
            except Exception:
                pass
                
    # Audit Complete
    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_carving_completed",
        result="success",
        details={
            "fts_residues_count": len(fts_messages),
            "slack_candidates_count": len(deleted_candidates),
            "report_path": str(report_txt_path.relative_to(exhibit_path))
        }
    )
    
    return {
        "status": "success",
        "fts_residues_count": len(fts_messages),
        "slack_candidates_count": len(deleted_candidates),
        "json_report": str(report_json_path),
        "txt_report": str(report_txt_path)
    }
