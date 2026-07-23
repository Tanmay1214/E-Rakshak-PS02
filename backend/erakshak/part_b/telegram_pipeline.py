"""Telegram Orchestration Pipeline — Phase 4.

Connects acquisition, parsing, and JSON output generation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from erakshak.adb.client import ADBClient
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.part_b.telegram_db_pull import acquire_telegram_databases
from erakshak.part_b.telegram_parser import TelegramParser


def run_telegram_pipeline(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
) -> dict[str, Any]:
    """Execute the full Telegram MVP pipeline.

    1. Acquire databases and sidecars using `acquire_telegram_databases`.
    2. For each acquired `.db`, parse it using `TelegramParser`.
    3. Save normalized JSONL output.
    
    Returns a summary dictionary of the entire operation.
    """
    audit.log(action="telegram_pipeline_start", result="started")

    # 1. Acquisition
    print("[*] Starting Telegram acquisition...")
    acq_results = acquire_telegram_databases(adb, case_folder, manifest, audit)
    
    # 2. Setup parsing outputs
    derived_telegram_dir = case_folder.derived_dir / "apps" / "telegram"
    
    pipeline_summary: dict[str, Any] = {
        "acquisition": acq_results,
        "parsing": {
            "parsed_dbs": [],
            "unsupported_dbs": [],
            "total_users": 0,
            "total_messages": 0,
            "total_dialogs": 0,
            "errors": [],
            "warnings": [],
        },
        "output_dir": str(derived_telegram_dir),
    }

    # If no packages were found or an error occurred, return early
    if not acq_results["packages_found"]:
        print("[-] No supported Telegram packages found on device.")
        return pipeline_summary

    # 3. Parsing
    print("[*] Starting Telegram database parsing...")
    
    # We will search the raw acquisition directory for downloaded DBs
    # rather than strictly relying on the result dict, ensuring we only 
    # parse what actually exists on disk.
    raw_telegram_dir = case_folder.raw_apps_telegram_dir
    
    import shutil
    
    for db_path in raw_telegram_dir.rglob("*.db"):
        # We only want to parse primary DBs, not sidecars, though rglob "*.db" 
        # matches `cache4.db`. If any `.db-wal` matches accidentally, rglob 
        # won't catch it because of the extension. But `cache4.db` is standard.
        
        # Package name is typically the parent directory name
        pkg_name = db_path.parent.name
        pkg_derived_dir = derived_telegram_dir / pkg_name
        pkg_derived_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"  -> Parsing {db_path.name} for {pkg_name}...")
        
        # Create a forensic working copy to prevent SQLite ?mode=ro from creating/modifying -shm/-wal sidecars in the raw evidence folder.
        working_dir = pkg_derived_dir / "_working_copy"
        working_dir.mkdir(parents=True, exist_ok=True)
        working_db_path = working_dir / db_path.name
        
        # Copy primary DB
        shutil.copy2(db_path, working_db_path)
        
        # Copy any associated sidecars
        for sidecar_ext in [".db-wal", ".db-shm", ".db-journal"]:
            raw_sidecar = db_path.parent / (db_path.name + sidecar_ext.replace(".db", ""))
            if raw_sidecar.exists():
                shutil.copy2(raw_sidecar, working_dir / raw_sidecar.name)
        
        with TelegramParser(working_db_path) as parser:
            parsed_data = parser.parse_all()
            
            if parsed_data["status"] == "success":
                pipeline_summary["parsing"]["parsed_dbs"].append(str(db_path))
                
                users = parsed_data["users"]
                messages = parsed_data["messages"]
                dialogs = parsed_data["dialogs"]
                
                pipeline_summary["parsing"]["total_users"] += len(users)
                pipeline_summary["parsing"]["total_messages"] += len(messages)
                pipeline_summary["parsing"]["total_dialogs"] += len(dialogs)
                
                # Write to JSONL
                if users:
                    _write_jsonl(pkg_derived_dir / f"{db_path.stem}_users.jsonl", users)
                if messages:
                    _write_jsonl(pkg_derived_dir / f"{db_path.stem}_messages.jsonl", messages)
                if dialogs:
                    _write_jsonl(pkg_derived_dir / f"{db_path.stem}_dialogs.jsonl", dialogs)
                    
                if parsed_data.get("warnings"):
                    pipeline_summary["parsing"]["warnings"].extend(parsed_data["warnings"])
                    
            else:
                pipeline_summary["parsing"]["unsupported_dbs"].append(str(db_path))
                if parsed_data.get("errors"):
                    pipeline_summary["parsing"]["errors"].extend(parsed_data["errors"])
                print(f"  [!] Unsupported schema in {db_path.name}")

    # Write overall pipeline summary
    summary_path = derived_telegram_dir / "telegram_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(pipeline_summary, f, indent=2)
        
    audit.log(action="telegram_pipeline_complete", result="success")
    print(f"[*] Telegram pipeline complete. Summary saved to {summary_path}")
    
    return pipeline_summary


def _write_jsonl(path: Path, items: list[dict]) -> None:
    """Helper to write a list of dicts to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
