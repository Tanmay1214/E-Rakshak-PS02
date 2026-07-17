"""WhatsApp Chat Exporter Runner for E-RAKSHAK.

Wraps execution of KnugiHK/Whatsapp-Chat-Exporter (wtsexporter).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any


def find_wtsexporter() -> str:
    """Finds the wtsexporter executable.
    
    First checks bundled locations, then falls back to PATH.
    """
    bundled_paths = [
        "platform-tools/tools/whatsapp-chat-exporter/wtsexporter.exe",
        "tools/whatsapp-chat-exporter/wtsexporter.exe",
        "tools/whatsapp-chat-exporter/wtsexporter"
    ]
    for bp in bundled_paths:
        if os.path.exists(bp):
            return str(Path(bp).resolve())
            
    # shutil.which
    found = shutil.which("wtsexporter")
    if found:
        return found
        
    raise RuntimeError("wtsexporter not found. Install with: pip install whatsapp-chat-exporter")


def is_sqlite_database(path: Path) -> bool:
    """Checks if the file starts with SQLite format 3 magic bytes."""
    if not path.is_file():
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(16)
            return header.startswith(b"SQLite format 3")
    except Exception:
        return False


def locate_whatsapp_artifacts(case_folder: Path) -> dict[str, Optional[Path]]:
    """Locates WhatsApp artifacts in the case folder.
    
    - Required:
      processed/apps/whatsapp/decrypted/msgstore.db
    - Optional:
      processed/apps/whatsapp/decrypted/wa.db
      raw/apps/whatsapp/wa.db
      processed/apps/whatsapp/media/
      raw/apps/whatsapp/media/
      raw/apps/whatsapp/WhatsApp/
      raw/apps/whatsapp/Android/media/com.whatsapp/WhatsApp/
    """
    case_folder = Path(case_folder)
    
    # Required
    msgstore_db = case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "msgstore.db"
    
    # Optional databases
    wa_db_candidates = [
        case_folder / "processed" / "apps" / "whatsapp" / "decrypted" / "wa.db",
        case_folder / "raw" / "apps" / "whatsapp" / "wa.db"
    ]
    wa_db = None
    for cand in wa_db_candidates:
        if cand.is_file():
            wa_db = cand
            break
            
    # Optional media
    media_candidates = [
        case_folder / "processed" / "apps" / "whatsapp" / "media",
        case_folder / "raw" / "apps" / "whatsapp" / "media",
        case_folder / "raw" / "apps" / "whatsapp" / "WhatsApp",
        case_folder / "raw" / "apps" / "whatsapp" / "Android" / "media" / "com.whatsapp" / "WhatsApp"
    ]
    media_dir = None
    for cand in media_candidates:
        if cand.is_dir():
            media_dir = cand
            break
            
    # Validations on required
    if not msgstore_db.is_file():
        raise RuntimeError("No decrypted WhatsApp msgstore.db found. Run whatsapp-auto-decrypt first.")
        
    if not is_sqlite_database(msgstore_db):
        raise RuntimeError("Decrypted msgstore.db is not a valid SQLite database.")
        
    return {
        "msgstore_db": msgstore_db,
        "wa_db": wa_db,
        "media_dir": media_dir
    }


def run_whatsapp_chat_exporter(
    case_id: str,
    exhibit_id: str,
    output_root: Path,
    input_dir: Optional[Path] = None,
    wa_db: Optional[Path] = None,
    media_dir: Optional[Path] = None,
    vcard_path: Optional[Path] = None,
    time_offset: Optional[int] = None,
    filter_date: Optional[str] = None,
    filter_date_format: Optional[str] = None,
    timeout_seconds: int = 900
) -> dict[str, Any]:
    """Runs the wtsexporter CLI tool."""
    case_folder = Path(output_root) / case_id / exhibit_id
    
    # Resolve msgstore.db
    if input_dir is not None:
        input_dir = Path(input_dir)
        msgstore_db = input_dir / "msgstore.db"
        if not msgstore_db.is_file():
            raise RuntimeError(f"msgstore.db not found in specified input directory: {input_dir}")
        if not is_sqlite_database(msgstore_db):
            raise RuntimeError(f"msgstore.db in specified input directory is not a valid SQLite database.")
    else:
        artifacts = locate_whatsapp_artifacts(case_folder)
        msgstore_db = artifacts["msgstore_db"]
        if wa_db is None:
            wa_db = artifacts["wa_db"]
        if media_dir is None:
            media_dir = artifacts["media_dir"]

    # Target folders
    html_output_dir = case_folder / "derived" / "whatsapp_exporter" / "html"
    html_output_dir.mkdir(parents=True, exist_ok=True)
    
    json_output_path = case_folder / "derived" / "whatsapp_exporter" / "result.json"
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Enforce local derived directory for media/vcards/thumbnails to prevent root folder clutter
    if media_dir is None:
        media_dir = case_folder / "derived" / "whatsapp_exporter" / "media_temp"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Date filter defaults to last 7 days if none specified
    if filter_date is None:
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        filter_date = f"> {seven_days_ago}"
    if filter_date_format is None:
        filter_date_format = "%Y-%m-%d"

    tool_path = find_wtsexporter()
    
    argv = [
        tool_path,
        "-a",
        "-d", str(msgstore_db),
        "-o", str(html_output_dir),
        "-j", str(json_output_path),
        "-m", str(media_dir),
        "--pretty-print-json"
    ]
    
    if wa_db is not None:
        argv += ["-w", str(wa_db)]
    if vcard_path is not None:
        argv += ["--enrich-from-vcards", str(vcard_path), "--default-country-code", "91"]
    if time_offset is not None:
        argv += ["--time-offset", str(time_offset)]
    if filter_date is not None:
        argv += ["--date", filter_date]
    if filter_date_format is not None:
        argv += ["--date-format", filter_date_format]
        
    start_time = time.time()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
            env=env
        )
        duration_ms = int((time.time() - start_time) * 1000)
        
        status = "success" if result.returncode == 0 else "failed"
        
        # Check generated files count
        generated_file_count = 0
        if html_output_dir.exists():
            generated_file_count += len([f for f in html_output_dir.rglob("*") if f.is_file()])
        if json_output_path.exists():
            generated_file_count += 1
            
        return {
            "status": status,
            "tool": "wtsexporter",
            "tool_path": tool_path,
            "command": argv,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "msgstore_db": str(msgstore_db),
            "wa_db": str(wa_db) if wa_db else "",
            "media_dir": str(media_dir) if media_dir else "",
            "html_output_dir": str(html_output_dir),
            "json_output_path": str(json_output_path),
            "generated_file_count": generated_file_count,
            "duration_ms": duration_ms
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "failed",
            "tool": "wtsexporter",
            "tool_path": tool_path,
            "command": argv,
            "return_code": -1,
            "stdout": "",
            "stderr": str(e),
            "msgstore_db": str(msgstore_db),
            "wa_db": str(wa_db) if wa_db else "",
            "media_dir": str(media_dir) if media_dir else "",
            "html_output_dir": str(html_output_dir),
            "json_output_path": str(json_output_path),
            "generated_file_count": 0,
            "duration_ms": duration_ms
        }
