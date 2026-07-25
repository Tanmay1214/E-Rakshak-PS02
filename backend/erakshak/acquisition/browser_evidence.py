"""Browser evidence acquisition and parsing module for E-RAKSHAK.

Identifies installed browsers, copies their databases in root or imported modes,
and parses visits, searches, and downloads.
"""

import json
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from erakshak.adb.client import ADBClient, ADBResult
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.config.defaults import (
    DEFAULT_ADB_TIMEOUT,
    STATUS_ACQUIRED,
    STATUS_FAILED,
    STATUS_NOT_EXPOSED,
)
from erakshak.parsers.chromium_history import parse_chromium_history
from erakshak.acquisition.whatsapp_root import detect_root_access, safe_extract_tar


SUPPORTED_BROWSERS = {
    "com.android.chrome": "Chrome",
    "com.chrome.beta": "Chrome Beta",
    "com.chrome.dev": "Chrome Dev",
    "com.brave.browser": "Brave",
    "com.microsoft.emmx": "Edge",
    "com.opera.browser": "Opera",
    "org.mozilla.firefox": "Firefox",
}


def acquire_browser_evidence(
    adb: ADBClient,
    case_folder: CaseFolder,
    manifest: ManifestWriter,
    audit: AuditLogger,
    mode: str = "non-root",
    import_root: Optional[str] = None,
    case_id: str = "",
    exhibit_id: str = "",
) -> dict[str, Any]:
    """Acquire and parse browser history, downloads, and searches."""
    started_at = datetime.now(timezone.utc).isoformat()
    warnings = []
    installed_browsers = []
    parsed_browsers = []
    not_accessible = []

    # 1. Setup paths
    raw_browser_dir = case_folder.exhibit_path / "raw" / "browser"
    raw_browser_dir.mkdir(parents=True, exist_ok=True)

    processed_browser_dir = case_folder.exhibit_path / "processed" / "browser"
    processed_browser_dir.mkdir(parents=True, exist_ok=True)

    derived_dir = case_folder.derived_dir
    derived_dir.mkdir(parents=True, exist_ok=True)

    history_records = []
    search_records = []
    download_records = []

    # 2. Detect installed packages (for non-root/rooted modes)
    if mode in ("non-root", "rooted"):
        pm_res = adb.shell(["pm", "list", "packages"], audit_action="list_packages_browser")
        if pm_res.ok:
            for line in pm_res.stdout.splitlines():
                line = line.strip()
                if line.startswith("package:"):
                    pkg_name = line.split(":", 1)[1].strip()
                    if pkg_name in SUPPORTED_BROWSERS:
                        installed_browsers.append(pkg_name)
        else:
            warnings.append("Could not list packages via pm list packages.")

    # 3. Process according to Mode
    if mode == "non-root":
        # Report inaccessible history due to sandbox
        for pkg in installed_browsers:
            not_accessible.append(pkg)
        warnings.append("Chrome history not accessible in non-root mode due to Android app sandboxing.")

    elif mode == "rooted":
        # Detect root access
        root_info = detect_root_access(adb, adb.serial)
        root_method = root_info["method"]
        adb_path = getattr(adb, "adb_path", "adb")
        serial = adb.serial

        if not root_info["root_available"]:
            warnings.append("Root access not available. Falling back to non-root mode reporting.")
            for pkg in installed_browsers:
                not_accessible.append(pkg)
            warnings.append("Chrome history not accessible in non-root mode due to Android app sandboxing.")
        else:
            # We have root access, attempt Chromium extraction
            for pkg in installed_browsers:
                # Firefox is detection-only for root mode
                if pkg == "org.mozilla.firefox":
                    not_accessible.append(pkg)
                    warnings.append("Firefox history parsing is detection-only.")
                    continue

                browser_name = SUPPORTED_BROWSERS[pkg]
                pkg_success = False
                
                # Check profiles
                for profile in ("Default", "Profile 1", "Profile 2"):
                    remote_profile_dir = f"/data/data/{pkg}/app_chrome/{profile}"
                    # Check if profile dir exists on device using su
                    check_cmd = ["su", "-c", f"ls -d {remote_profile_dir}"]
                    if root_method == "su_0":
                        check_cmd = ["su", "0", f"ls -d {remote_profile_dir}"]
                    elif root_method == "adb_root":
                        check_cmd = ["ls", "-d", remote_profile_dir]

                    check_res = adb.shell(check_cmd)
                    if not check_res.ok or "no such" in check_res.stderr.lower() or "not found" in check_res.stderr.lower():
                        continue

                    # Tar copy profile databases
                    temp_tar_name = f"browser_{pkg}_{profile}.tar"
                    temp_tar_path = raw_browser_dir / temp_tar_name
                    
                    # Command to tar the History database group
                    tar_cmd = f"tar -C / -cf - data/data/{pkg}/app_chrome/{profile}/History data/data/{pkg}/app_chrome/{profile}/History-wal data/data/{pkg}/app_chrome/{profile}/History-shm 2>/dev/null"
                    
                    if root_method == "su":
                        cmd = [adb_path]
                        if serial and serial != "auto":
                            cmd += ["-s", serial]
                        cmd += ["exec-out", "su", "-c", tar_cmd]
                    elif root_method == "su_0":
                        cmd = [adb_path]
                        if serial and serial != "auto":
                            cmd += ["-s", serial]
                        cmd += ["exec-out", "su", "0", tar_cmd]
                    else:
                        cmd = [adb_path]
                        if serial and serial != "auto":
                            cmd += ["-s", serial]
                        cmd += ["exec-out", "tar", "-C", "/", "-cf", "-", f"data/data/{pkg}/app_chrome/{profile}/History", f"data/data/{pkg}/app_chrome/{profile}/History-wal", f"data/data/{pkg}/app_chrome/{profile}/History-shm"]

                    try:
                        proc = subprocess.run(cmd, capture_output=True, timeout=DEFAULT_ADB_TIMEOUT)
                        if proc.returncode == 0 and len(proc.stdout) > 512:
                            with open(temp_tar_path, "wb") as f:
                                f.write(proc.stdout)
                            
                            # Extract tar into raw
                            safe_extract_tar(temp_tar_path, raw_browser_dir, audit, case_id, exhibit_id)
                            
                            # Move extracted files to raw/browser/<package>/<profile>/
                            src_history_dir = raw_browser_dir / "data" / "data" / pkg / "app_chrome" / profile
                            dest_profile_dir = raw_browser_dir / pkg / profile
                            dest_profile_dir.mkdir(parents=True, exist_ok=True)
                            
                            for filename in ("History", "History-wal", "History-shm"):
                                file_path = src_history_dir / filename
                                if file_path.is_file():
                                    shutil.copy2(file_path, dest_profile_dir / filename)
                                    
                            # Cleanup temp data folders inside raw_browser_dir
                            if (raw_browser_dir / "data").exists():
                                shutil.rmtree(raw_browser_dir / "data")
                                
                            # Create parser-ready processed copy
                            proc_profile_dir = processed_browser_dir / pkg / profile
                            proc_profile_dir.mkdir(parents=True, exist_ok=True)
                            local_history = proc_profile_dir / "History"
                            
                            shutil.copy2(dest_profile_dir / "History", local_history)
                            for filename in ("History-wal", "History-shm"):
                                sidecar = dest_profile_dir / filename
                                if sidecar.is_file():
                                    shutil.copy2(sidecar, proc_profile_dir / filename)
                                    
                            # Add raw and processed database files to manifest
                            manifest.add_file(
                                artifact_class="browser_raw_db",
                                source_type="adb_command",
                                source_command_or_path=f"su tar of {pkg} History",
                                destination_path=dest_profile_dir / "History",
                                status=STATUS_ACQUIRED,
                                started_at=started_at,
                            )
                            
                            # Parse History
                            parsed_data = parse_chromium_history(local_history, browser_name, pkg, profile)
                            history_records.extend(parsed_data["history"])
                            search_records.extend(parsed_data["searches"])
                            download_records.extend(parsed_data["downloads"])
                            pkg_success = True
                            
                    except Exception as e:
                        warnings.append(f"Failed extracting {pkg} profile {profile}: {e}")
                    finally:
                        if temp_tar_path.is_file():
                            try:
                                temp_tar_path.unlink()
                            except OSError:
                                pass
                                
                if pkg_success:
                    parsed_browsers.append(pkg)
                else:
                    not_accessible.append(pkg)

    elif mode == "imported":
        if not import_root or not Path(import_root).is_dir():
            warnings.append(f"Import root dir does not exist: {import_root}")
        else:
            import_root_path = Path(import_root)
            # Recursively scan for files named "History"
            for history_file in import_root_path.glob("**/History"):
                if not history_file.is_file():
                    continue
                
                # Deduce package and profile from path
                # Path should match: .../<package>/app_chrome/<profile>/History
                parts = history_file.parts
                pkg = None
                profile = "Default"
                
                # Look for package name in the path parts
                for part in parts:
                    if part in SUPPORTED_BROWSERS:
                        pkg = part
                        break
                        
                # Look for profile
                for p_name in ("Default", "Profile 1", "Profile 2"):
                    if p_name in parts:
                        profile = p_name
                        break
                        
                if not pkg:
                    # Fallback to Chrome if not matching, but log warning
                    pkg = "com.android.chrome"
                    
                browser_name = SUPPORTED_BROWSERS.get(pkg, "Chrome")
                
                # Setup output folders
                dest_profile_dir = raw_browser_dir / pkg / profile
                dest_profile_dir.mkdir(parents=True, exist_ok=True)
                
                proc_profile_dir = processed_browser_dir / pkg / profile
                proc_profile_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy History and sidecars
                shutil.copy2(history_file, dest_profile_dir / "History")
                shutil.copy2(history_file, proc_profile_dir / "History")
                
                for sidecar_ext in ("-wal", "-shm"):
                    sidecar_file = history_file.parent / f"History{sidecar_ext}"
                    if sidecar_file.is_file():
                        shutil.copy2(sidecar_file, dest_profile_dir / f"History{sidecar_ext}")
                        shutil.copy2(sidecar_file, proc_profile_dir / f"History{sidecar_ext}")
                        
                manifest.add_file(
                    artifact_class="browser_raw_db",
                    source_type="imported_file",
                    source_command_or_path=str(history_file),
                    destination_path=dest_profile_dir / "History",
                    status=STATUS_ACQUIRED,
                    started_at=started_at,
                )
                
                # Parse History
                parsed_data = parse_chromium_history(proc_profile_dir / "History", browser_name, pkg, profile)
                history_records.extend(parsed_data["history"])
                search_records.extend(parsed_data["searches"])
                download_records.extend(parsed_data["downloads"])
                
                if pkg not in parsed_browsers:
                    parsed_browsers.append(pkg)

    # 4. Write output JSONL files
    hist_jsonl = derived_dir / "browser_history.jsonl"
    with open(hist_jsonl, "w", encoding="utf-8") as f:
        for r in history_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest.add_file(
        artifact_class="browser_history",
        source_type="parsed",
        source_command_or_path="browser_evidence_acq",
        destination_path=hist_jsonl,
        status=STATUS_ACQUIRED if history_records else STATUS_NOT_EXPOSED,
    )

    searches_jsonl = derived_dir / "browser_searches.jsonl"
    with open(searches_jsonl, "w", encoding="utf-8") as f:
        for r in search_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest.add_file(
        artifact_class="browser_searches",
        source_type="parsed",
        source_command_or_path="browser_evidence_acq",
        destination_path=searches_jsonl,
        status=STATUS_ACQUIRED if search_records else STATUS_NOT_EXPOSED,
    )

    downloads_jsonl = derived_dir / "browser_downloads.jsonl"
    with open(downloads_jsonl, "w", encoding="utf-8") as f:
        for r in download_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest.add_file(
        artifact_class="browser_downloads",
        source_type="parsed",
        source_command_or_path="browser_evidence_acq",
        destination_path=downloads_jsonl,
        status=STATUS_ACQUIRED if download_records else STATUS_NOT_EXPOSED,
    )

    # 5. Write browser_summary.json
    summary_path = derived_dir / "browser_summary.json"
    summary_data = {
        "case_id": case_id,
        "exhibit_id": exhibit_id,
        "mode": mode,
        "installed_browsers": installed_browsers,
        "parsed_browsers": parsed_browsers,
        "history_records": len(history_records),
        "search_records": len(search_records),
        "download_records": len(download_records),
        "not_accessible": not_accessible,
        "warnings": warnings,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    manifest.add_file(
        artifact_class="browser_summary",
        source_type="parsed",
        source_command_or_path="browser_evidence_acq",
        destination_path=summary_path,
        status=STATUS_ACQUIRED,
    )

    # Log to audit trail
    audit.log(
        action="collect_browser_evidence",
        command_category="browser",
        command_redacted=f"mode={mode}",
        result="success" if parsed_browsers or mode == "non-root" else "failed",
        warning="; ".join(warnings) if warnings else None,
        output_path=str(summary_path),
    )

    return summary_data
