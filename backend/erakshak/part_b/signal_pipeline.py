"""Signal Android acquisition and parsing pipeline."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from erakshak.adb.client import ADBClient
from erakshak.case.audit import AuditLogger
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.part_b.signal_db_pull import acquire_signal_databases
from erakshak.part_b.signal_key_extract import extract_signal_db_key
from erakshak.part_b.signal_parser import SignalParser


def run_signal_pipeline(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
    signal_db_key: str | None = None,
    auto_extract_key: bool = False,
) -> dict[str, Any]:
    """Execute Signal package detection, DB acquisition, and parsing."""
    audit.log(action="signal_pipeline_start", result="started")
    print("[*] Starting Signal acquisition...")
    acq_results = acquire_signal_databases(adb, case_folder, manifest, audit)

    derived_signal_dir = case_folder.derived_dir / "apps" / "signal"
    summary: dict[str, Any] = {
        "acquisition": acq_results,
        "parsing": {
            "parsed_dbs": [],
            "unsupported_dbs": [],
            "total_recipients": 0,
            "total_threads": 0,
            "total_messages": 0,
            "errors": [],
            "warnings": [],
        },
        "key_extraction": {
            "attempted": False,
            "success": False,
            "error": "",
        },
        "output_dir": str(derived_signal_dir),
    }

    if not acq_results["packages_found"]:
        print("[-] No supported Signal packages found on device.")
        return summary

    if auto_extract_key and not signal_db_key:
        summary["key_extraction"]["attempted"] = True
        print("[*] Attempting root-only Signal DB key extraction...")
        signal_db_key, key_error = extract_signal_db_key(adb, audit)
        if signal_db_key:
            summary["key_extraction"]["success"] = True
            print("  [OK] Signal DB key extracted in memory.")
        else:
            summary["key_extraction"]["error"] = key_error
            summary["parsing"]["warnings"].append(key_error)
            print(f"  [!] Signal DB key extraction failed: {key_error}")

    print("[*] Starting Signal database parsing...")
    raw_signal_dir = case_folder.raw_apps_signal_dir
    for db_path in raw_signal_dir.rglob("*.db"):
        if db_path.name != "databases_signal.db":
            continue
        pkg_name = db_path.parent.name
        pkg_derived_dir = derived_signal_dir / pkg_name
        pkg_derived_dir.mkdir(parents=True, exist_ok=True)

        print(f"  -> Parsing {db_path.name} for {pkg_name}...")
        working_dir = pkg_derived_dir / "_working_copy"
        working_dir.mkdir(parents=True, exist_ok=True)
        working_db_path = working_dir / db_path.name
        shutil.copy2(db_path, working_db_path)
        for ext in ("-wal", "-shm", "-journal"):
            sidecar = db_path.parent / (db_path.name + ext)
            if sidecar.exists():
                shutil.copy2(sidecar, working_dir / sidecar.name)

        with SignalParser(working_db_path, db_key=signal_db_key) as parser:
            parsed = parser.parse_all()
            if parsed["status"] == "success":
                summary["parsing"]["parsed_dbs"].append(str(db_path))
                recipients = parsed["recipients"]
                threads = parsed["threads"]
                messages = parsed["messages"]
                summary["parsing"]["total_recipients"] += len(recipients)
                summary["parsing"]["total_threads"] += len(threads)
                summary["parsing"]["total_messages"] += len(messages)
                if recipients:
                    _write_jsonl(pkg_derived_dir / f"{db_path.stem}_recipients.jsonl", recipients)
                if threads:
                    _write_jsonl(pkg_derived_dir / f"{db_path.stem}_threads.jsonl", threads)
                if messages:
                    _write_jsonl(pkg_derived_dir / f"{db_path.stem}_messages.jsonl", messages)
                summary["parsing"]["warnings"].extend(parsed.get("warnings", []))
            else:
                summary["parsing"]["unsupported_dbs"].append(str(db_path))
                summary["parsing"]["errors"].extend(parsed.get("errors", []))
                print(f"  [!] Unsupported or encrypted Signal database: {db_path.name}")

    summary_path = derived_signal_dir / "signal_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    manifest.add_file("signal_summary", "parsed", "signal pipeline", summary_path)
    audit.log(action="signal_pipeline_complete", result="success", output_path=str(summary_path))
    print(f"[*] Signal pipeline complete. Summary saved to {summary_path}")
    return summary


def _write_jsonl(path: Path, items: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
