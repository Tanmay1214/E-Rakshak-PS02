"""Import exports from the Android collector companion app.

The collector app (built separately in Android Studio / Kotlin) exports
structured forensic data files from the device.  This module validates,
copies, hashes, and registers those exported files within the E-RAKSHAK
case folder.

Expected collector output files
--------------------------------
- ``calls.jsonl``
- ``sms.jsonl``
- ``mms.jsonl``
- ``media_index.jsonl``

The list of expected files is sourced from
``erakshak.config.defaults.COLLECTOR_EXPECTED_FILES``.

Output artefacts
----------------
- ``raw/collector/<filename>`` – validated copies of each export file

.. note::

   The collector app is **not** part of this Python tool.  It will be
   built separately.  This module only handles importing its output.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_jsonl(path: Path) -> tuple[bool, int, str | None]:
    """Validate that *path* contains well-formed JSONL.

    Returns
    -------
    tuple[bool, int, str | None]
        ``(is_valid, line_count, error_message)``.
    """
    line_count = 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line_num, line in enumerate(fh, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                json.loads(stripped)
                line_count += 1
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return False, line_count, f"line {line_num}: {exc}"
    return True, line_count, None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def import_collector_export(
    collector_folder: str | None,
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Import manually-exported collector files.

    Parameters
    ----------
    collector_folder : str or None
        Absolute path to the directory containing the collector app's
        exported JSONL files.  Pass ``None`` to skip import.
    case_folder : CaseFolder
        Open case folder.
    manifest : ManifestWriter
        Manifest writer.
    audit : AuditLogger
        Audit trail logger.

    Returns
    -------
    dict
        Summary with ``status``, ``imported_files``, ``warnings``.
    """
    from erakshak.case.hashing import hash_file
    from erakshak.config.defaults import (
        COLLECTOR_EXPECTED_FILES,
        STATUS_ACQUIRED,
        STATUS_FAILED,
    )

    results: dict = {
        "status": "not_applicable",
        "imported_files": [],
        "warnings": [],
    }

    # ---- guard: no folder supplied ------------------------------------------
    if not collector_folder:
        results["warnings"].append(
            "No collector export folder provided. "
            "The collector app must be built in Android Studio and "
            "its exports placed in a folder, then passed via "
            "--collector-export-folder."
        )
        audit.log(
            action="collector_import_skipped",
            command_category="collector",
            result="skipped",
            warning="No collector folder provided",
        )
        return results

    src = Path(collector_folder)

    # ---- guard: folder does not exist ---------------------------------------
    if not src.exists() or not src.is_dir():
        results["status"] = STATUS_FAILED
        results["warnings"].append(
            f"Collector export folder not found: {collector_folder}"
        )
        audit.log(
            action="collector_import_failed",
            command_category="collector",
            result="failed",
            error=f"Folder not found: {collector_folder}",
        )
        return results

    dest_dir: Path = case_folder.raw_collector_dir

    # ---- iterate over expected files ----------------------------------------
    imported: list[dict] = []

    for expected_file in COLLECTOR_EXPECTED_FILES:
        src_file = src / expected_file
        if not src_file.exists():
            results["warnings"].append(
                f"Expected collector file not found: {expected_file}"
            )
            continue

        # Validate JSONL structure
        is_valid, line_count, err_msg = _validate_jsonl(src_file)
        if not is_valid:
            results["warnings"].append(
                f"{expected_file}: invalid JSONL ({err_msg})"
            )
            continue

        if line_count == 0:
            results["warnings"].append(
                f"{expected_file}: file is empty (0 records)"
            )
            # Still import an empty-but-valid file — it represents a
            # legitimate "no data" state.

        # Copy into raw/collector/
        dest_file: Path = dest_dir / expected_file
        shutil.copy2(src_file, dest_file)

        # Hash the destination copy
        file_hash: str = hash_file(dest_file)

        # Record in manifest
        artifact_label = f"collector_{expected_file.replace('.jsonl', '')}"
        manifest.add_file(
            artifact_class=artifact_label,
            source_type="collector_import",
            source_command_or_path=str(src_file),
            destination_path=dest_file,
            status=STATUS_ACQUIRED,
        )

        imported.append({
            "file": expected_file,
            "records": line_count,
            "sha256": file_hash,
        })

    # ---- finalise -----------------------------------------------------------
    results["imported_files"] = imported
    results["status"] = STATUS_ACQUIRED if imported else "no_files_found"

    audit.log(
        action="collector_import_complete",
        command_category="collector",
        result=results["status"],
        output_path=str(dest_dir),
    )

    return results
