"""E-RAKSHAK low-level WhatsApp root and import acquisition module.

Provides low-level functions for checking root access, package detection,
and pulling/copying files from rooted ADB devices or imported filesystem dumps.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any, Optional

from erakshak.case.hashing import hash_file

# Support packages
SUPPORTED_PACKAGES = ["com.whatsapp", "com.whatsapp.w4b"]


def parse_dumpsys_package_root(text: str, package_name: str) -> dict[str, Any]:
    """Parse output of ``dumpsys package <package>`` and return attributes."""
    info: dict[str, Any] = {
        "package_name": package_name,
        "version_name": None,
        "version_code": None,
        "first_install_time": None,
        "last_update_time": None,
        "data_dir": None,
        "uid": None,
        "is_system_app": False,
    }
    if not text:
        return info

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("versionName="):
            info["version_name"] = line.split("=", 1)[1].strip()
        elif line.startswith("versionCode="):
            val = line.split("=", 1)[1].strip().split()[0]
            info["version_code"] = val
        elif line.startswith("firstInstallTime="):
            info["first_install_time"] = line.split("=", 1)[1].strip()
        elif line.startswith("lastUpdateTime="):
            info["last_update_time"] = line.split("=", 1)[1].strip()
        elif line.startswith("dataDir="):
            info["data_dir"] = line.split("=", 1)[1].strip()
        elif line.startswith("userId=") or line.startswith("appId="):
            info["uid"] = line.split("=", 1)[1].strip()
        elif line.startswith("pkgFlags="):
            flags = line.split("=", 1)[1].strip()
            if "SYSTEM" in flags:
                info["is_system_app"] = True
    return info


def detect_root_access(adb_client: Any, serial: str) -> dict[str, Any]:
    """Run non-destructive checks to determine if root access is available."""
    warnings = []
    # Check 1: adb shell id
    try:
        id_res = adb_client.shell(["id"], audit_action="detect_root_id")
        if id_res.ok and "uid=0(root)" in id_res.stdout:
            return {
                "root_available": True,
                "method": "adb_root",
                "raw_id": id_res.stdout.strip(),
                "warnings": [],
            }
        elif not id_res.ok and id_res.stderr:
            warnings.append(f"shell id failed: {id_res.stderr.strip()}")
    except Exception as e:
        warnings.append(f"shell id failed with exception: {str(e)}")

    # Check 2: adb shell su -c id
    try:
        su_res = adb_client.shell(["su", "-c", "id"], audit_action="detect_root_su")
        if su_res.ok and "uid=0(root)" in su_res.stdout:
            return {
                "root_available": True,
                "method": "su",
                "raw_id": su_res.stdout.strip(),
                "warnings": warnings,
            }
        elif not su_res.ok and su_res.stderr:
            warnings.append(f"su -c id failed: {su_res.stderr.strip()}")
    except Exception as e:
        warnings.append(f"su -c id failed with exception: {str(e)}")

    # Check 3: adb shell su 0 id (for emulator root support)
    try:
        su0_res = adb_client.shell(["su", "0", "id"], audit_action="detect_root_su_0")
        if su0_res.ok and "uid=0(root)" in su0_res.stdout:
            return {
                "root_available": True,
                "method": "su_0",
                "raw_id": su0_res.stdout.strip(),
                "warnings": warnings,
            }
        elif not su0_res.ok and su0_res.stderr:
            warnings.append(f"su 0 id failed: {su0_res.stderr.strip()}")
    except Exception as e:
        warnings.append(f"su 0 id failed with exception: {str(e)}")

    raw_id = ""
    return {
        "root_available": False,
        "method": "none",
        "raw_id": raw_id,
        "warnings": warnings,
    }


def detect_whatsapp_packages(adb_client: Any, serial: str) -> list[dict[str, Any]]:
    """Query package manager for WhatsApp variants and get package details."""
    packages_found = []
    pm_res = adb_client.shell(["pm", "list", "packages"], audit_action="list_packages")
    if not pm_res.ok:
        return []

    package_names = []
    for line in pm_res.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            pkg_name = line.split(":", 1)[1].strip()
            if pkg_name in SUPPORTED_PACKAGES:
                package_names.append(pkg_name)

    for pkg in package_names:
        dumpsys_res = adb_client.shell(["dumpsys", "package", pkg], audit_action=f"dumpsys_{pkg}")
        if dumpsys_res.ok:
            info = parse_dumpsys_package_root(dumpsys_res.stdout, pkg)
            packages_found.append(info)
        else:
            packages_found.append({
                "package_name": pkg,
                "version_name": None,
                "version_code": None,
                "first_install_time": None,
                "last_update_time": None,
                "data_dir": None,
                "uid": None,
                "is_system_app": False,
            })
    return packages_found


def safe_extract_tar(
    tar_path: Path,
    extract_dir: Path,
    audit_logger: Optional[Any] = None,
    case_id: str = "",
    exhibit_id: str = "",
) -> list[str]:
    """Extract a tar archive safely relative to extract_dir, enforcing security checks."""
    warnings = []
    extract_dir = Path(extract_dir).resolve()
    extract_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path, "r") as tar:
        members = []
        for member in tar.getmembers():
            name = member.name

            # Reject links (symlinks/hardlinks)
            if member.issym() or member.islnk():
                warn_msg = f"Skipping symlink/hardlink tar member: {name}"
                warnings.append(warn_msg)
                if audit_logger:
                    audit_logger.log(
                        action="whatsapp_tar_member_skipped",
                        result="warning",
                        warning=warn_msg,
                    )
                continue

            # Reject absolute paths or Windows drive letters
            clean_name = name.lstrip("/")
            # Check for drive letter or leading slash / backslash
            if ":" in clean_name or clean_name.startswith(("/", "\\")):
                warn_msg = f"Skipping member with drive/absolute path: {name}"
                warnings.append(warn_msg)
                if audit_logger:
                    audit_logger.log(
                        action="whatsapp_tar_member_skipped",
                        result="warning",
                        warning=warn_msg,
                    )
                continue

            # Reject path traversal (..)
            parts = re.split(r"[/\\]", clean_name)
            if ".." in parts:
                warn_msg = f"Skipping path traversal member: {name}"
                warnings.append(warn_msg)
                if audit_logger:
                    audit_logger.log(
                        action="whatsapp_tar_member_skipped",
                        result="warning",
                        warning=warn_msg,
                    )
                continue

            # Enforce destination directory boundaries
            target_path = (extract_dir / clean_name).resolve()
            if not str(target_path).startswith(str(extract_dir)):
                warn_msg = f"Skipping out-of-bounds member: {name}"
                warnings.append(warn_msg)
                if audit_logger:
                    audit_logger.log(
                        action="whatsapp_tar_member_skipped",
                        result="warning",
                        warning=warn_msg,
                    )
                continue

            # Assign sanitised name relative to extract_dir
            member.name = clean_name
            members.append(member)

        tar.extractall(path=extract_dir, members=members)
    return warnings


def prune_cache_dir(cache_dir: Path, max_bytes: int) -> None:
    """Prune files in cache_dir recursively until total size is below max_bytes."""
    if not cache_dir.is_dir():
        return
    files = []
    for f in cache_dir.rglob("*"):
        if f.is_file():
            files.append((f, f.stat().st_size))

    total_size = sum(sz for _, sz in files)
    if total_size <= max_bytes:
        return

    # Sort files: largest size first to prune efficiently
    files.sort(key=lambda x: x[1], reverse=True)

    for f, sz in files:
        try:
            f.unlink()
            total_size -= sz
            if total_size <= max_bytes:
                break
        except OSError:
            pass


def acquire_whatsapp_rooted_device(
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
    audit_logger: Optional[Any] = None,
) -> dict[str, Any]:
    """Acquire WhatsApp private data and media directories from a rooted device via ADB."""
    from erakshak.adb.client import ADBClient

    if adb_client is None:
        adb_client = ADBClient(serial=serial, adb_path="adb")

    output_root = Path(output_root)
    dest_package_root = (
        output_root
        / case_id
        / exhibit_id
        / "raw"
        / "apps"
        / "whatsapp"
        / "rooted"
        / package_name
    )
    dest_package_root.mkdir(parents=True, exist_ok=True)

    # 1. Determine root method
    root_info = detect_root_access(adb_client, serial)
    root_method = root_info["method"]

    acquired_files = []
    skipped_files = []
    warnings = []
    errors = []

    # 2. Map remote paths
    paths_to_acquire = [
        {"type": "data", "path": f"/data/data/{package_name}/databases", "required": True},
        {"type": "data", "path": f"/data/data/{package_name}/shared_prefs", "required": True},
    ]

    if include_files:
        paths_to_acquire.append({"type": "data", "path": f"/data/data/{package_name}/files", "required": False})

    if include_cache:
        paths_to_acquire.append({"type": "data", "path": f"/data/data/{package_name}/cache", "required": False})

    if include_shared_media:
        if package_name == "com.whatsapp.w4b":
            paths_to_acquire.append({"type": "sdcard", "path": "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business", "required": False})
            paths_to_acquire.append({"type": "sdcard", "path": "/sdcard/WhatsApp Business", "required": False})
        else:
            paths_to_acquire.append({"type": "sdcard", "path": "/sdcard/Android/media/com.whatsapp/WhatsApp", "required": False})
            paths_to_acquire.append({"type": "sdcard", "path": "/sdcard/WhatsApp", "required": False})

    # Find the adb path token
    adb_path = getattr(adb_client, "adb_path", "adb")

    for item in paths_to_acquire:
        remote_path = item["path"]
        is_required = item["required"]
        is_sdcard = item["type"] == "sdcard"

        # Check if remote path exists
        # su or standard shell depending on path
        check_cmd = ["ls", "-d", remote_path]
        if not is_sdcard and root_method == "su":
            check_cmd = ["su", "-c", f"ls -d {remote_path}"]
        elif not is_sdcard and root_method == "su_0":
            check_cmd = ["su", "0", f"ls -d {remote_path}"]

        check_res = adb_client.shell(check_cmd)
        if not check_res.ok or "no such" in check_res.stderr.lower() or "not found" in check_res.stderr.lower():
            if is_required:
                errors.append(f"Required path {remote_path} is missing on device.")
            else:
                skipped_files.append({"source_path": remote_path, "status": "not_present"})
            continue

        # Decide copy strategy
        success = False
        method_used = "adb_pull"

        # Tar is only supported/needed for private app data paths (/data/data/...)
        if not is_sdcard and root_method != "none":
            temp_tar_name = f"temp_{remote_path.replace('/', '_')}.tar"
            temp_tar_path = dest_package_root / temp_tar_name

            # Build exec-out command
            if root_method == "su":
                cmd = [adb_path]
                if serial and serial != "auto":
                    cmd += ["-s", serial]
                cmd += ["exec-out", "su", "-c", f"tar -cf - {remote_path} 2>/dev/null"]
                method_used = "exec_out_tar_su"
            elif root_method == "su_0":
                cmd = [adb_path]
                if serial and serial != "auto":
                    cmd += ["-s", serial]
                cmd += ["exec-out", "su", "0", f"tar -cf - {remote_path} 2>/dev/null"]
                method_used = "exec_out_tar_su_0"
            else:
                cmd = [adb_path]
                if serial and serial != "auto":
                    cmd += ["-s", serial]
                cmd += ["exec-out", "tar", "-cf", "-", remote_path]
                method_used = "exec_out_tar_adb_root"

            try:
                # Capture bytes directly (no text processing)
                tar_proc = subprocess.run(cmd, capture_output=True, timeout=timeout_seconds)
                if tar_proc.returncode == 0 and len(tar_proc.stdout) > 512:
                    with open(temp_tar_path, "wb") as f:
                        f.write(tar_proc.stdout)

                    # Extract safely
                    tar_warns = safe_extract_tar(temp_tar_path, dest_package_root, audit_logger, case_id, exhibit_id)
                    warnings.extend(tar_warns)
                    success = True
                else:
                    warnings.append(f"tar execution returned empty or failed for {remote_path}. Falling back to adb pull.")
            except Exception as e:
                warnings.append(f"tar failed for {remote_path}: {str(e)}. Falling back to adb pull.")
            finally:
                if temp_tar_path.exists():
                    try:
                        temp_tar_path.unlink()
                    except OSError:
                        pass

        # Fallback to adb pull if tar didn't run/failed, or if it is on sdcard
        if not success:
            local_dest = dest_package_root / remote_path.lstrip("/")
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            method_used = "adb_pull_fallback"

            pull_res = adb_client.pull(remote_path, str(local_dest.parent), timeout=timeout_seconds)
            if pull_res.ok and local_dest.exists():
                success = True
            else:
                if is_required:
                    errors.append(f"Failed to acquire required path {remote_path} via adb pull.")
                else:
                    skipped_files.append({"source_path": remote_path, "status": "failed"})

        # Record acquired files
        if success:
            local_target_dir = dest_package_root / remote_path.lstrip("/")
            if local_target_dir.is_dir():
                for root_dir, _, filenames in os.walk(local_target_dir):
                    for fname in filenames:
                        file_path = Path(root_dir) / fname
                        rel_path = file_path.relative_to(dest_package_root)
                        src_path_on_device = "/" + str(rel_path).replace("\\", "/")
                        
                        sha = hash_file(file_path)
                        size = file_path.stat().st_size
                        acquired_files.append({
                            "source_path": src_path_on_device,
                            "destination_path": file_path,
                            "size_bytes": size,
                            "sha256": sha,
                            "acquisition_method": method_used,
                            "status": "acquired",
                        })

    # Cache pruning logic
    if include_cache and max_cache_bytes is not None:
        local_cache_path = dest_package_root / "data" / "data" / package_name / "cache"
        if local_cache_path.is_dir():
            prune_cache_dir(local_cache_path, max_cache_bytes)

            # Re-verify acquired files lists (remove pruned ones)
            acquired_files = [x for x in acquired_files if Path(x["destination_path"]).exists()]

    status = "success"
    if errors:
        status = "failed"
    elif warnings:
        status = "partial"

    return {
        "status": status,
        "acquired_files": acquired_files,
        "skipped_files": skipped_files,
        "warnings": warnings,
        "errors": errors,
    }


def acquire_whatsapp_from_import(
    case_id: str,
    exhibit_id: str,
    import_root: Path,
    output_root: Path,
    package_name: str = "com.whatsapp",
) -> dict[str, Any]:
    """Locate and copy WhatsApp data directories recursively from an imported filesystem dump."""
    import_root = Path(import_root)
    output_root = Path(output_root)
    dest_package_root = (
        output_root
        / case_id
        / exhibit_id
        / "raw"
        / "apps"
        / "whatsapp"
        / "imported"
        / package_name
    )
    dest_package_root.mkdir(parents=True, exist_ok=True)

    acquired_files = []
    skipped_files = []
    warnings = []
    errors = []

    # 1. Locate private data folder containing "databases" or "files" or "shared_prefs"
    private_dir = None
    for p in import_root.rglob(package_name):
        if p.is_dir() and (
            (p / "databases").is_dir()
            or (p / "files").is_dir()
            or (p / "shared_prefs").is_dir()
        ):
            private_dir = p
            break

    # 2. Locate shared media folder
    media_dir_name = "WhatsApp Business" if package_name == "com.whatsapp.w4b" else "WhatsApp"
    media_root = None
    for p in import_root.rglob(media_dir_name):
        if p.is_dir() and ((p / "Media").is_dir() or (p / "Databases").is_dir()):
            media_root = p
            break

    # 3. Copy private data
    if private_dir:
        # Destination inside raw imported folder: data/data/<package_name>/
        local_private_dest = dest_package_root / "data" / "data" / package_name
        local_private_dest.mkdir(parents=True, exist_ok=True)

        for sub in ["databases", "files", "shared_prefs", "cache"]:
            sub_src = private_dir / sub
            if sub_src.is_dir():
                sub_dest = local_private_dest / sub
                # Copy tree
                shutil.copytree(sub_src, sub_dest, dirs_exist_ok=True)
            else:
                skipped_files.append({
                    "source_path": f"/data/data/{package_name}/{sub}",
                    "status": "not_present",
                })
    else:
        errors.append(f"Private data directory for {package_name} not found in import_root.")

    # 4. Copy shared media
    if media_root:
        # Check parent folder: was it under Android/media/com.whatsapp/WhatsApp or sdcard/WhatsApp?
        # We can reconstruct it based on the presence of com.whatsapp in the parent path
        is_android_media = "com.whatsapp" in str(media_root.parent).lower()
        if is_android_media:
            local_media_dest = dest_package_root / "sdcard" / "Android" / "media" / package_name / media_dir_name
        else:
            local_media_dest = dest_package_root / "sdcard" / media_dir_name

        local_media_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(media_root, local_media_dest, dirs_exist_ok=True)
    else:
        skipped_files.append({
            "source_path": f"/sdcard/{media_dir_name}",
            "status": "not_present",
        })

    # 5. Scan and Hash
    for root_dir, _, filenames in os.walk(dest_package_root):
        for fname in filenames:
            file_path = Path(root_dir) / fname
            # Determine target relative path
            rel_path = file_path.relative_to(dest_package_root)
            src_path_in_import = "/" + str(rel_path).replace("\\", "/")

            sha = hash_file(file_path)
            size = file_path.stat().st_size
            acquired_files.append({
                "source_path": src_path_in_import,
                "destination_path": file_path,
                "size_bytes": size,
                "sha256": sha,
                "acquisition_method": "imported_copy",
                "status": "acquired",
            })

    status = "success"
    if errors:
        status = "failed"
    elif warnings:
        status = "partial"

    return {
        "status": status,
        "acquired_files": acquired_files,
        "skipped_files": skipped_files,
        "warnings": warnings,
        "errors": errors,
    }
