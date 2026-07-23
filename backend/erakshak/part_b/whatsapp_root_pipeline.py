"""E-RAKSHAK WhatsApp Root and Import Acquisition Pipeline Orchestrator.

Manages folder structures, executing root detection, package detection,
raw data copying/tarring, manifest recording, audit trail logging,
and parser-ready staging.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from erakshak.acquisition.whatsapp_root import (
    acquire_whatsapp_from_import,
    acquire_whatsapp_rooted_device,
    detect_root_access,
    detect_whatsapp_packages,
)
from erakshak.case.hashing import hash_file


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_whatsapp_manifest(manifest_path: Path, record: dict[str, Any]) -> None:
    """Append a single JSONL record to the acquisition manifest."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_sha256sum(sha256sums_path: Path, sha256: str, dest_path: Path) -> None:
    """Append the file hash and path to sha256sums.txt in coreutils format."""
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sha256sums_path, "a", encoding="utf-8") as f:
        f.write(f"{sha256}  {dest_path}\n")


def append_audit_event(
    audit_path: Path,
    case_id: str,
    exhibit_id: str,
    action: str,
    result: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Append a forensic audit event to the audit trail log."""
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": _now_iso(),
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "action": action,
        "result": result,
        "details": details or {},
    }
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def stage_parser_ready_files(
    case_id: str,
    exhibit_id: str,
    output_root: Path,
    package_name: str,
    source_type: str,  # rooted_adb | imported_filesystem
    raw_package_dir: Path,
    warnings_list: list[str],
) -> dict[str, Any]:
    """Copy msgstore.db, wa.db, associated sidecars, and media into the processed/ folder."""
    output_root = Path(output_root)
    exhibit_path = output_root / case_id / exhibit_id
    processed_dir = exhibit_path / "processed" / "apps" / "whatsapp" / "rooted" / package_name
    processed_dir.mkdir(parents=True, exist_ok=True)

    databases_found = []
    sidecars_found = []
    key_file_found = False
    media_found = False

    # 1. Databases and Sidecars
    # Raw private databases are located at: <raw_package_dir>/data/data/<package_name>/databases/
    raw_db_dir = raw_package_dir / "data" / "data" / package_name / "databases"
    
    # Priority databases
    db_names = ["msgstore.db", "wa.db", "axolotl.db", "chatsettings.db"]
    sidecar_exts = [".db-wal", ".db-shm", ".db-journal"]

    if raw_db_dir.is_dir():
        for db_name in db_names:
            raw_db_path = raw_db_dir / db_name
            if raw_db_path.is_file():
                databases_found.append(db_name)
                # Copy to processed/
                shutil.copy2(raw_db_path, processed_dir / db_name)
                
                # Check for sidecars
                for ext in sidecar_exts:
                    sidecar_name = db_name + ext.replace(".db", "")
                    raw_sidecar_path = raw_db_dir / sidecar_name
                    if raw_sidecar_path.is_file():
                        sidecars_found.append(sidecar_name)
                        shutil.copy2(raw_sidecar_path, processed_dir / sidecar_name)

    # 2. Key Files
    # Raw private files are located at: <raw_package_dir>/data/data/<package_name>/files/
    raw_files_dir = raw_package_dir / "data" / "data" / package_name / "files"
    key_names = ["key", "encrypted_backup.key"]
    if raw_files_dir.is_dir():
        for key_name in key_names:
            raw_key_path = raw_files_dir / key_name
            if raw_key_path.is_file():
                key_file_found = True
                # Stage it too so it is accessible in processed/
                shutil.copy2(raw_key_path, processed_dir / key_name)

    # 3. Media folder
    # Locate media folder in raw/
    media_candidates = [
        raw_package_dir / "sdcard" / "Android" / "media" / package_name / ("WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp"),
        raw_package_dir / "sdcard" / ("WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp"),
    ]

    for cand in media_candidates:
        if cand.is_dir():
            dest_media = processed_dir / "media"
            # Remove dest_media if it already exists
            if dest_media.exists():
                try:
                    if dest_media.is_dir():
                        shutil.rmtree(dest_media)
                    else:
                        dest_media.unlink()
                except OSError:
                    pass
            try:
                shutil.copytree(cand, dest_media, dirs_exist_ok=True)
                media_found = True
                break
            except Exception as e:
                warnings_list.append(f"Failed to copy media folder to processed: {str(e)}")

    # 4. Createderived/whatsapp_root_summary.json
    summary = {
        "app": "WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp",
        "package_name": package_name,
        "source_type": source_type,
        "databases_found": databases_found,
        "sidecars_found": sidecars_found,
        "key_file_found": key_file_found,
        "media_found": media_found,
        "parser_ready_path": str(processed_dir),
        "warnings": warnings_list,
    }

    derived_summary_path = exhibit_path / "derived" / "whatsapp_root_summary.json"
    derived_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(derived_summary_path, "w", encoding="utf-8") as sf:
        json.dump(summary, sf, indent=2)

    return summary


def run_whatsapp_root_adb_pipeline(
    case_id: str,
    exhibit_id: str,
    serial: str,
    output_root: Path,
    package_name: str = "com.whatsapp",
    include_cache: bool = True,
    include_files: bool = True,
    include_shared_media: bool = True,
    max_cache_bytes: Optional[int] = None,
    timeout_seconds: int = 600,
    adb_client: Optional[Any] = None,
) -> dict[str, Any]:
    """Orchestrates live rooted device acquisition and parser staging."""
    output_root = Path(output_root)
    exhibit_path = output_root / case_id / exhibit_id
    acquisition_dir = exhibit_path / "acquisition"
    audit_path = acquisition_dir / "audit.jsonl"
    manifest_path = acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = exhibit_path / "hashes" / "sha256sums.txt"

    from erakshak.adb.client import ADBClient
    if adb_client is None:
        adb_client = ADBClient(serial=serial, adb_path="adb")

    started_at = _now_iso()

    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_root_acquisition_started",
        result="success",
        details={"package_name": package_name, "serial": serial},
    )

    # 1. Root capability check
    root_info = detect_root_access(adb_client, serial)
    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_root_detected",
        result="success" if root_info["root_available"] else "failed",
        details=root_info,
    )

    if not root_info["root_available"]:
        err_msg = "Root access is not available. This mode requires an already-rooted device or imported filesystem dump."
        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action="whatsapp_root_acquisition_failed",
            result="failed",
            details={"error": err_msg},
        )
        return {"status": "failed", "error": err_msg}

    # 2. Package detection
    packages = detect_whatsapp_packages(adb_client, serial)
    target_package = next((p for p in packages if p["package_name"] == package_name), None)

    if not target_package:
        err_msg = f"Package {package_name} was not found on the device."
        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action="whatsapp_root_acquisition_failed",
            result="failed",
            details={"error": err_msg},
        )
        return {"status": "failed", "error": err_msg}

    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_package_detected",
        result="success",
        details=target_package,
    )

    # 3. Rooted acquisition
    raw_package_dir = exhibit_path / "raw" / "apps" / "whatsapp" / "rooted" / package_name
    raw_package_dir.mkdir(parents=True, exist_ok=True)

    acq_res = acquire_whatsapp_rooted_device(
        case_id=case_id,
        exhibit_id=exhibit_id,
        serial=serial,
        output_root=output_root,
        package_name=package_name,
        include_cache=include_cache,
        include_files=include_files,
        include_shared_media=include_shared_media,
        max_cache_bytes=max_cache_bytes,
        timeout_seconds=timeout_seconds,
        adb_client=adb_client,
        audit_logger=None,  # Handled locally
    )

    # Identify if expected core files are missing and report them as not_present
    core_files = [
        f"/data/data/{package_name}/databases/msgstore.db",
        f"/data/data/{package_name}/databases/wa.db",
        f"/data/data/{package_name}/files/key",
    ]
    acquired_source_paths = {x["source_path"] for x in acq_res["acquired_files"]}
    for cf in core_files:
        if cf not in acquired_source_paths:
            if not any(x["source_path"] == cf for x in acq_res["skipped_files"]):
                acq_res["skipped_files"].append({
                    "source_path": cf,
                    "status": "not_present"
                })

    warnings = acq_res["warnings"]
    errors = acq_res["errors"]

    # 4. Manifest logging & key safety checks
    for file_record in acq_res["acquired_files"]:
        # Safe logging for key files
        is_key_file = any(
            file_record["source_path"].endswith(suffix)
            for suffix in ["/files/key", "/files/encrypted_backup.key"]
        )

        dest_path = Path(file_record["destination_path"])
        rel_dest_path = dest_path.relative_to(exhibit_path)

        manifest_record = {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_root_artifact",
            "app": "WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp",
            "package_name": package_name,
            "source_type": "rooted_adb",
            "source_path": file_record["source_path"],
            "destination_path": str(rel_dest_path),
            "sha256": file_record["sha256"],
            "size_bytes": file_record["size_bytes"],
            "acquisition_method": file_record["acquisition_method"],
            "status": "acquired",
            "reason_code": "",
            "started_at": started_at,
            "completed_at": _now_iso(),
        }
        append_whatsapp_manifest(manifest_path, manifest_record)
        append_sha256sum(sha256sums_path, file_record["sha256"], dest_path)

        if is_key_file:
            append_audit_event(
                audit_path=audit_path,
                case_id=case_id,
                exhibit_id=exhibit_id,
                action="whatsapp_source_group_acquired",
                result="success",
                details={
                    "key_file_acquired": True,
                    "key_file_hash": file_record["sha256"],
                    "key_file_path": str(rel_dest_path),
                },
            )
        else:
            append_audit_event(
                audit_path=audit_path,
                case_id=case_id,
                exhibit_id=exhibit_id,
                action="whatsapp_source_path_checked",
                result="success",
                details={"source_path": file_record["source_path"], "status": "acquired"},
            )

    # Skipped files manifest entries
    for skip in acq_res["skipped_files"]:
        manifest_record = {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_root_artifact",
            "app": "WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp",
            "package_name": package_name,
            "source_type": "rooted_adb",
            "source_path": skip["source_path"],
            "destination_path": "",
            "sha256": "",
            "size_bytes": 0,
            "acquisition_method": "none",
            "status": skip["status"],
            "reason_code": skip["status"],
            "started_at": started_at,
            "completed_at": _now_iso(),
        }
        append_whatsapp_manifest(manifest_path, manifest_record)
        
        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action="whatsapp_source_group_missing",
            result="not_present",
            details={"source_path": skip["source_path"]},
        )

    # 5. Parser-ready staging
    if acq_res["status"] != "failed":
        summary = stage_parser_ready_files(
            case_id=case_id,
            exhibit_id=exhibit_id,
            output_root=output_root,
            package_name=package_name,
            source_type="rooted_adb",
            raw_package_dir=raw_package_dir,
            warnings_list=warnings,
        )
    else:
        summary = {}

    status_final = acq_res["status"]
    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_root_acquisition_completed" if status_final in ("success", "partial") else "whatsapp_root_acquisition_failed",
        result=status_final,
        details={"warnings": warnings, "errors": errors},
    )

    return {
        "status": status_final,
        "warnings": warnings,
        "errors": errors,
        "summary": summary,
    }


def run_whatsapp_root_import_pipeline(
    case_id: str,
    exhibit_id: str,
    import_root: Path,
    output_root: Path,
    package_name: str = "com.whatsapp",
) -> dict[str, Any]:
    """Orchestrates filesystem dump import and parser staging."""
    output_root = Path(output_root)
    exhibit_path = output_root / case_id / exhibit_id
    acquisition_dir = exhibit_path / "acquisition"
    audit_path = acquisition_dir / "audit.jsonl"
    manifest_path = acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = exhibit_path / "hashes" / "sha256sums.txt"

    started_at = _now_iso()

    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_import_acquisition_started",
        result="success",
        details={"package_name": package_name, "import_root": str(import_root)},
    )

    raw_package_dir = exhibit_path / "raw" / "apps" / "whatsapp" / "imported" / package_name
    raw_package_dir.mkdir(parents=True, exist_ok=True)

    acq_res = acquire_whatsapp_from_import(
        case_id=case_id,
        exhibit_id=exhibit_id,
        import_root=import_root,
        output_root=output_root,
        package_name=package_name,
    )

    # Identify if expected core files are missing and report them as not_present
    core_files = [
        f"/data/data/{package_name}/databases/msgstore.db",
        f"/data/data/{package_name}/databases/wa.db",
        f"/data/data/{package_name}/files/key",
    ]
    acquired_source_paths = {x["source_path"] for x in acq_res["acquired_files"]}
    for cf in core_files:
        if cf not in acquired_source_paths:
            if not any(x["source_path"] == cf for x in acq_res["skipped_files"]):
                acq_res["skipped_files"].append({
                    "source_path": cf,
                    "status": "not_present"
                })

    warnings = acq_res["warnings"]
    errors = acq_res["errors"]

    # Manifest logging
    for file_record in acq_res["acquired_files"]:
        is_key_file = any(
            file_record["source_path"].endswith(suffix)
            for suffix in ["/files/key", "/files/encrypted_backup.key"]
        )

        dest_path = Path(file_record["destination_path"])
        rel_dest_path = dest_path.relative_to(exhibit_path)

        manifest_record = {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_root_artifact",
            "app": "WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp",
            "package_name": package_name,
            "source_type": "imported_filesystem",
            "source_path": file_record["source_path"],
            "destination_path": str(rel_dest_path),
            "sha256": file_record["sha256"],
            "size_bytes": file_record["size_bytes"],
            "acquisition_method": "imported_copy",
            "status": "acquired",
            "reason_code": "",
            "started_at": started_at,
            "completed_at": _now_iso(),
        }
        append_whatsapp_manifest(manifest_path, manifest_record)
        append_sha256sum(sha256sums_path, file_record["sha256"], dest_path)

        if is_key_file:
            append_audit_event(
                audit_path=audit_path,
                case_id=case_id,
                exhibit_id=exhibit_id,
                action="whatsapp_source_group_acquired",
                result="success",
                details={
                    "key_file_acquired": True,
                    "key_file_hash": file_record["sha256"],
                    "key_file_path": str(rel_dest_path),
                },
            )
        else:
            append_audit_event(
                audit_path=audit_path,
                case_id=case_id,
                exhibit_id=exhibit_id,
                action="whatsapp_source_path_checked",
                result="success",
                details={"source_path": file_record["source_path"], "status": "acquired"},
            )

    # Skipped files manifest
    for skip in acq_res["skipped_files"]:
        manifest_record = {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_root_artifact",
            "app": "WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp",
            "package_name": package_name,
            "source_type": "imported_filesystem",
            "source_path": skip["source_path"],
            "destination_path": "",
            "sha256": "",
            "size_bytes": 0,
            "acquisition_method": "imported_copy",
            "status": skip["status"],
            "reason_code": skip["status"],
            "started_at": started_at,
            "completed_at": _now_iso(),
        }
        append_whatsapp_manifest(manifest_path, manifest_record)

        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action="whatsapp_source_group_missing",
            result="not_present",
            details={"source_path": skip["source_path"]},
        )

    # 5. Stage parser files
    if acq_res["status"] != "failed":
        summary = stage_parser_ready_files(
            case_id=case_id,
            exhibit_id=exhibit_id,
            output_root=output_root,
            package_name=package_name,
            source_type="imported_filesystem",
            raw_package_dir=raw_package_dir,
            warnings_list=warnings,
        )
    else:
        summary = {}

    status_final = acq_res["status"]
    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action="whatsapp_import_acquisition_completed" if status_final in ("success", "partial") else "whatsapp_import_acquisition_failed",
        result=status_final,
        details={"warnings": warnings, "errors": errors},
    )

    return {
        "status": status_final,
        "warnings": warnings,
        "errors": errors,
        "summary": summary,
    }
