"""Inventory and optionally pull media files from the device.

Scans a configurable list of media-bearing directories on the device,
builds an index of every file found, and — when explicitly requested —
pulls files into the case folder within a caller-specified byte budget.

Target folders (default)
------------------------
- ``/sdcard/DCIM``
- ``/sdcard/Pictures``
- ``/sdcard/Movies``
- ``/sdcard/Download``
- ``/sdcard/WhatsApp/Media``
- ``/sdcard/Android/media``

Output artefacts
----------------
- ``derived/media_index.jsonl`` – one JSON object per file
- Pulled files (if enabled) go into ``raw/media/``
"""

from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_local_dest(base_dir: Path, filename: str, ext: str) -> Path:
    """Return a local path that does not collide with existing files.

    Appends ``_1``, ``_2``, … to the stem until a free name is found.
    """
    dest = base_dir / filename
    counter = 1
    stem = Path(filename).stem
    while dest.exists():
        dest = base_dir / f"{stem}_{counter}{ext}"
        counter += 1
    return dest


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def acquire_media(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
    *,
    media_days: int = 7,
    media_max_bytes: int = 2_147_483_648,
    pull_media: bool = False,
) -> dict:
    """Inventory and optionally pull media files.

    Parameters
    ----------
    adb : ADBClient
        Connected ADB wrapper.
    case_folder : CaseFolder
        Open case folder.
    manifest : ManifestWriter
        Manifest writer.
    audit : AuditLogger
        Audit trail logger.
    media_days : int, optional
        Only consider files modified within the last *media_days* days
        (advisory — used for filtering if timestamps are parseable).
        Defaults to ``7``.
    media_max_bytes : int, optional
        Maximum total bytes to pull.  Defaults to 2 GiB.
    pull_media : bool, optional
        If ``True``, actually pull files from the device into
        ``raw/media/``.  If ``False`` (the default), only build the
        inventory — no files are transferred.

    Returns
    -------
    dict
        Summary with ``status``, ``files_inventoried``,
        ``files_pulled``, ``total_bytes_pulled``, ``warnings``.
    """
    from erakshak.adb.parsers import parse_ls_output
    from erakshak.case.hashing import hash_file
    from erakshak.config.defaults import (
        MEDIA_TARGET_FOLDERS,
        MEDIA_PULL_TIMEOUT,
        DEFAULT_ADB_TIMEOUT,
        STATUS_ACQUIRED,
    )

    results: dict = {
        "status": STATUS_ACQUIRED,
        "files_inventoried": 0,
        "files_pulled": 0,
        "total_bytes_pulled": 0,
        "warnings": [],
    }

    all_files: list[dict] = []

    # ---- 1. List files in each target folder --------------------------------
    for folder in MEDIA_TARGET_FOLDERS:
        folder_label = folder.rstrip("/").split("/")[-1]
        ls_result = adb.shell(
            ["ls", "-laR", folder],
            timeout=DEFAULT_ADB_TIMEOUT,
            audit_action=f"media_ls_{folder_label}",
        )

        if ls_result.return_code != 0:
            stderr_lower = ls_result.stderr.lower()
            if "no such file" in stderr_lower or "not found" in stderr_lower:
                # Folder simply does not exist on this device — expected.
                continue
            results["warnings"].append(
                f"ls failed for {folder}: {ls_result.stderr[:200]}"
            )
            continue

        files = parse_ls_output(ls_result.stdout)
        for entry in files:
            entry["source_folder"] = folder
        all_files.extend(files)

    # ---- 2. Build media index (skip directory entries) ----------------------
    media_index: list[dict] = []
    bytes_pulled = 0

    for f_entry in all_files:
        if f_entry.get("type") == "directory":
            continue

        source_path: str = f_entry.get("path", "")
        filename: str = f_entry.get("filename", "")
        ext: str = Path(filename).suffix.lower() if filename else ""
        mime_type: str | None = (
            mimetypes.guess_type(filename)[0] if filename else None
        )
        size: int | None = f_entry.get("size")
        modified: str | None = f_entry.get("datetime")

        entry: dict = {
            "source_path": source_path,
            "filename": filename,
            "extension": ext,
            "mime_type": mime_type,
            "size": size,
            "modified_time": modified,
            "source_folder": f_entry.get("source_folder", ""),
            "pulled": False,
            "local_path": None,
            "sha256": None,
        }

        # ---- optional pull --------------------------------------------------
        if pull_media and size is not None and source_path:
            if bytes_pulled + (size or 0) <= media_max_bytes:
                local_dest = _safe_local_dest(
                    case_folder.raw_media_dir, filename, ext,
                )
                pull_result = adb.pull(
                    source_path,
                    str(local_dest),
                    timeout=MEDIA_PULL_TIMEOUT,
                    audit_action=f"media_pull_{filename}",
                )
                if pull_result.return_code == 0 and local_dest.exists():
                    entry["pulled"] = True
                    entry["local_path"] = str(local_dest)
                    entry["sha256"] = hash_file(local_dest)
                    bytes_pulled += local_dest.stat().st_size
                    results["files_pulled"] += 1
                    manifest.add_file(
                        "media_file", "adb_pull", source_path, local_dest,
                    )
                else:
                    results["warnings"].append(
                        f"pull failed: {source_path}"
                    )

        media_index.append(entry)

    # ---- 3. Write derived/media_index.jsonl ---------------------------------
    results["files_inventoried"] = len(media_index)
    results["total_bytes_pulled"] = bytes_pulled

    index_path: Path = case_folder.derived_dir / "media_index.jsonl"
    with open(index_path, "w", encoding="utf-8") as fh:
        for entry in media_index:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    manifest.add_file(
        "media_index", "parsed", "ls -laR + inventory", index_path,
    )

    # ---- 4. Finalise --------------------------------------------------------
    if results["warnings"]:
        results["status"] = "partial"

    audit.log(
        action="media_acquired",
        command_category="media",
        result=results["status"],
        output_path=str(index_path),
    )

    return results
