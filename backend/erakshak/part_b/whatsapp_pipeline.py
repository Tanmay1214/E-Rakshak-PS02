"""WhatsApp Part B Decryption Pipeline Orchestrator for E-RAKSHAK.

Manages folder structures, file copies/adb pulls, key acquisition delegation,
key metadata recording, wadecrypt subprocess execution, and manifest/audit trails.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from erakshak.case.hashing import hash_file
from erakshak.part_b.whatsapp_key_capture import capture_whatsapp_backup_key
from erakshak.part_b.whatsapp_decrypt import (
    validate_hex_key,
    key_metadata,
    is_sqlite_database,
    decrypt_with_wadecrypt,
)


def append_manifest_record(manifest_path: Path, record: dict[str, Any]) -> None:
    """Appends a single JSONL record to the acquisition manifest."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_audit_event(
    audit_path: Path,
    case_id: str,
    exhibit_id: str,
    action: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Appends a forensic audit event to the audit trail log."""
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "action": action,
        "result": result,
        "details": details or {},
    }
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def append_sha256sum(sha256sums_path: Path, sha256: str, target_path: Path) -> None:
    """Appends the file hash and path to sha256sums.txt in coreutils format."""
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sha256sums_path, "a", encoding="utf-8") as f:
        f.write(f"{sha256}  {target_path}\n")


def is_remote_android_path(path_str: str) -> bool:
    """Checks if the path is a remote Android path (e.g. starts with /sdcard or /data)."""
    normalized = path_str.replace("\\", "/")
    if normalized.startswith(("/sdcard", "/data", "/storage", "sdcard/", "data/", "storage/")):
        return True
    if normalized.startswith("/") and not Path(path_str).exists():
        return True
    return False


def get_android_sdk(adb_path: str, serial: str | None) -> int:
    """Queries the connected Android device for its SDK API level."""
    adb_cmd = [adb_path]
    if serial:
        adb_cmd += ["-s", serial]
    adb_cmd += ["shell", "getprop", "ro.build.version.sdk"]
    try:
        res = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return int(res.stdout.strip())
    except Exception:
        pass
    return 30  # Default to SDK 30 (Android 11) if query fails


def resolve_whatsapp_remote_path(adb_path: str, serial: str | None, path_str: str) -> str:
    """Resolves correct remote path based on Android SDK version.

    For Android 11+ (SDK >= 30), standard database directory is:
        /sdcard/Android/media/com.whatsapp/WhatsApp/Databases/
    For Android 10 and below (SDK < 30), it is:
        /sdcard/WhatsApp/Databases/
    """
    sdk = get_android_sdk(adb_path, serial)
    normalized = path_str.replace("\\", "/").rstrip("/")
    
    is_databases_dir = normalized in (
        "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases",
        "/sdcard/WhatsApp/Databases",
        "sdcard/Android/media/com.whatsapp/WhatsApp/Databases",
        "sdcard/WhatsApp/Databases"
    )

    if is_databases_dir:
        if sdk >= 30:  # Android 11+
            return "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/"
        else:          # Android 10 and below
            return "/sdcard/WhatsApp/Databases/"
            
    return path_str


def find_msgstore_in_remote_dir(adb_path: str, serial: str | None, remote_dir: str) -> str | None:
    """Lists files in the remote directory and finds the active or latest msgstore database."""
    adb_cmd = [adb_path]
    if serial:
        adb_cmd += ["-s", serial]
    adb_cmd += ["shell", "ls", "-1", remote_dir]
    try:
        res = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            return None
        
        files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        
        # 1. Look for active backup database (msgstore.db.crypt15, msgstore.db.crypt14, etc.)
        active_candidates = []
        for f in files:
            if f.startswith("msgstore.db.crypt"):
                active_candidates.append(f)
        
        if active_candidates:
            active_candidates.sort(reverse=True)  # Sort descending to get highest crypt extension
            return remote_dir.rstrip("/") + "/" + active_candidates[0]
            
        # 2. Look for dated candidates (msgstore-YYYY-MM-DD.1.db.crypt15, etc.)
        dated_candidates = []
        for f in files:
            if f.startswith("msgstore-") and ".db.crypt" in f:
                dated_candidates.append(f)
                
        if dated_candidates:
            dated_candidates.sort()  # Lexicographical sort puts latest date last
            return remote_dir.rstrip("/") + "/" + dated_candidates[-1]
            
    except Exception:
        pass
    return None


def pull_file_from_device(adb_path: str, serial: str | None, remote_path: str, local_dest: Path) -> bool:
    """Pulls a remote file from the Android device to a local destination."""
    adb_cmd = [adb_path]
    if serial:
        adb_cmd += ["-s", serial]
    adb_cmd += ["pull", remote_path, str(local_dest)]
    try:
        res = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=300)
        return res.returncode == 0
    except Exception:
        return False


def run_whatsapp_key_capture_and_decrypt(
    case_id: str,
    exhibit_id: str,
    encrypted_backup_path: Path,
    output_root: Path,
    timeout_seconds: int = 300,
    adb_path: str = "adb",
    serial: str | None = None,
    hex_key_manual: str | None = None,
) -> dict[str, Any]:
    """Orchestrates WhatsApp backup copy/pull, key acquisition, metadata log, and decryption."""
    # 1. Setup paths
    exhibit_path = output_root / case_id / exhibit_id
    raw_enc_dir = exhibit_path / "raw" / "apps" / "whatsapp" / "encrypted"
    processed_dec_dir = exhibit_path / "processed" / "apps" / "whatsapp" / "decrypted"
    acquisition_dir = exhibit_path / "acquisition"
    hashes_dir = exhibit_path / "hashes"

    # Create directories
    raw_enc_dir.mkdir(parents=True, exist_ok=True)
    processed_dec_dir.mkdir(parents=True, exist_ok=True)
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    hashes_dir.mkdir(parents=True, exist_ok=True)

    audit_path = acquisition_dir / "audit.jsonl"
    manifest_path = acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = hashes_dir / "sha256sums.txt"

    # Initialize results
    pipeline_res: dict[str, Any] = {
        "status": "failed",
        "encrypted_backup_path": "",
        "decrypted_db_path": "",
        "encrypted_sha256": "",
        "decrypted_sha256": "",
        "sqlite_verified": False,
        "key_metadata": {},
        "error": None,
    }

    # Start Pipeline Audit
    append_audit_event(
        audit_path, case_id, exhibit_id,
        "whatsapp_decryption_pipeline_started", "success"
    )

    # 2. Verify and Copy/Pull Encrypted Backup
    backup_str = str(encrypted_backup_path)
    is_remote = is_remote_android_path(backup_str)
    
    dest_backup = None
    source_type = "operator_supplied_file"
    source_path_val = backup_str

    if is_remote:
        # Resolve target path based on Android version
        resolved_remote_dir = resolve_whatsapp_remote_path(adb_path, serial, backup_str)
        print(f"[*] Resolved remote path: {resolved_remote_dir}")
        
        # Check if resolved path is a directory (does not end with crypt extension)
        remote_file_path = resolved_remote_dir
        if not re.search(r"\.crypt\d+$", resolved_remote_dir.lower()):
            print(f"[*] Path is a remote directory. Searching for databases in {resolved_remote_dir}...")
            discovered_path = find_msgstore_in_remote_dir(adb_path, serial, resolved_remote_dir)
            if not discovered_path:
                err_msg = f"No WhatsApp backup database found in remote directory: {resolved_remote_dir}"
                append_audit_event(
                    audit_path, case_id, exhibit_id,
                    "whatsapp_backup_decryption_failed", "failed",
                    {"error": err_msg}
                )
                pipeline_res["error"] = err_msg
                return pipeline_res
            remote_file_path = discovered_path
            print(f"[+] Discovered backup on device: {remote_file_path}")
            
        dest_backup = raw_enc_dir / Path(remote_file_path).name
        source_path_val = remote_file_path
        
        print(f"[*] Pulling remote backup {remote_file_path} from device...")
        success = pull_file_from_device(adb_path, serial, remote_file_path, dest_backup)
        if not success:
            err_msg = f"Failed to pull WhatsApp backup from device: {remote_file_path}"
            append_audit_event(
                audit_path, case_id, exhibit_id,
                "whatsapp_backup_decryption_failed", "failed",
                {"error": err_msg}
            )
            pipeline_res["error"] = err_msg
            return pipeline_res
            
        source_type = "adb_pull"
        append_audit_event(
            audit_path, case_id, exhibit_id,
            "encrypted_backup_pulled", "success",
            {"remote_path": remote_file_path, "local_path": str(dest_backup)}
        )
    else:
        encrypted_backup_path = Path(encrypted_backup_path)
        if not encrypted_backup_path.exists():
            err_msg = f"Backup file not found: {encrypted_backup_path}"
            append_audit_event(
                audit_path, case_id, exhibit_id,
                "whatsapp_backup_decryption_failed", "failed",
                {"error": err_msg}
            )
            pipeline_res["error"] = err_msg
            return pipeline_res

        dest_backup = raw_enc_dir / encrypted_backup_path.name
        try:
            shutil.copy2(encrypted_backup_path, dest_backup)
            append_audit_event(
                audit_path, case_id, exhibit_id,
                "encrypted_backup_copied", "success"
            )
        except Exception as e:
            err_msg = f"Failed to copy backup file: {str(e)}"
            append_audit_event(
                audit_path, case_id, exhibit_id,
                "whatsapp_backup_decryption_failed", "failed",
                {"error": err_msg}
            )
            pipeline_res["error"] = err_msg
            return pipeline_res

    # 3. Hash Encrypted Backup
    enc_sha = hash_file(dest_backup)
    enc_size = dest_backup.stat().st_size
    pipeline_res["encrypted_backup_path"] = str(dest_backup)
    pipeline_res["encrypted_sha256"] = enc_sha
    
    append_sha256sum(sha256sums_path, enc_sha, dest_backup)

    # 4. Key Acquisition
    hex_key = None
    key_source_type = "authorized_ui_capture"
    
    try:
        if hex_key_manual:
            print("[*] Using manually provided encryption key...")
            hex_key = validate_hex_key(hex_key_manual)
            key_source_type = "manual_input"
        else:
            print("[*] Initiating automated key capture from device...")
            append_audit_event(
                audit_path, case_id, exhibit_id,
                "whatsapp_key_capture_started", "success"
            )
            hex_key = capture_whatsapp_backup_key(adb_path=adb_path, serial=serial)
            
            meta = key_metadata(hex_key)
            append_audit_event(
                audit_path, case_id, exhibit_id,
                "whatsapp_key_capture_completed", "success",
                meta
            )
    except Exception as e:
        err_msg = f"Key acquisition failed: {str(e)}"
        print(f"[-] {err_msg}")
        append_audit_event(
            audit_path, case_id, exhibit_id,
            "whatsapp_backup_decryption_failed", "failed",
            {"error": err_msg}
        )
        pipeline_res["error"] = err_msg
        
        # Manifest record for failure
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_encrypted_backup",
            "source_type": source_type,
            "source_path": source_path_val,
            "destination_path": str(dest_backup),
            "sha256": enc_sha,
            "size_bytes": enc_size,
            "status": "acquired"
        })
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_decrypted_msgstore",
            "source_type": "wadecrypt",
            "destination_path": "",
            "sha256": "",
            "size_bytes": 0,
            "status": "failed",
            "sqlite_verified": False
        })
        return pipeline_res

    # 5. Save Key Metadata
    meta = key_metadata(hex_key)
    pipeline_res["key_metadata"] = meta
    
    meta_path = raw_enc_dir / "key_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    meta_sha = hash_file(meta_path)
    meta_size = meta_path.stat().st_size
    append_sha256sum(sha256sums_path, meta_sha, meta_path)

    # 6. Decrypt
    output_db = processed_dec_dir / "msgstore.db"
    
    command_redacted = f"wadecrypt <REDACTED_KEY> {dest_backup} {output_db}"
    append_audit_event(
        audit_path, case_id, exhibit_id,
        "wadecrypt_invoked", "success",
        {
            "command_redacted": command_redacted,
            "tool": "wadecrypt",
            "tool_source": "wa-crypt-tools",
        }
    )

    dec_res = decrypt_with_wadecrypt(hex_key, dest_backup, output_db, timeout_seconds)
    
    # Dereference key
    hex_key = None
    del hex_key

    # 7. Check Decryption Outcome
    if dec_res["status"] == "success":
        dec_sha = hash_file(output_db)
        dec_size = output_db.stat().st_size
        
        pipeline_res["status"] = "success"
        pipeline_res["decrypted_db_path"] = str(output_db)
        pipeline_res["decrypted_sha256"] = dec_sha
        pipeline_res["sqlite_verified"] = True
        
        append_sha256sum(sha256sums_path, dec_sha, output_db)
        
        append_audit_event(
            audit_path, case_id, exhibit_id,
            "whatsapp_backup_decryption_completed", "success"
        )
        
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_encrypted_backup",
            "source_type": source_type,
            "source_path": source_path_val,
            "destination_path": str(dest_backup),
            "sha256": enc_sha,
            "size_bytes": enc_size,
            "status": "acquired"
        })
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_key_metadata",
            "source_type": key_source_type,
            "destination_path": str(meta_path),
            "sha256": meta_sha,
            "size_bytes": meta_size,
            "status": "metadata_recorded"
        })
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_decrypted_msgstore",
            "source_type": "wadecrypt",
            "destination_path": str(output_db),
            "sha256": dec_sha,
            "size_bytes": dec_size,
            "status": "decrypted",
            "sqlite_verified": True
        })
    else:
        err_msg = dec_res.get("error", "Decryption failed.")
        pipeline_res["error"] = err_msg
        
        append_audit_event(
            audit_path, case_id, exhibit_id,
            "whatsapp_backup_decryption_failed", "failed",
            {"error": err_msg}
        )
        
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_encrypted_backup",
            "source_type": source_type,
            "source_path": source_path_val,
            "destination_path": str(dest_backup),
            "sha256": enc_sha,
            "size_bytes": enc_size,
            "status": "acquired"
        })
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_key_metadata",
            "source_type": key_source_type,
            "destination_path": str(meta_path),
            "sha256": meta_sha,
            "size_bytes": meta_size,
            "status": "metadata_recorded"
        })
        append_manifest_record(manifest_path, {
            "case_id": case_id,
            "exhibit_id": exhibit_id,
            "artifact_class": "whatsapp_decrypted_msgstore",
            "source_type": "wadecrypt",
            "destination_path": "",
            "sha256": "",
            "size_bytes": 0,
            "status": "failed",
            "sqlite_verified": False
        })

    return pipeline_res


def run_whatsapp_unified_pipeline(
    case_id: str,
    exhibit_id: str,
    encrypted_backup_path: Path,
    output_root: Path,
    timeout_seconds: int = 300,
    adb_path: str = "adb",
    serial: str | None = None,
    hex_key_manual: str | None = None,
    time_offset: int | None = None,
    filter_date: str | None = None,
    filter_date_format: str | None = None,
) -> dict[str, Any]:
    """Runs the unified pipeline: UI key capture & decryption -> parsing & HTML/JSON report generation."""
    # 1. Run capture and decryption
    dec_res = run_whatsapp_key_capture_and_decrypt(
        case_id=case_id,
        exhibit_id=exhibit_id,
        encrypted_backup_path=encrypted_backup_path,
        output_root=output_root,
        timeout_seconds=timeout_seconds,
        adb_path=adb_path,
        serial=serial,
        hex_key_manual=hex_key_manual,
    )
    
    if dec_res["status"] != "success":
        return {
            "status": "failed",
            "error": f"Decryption stage failed: {dec_res.get('error', 'Unknown error')}"
        }
        
    # 2. Run parse and export pipeline
    from erakshak.part_b.whatsapp_parse_pipeline import parse_decrypted_whatsapp
    
    try:
        parse_res = parse_decrypted_whatsapp(
            case_id=case_id,
            exhibit_id=exhibit_id,
            output_root=output_root,
            input_dir=None,
            wa_db=None,
            media_dir=None,
            vcard_path=None,
            time_offset=time_offset,
            filter_date=filter_date,
            filter_date_format=filter_date_format
        )
        
        if parse_res["status"] == "success":
            return {
                "status": "success",
                "decryption": dec_res,
                "parsing": parse_res
            }
        else:
            return {
                "status": "failed",
                "error": f"Parsing stage failed: {parse_res.get('stderr', 'Unknown error')}",
                "decryption": dec_res
            }
    except Exception as e:
        return {
            "status": "failed",
            "error": f"Parsing stage crashed: {str(e)}",
            "decryption": dec_res
        }

