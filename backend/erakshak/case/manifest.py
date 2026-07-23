"""Streaming JSONL manifest writer for E-RAKSHAK.

Every raw and derived file created during an acquisition run is recorded
in ``manifest.jsonl``.  Each entry captures provenance (source command,
artefact class), integrity (SHA-256, size), and status.  A companion
``sha256sums.txt`` file is maintained in coreutils-compatible format.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from erakshak.case.hashing import hash_file
from erakshak.config.defaults import TOOL_VERSION


class ManifestWriter:
    """Streaming JSONL manifest writer.

    Typical usage::

        mw = ManifestWriter(
            manifest_path=Path("manifest.jsonl"),
            sha256sums_path=Path("hashes/sha256sums.txt"),
            case_id="CASE-001",
            exhibit_id="EXH-001",
        )
        mw.add_file(
            artifact_class="system_property",
            source_type="adb_shell",
            source_command_or_path="adb shell getprop",
            destination_path=Path("raw/system/getprop.txt"),
        )
    """

    def __init__(
        self,
        manifest_path: Path,
        sha256sums_path: Path,
        case_id: str,
        exhibit_id: str,
    ) -> None:
        self.manifest_path = manifest_path
        self.sha256sums_path = sha256sums_path
        self.case_id = case_id
        self.exhibit_id = exhibit_id
        # Ensure parent directories exist for both output files.
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.sha256sums_path.parent.mkdir(parents=True, exist_ok=True)
        # Clear files on start of a new acquisition run/preflight
        self.manifest_path.open("w", encoding="utf-8").close()
        self.sha256sums_path.open("w", encoding="utf-8").close()

    # ── public API ───────────────────────────────────────────────────────────

    def add_file(
        self,
        artifact_class: str,
        source_type: str,
        source_command_or_path: str,
        destination_path: Path,
        status: str = "acquired",
        reason_code: str | None = "",
        started_at: str = "",
        completed_at: str = "",
    ) -> dict:
        """Record a successfully acquired file in the manifest.

        Computes the SHA-256 digest of *destination_path* (if the file
        exists on disk), appends a record to ``manifest.jsonl``, and
        writes the hash line to ``sha256sums.txt``.

        Args:
            artifact_class:          Logical class (``"system_property"``, …).
            source_type:             How it was obtained (``"adb_shell"``, …).
            source_command_or_path:  The command or on-device path.
            destination_path:        Local path where the artefact was saved.
            status:                  Acquisition status (default ``"acquired"``).
            reason_code:             Machine-readable reason, if status ≠ acquired.
            started_at:              ISO-8601 start timestamp (auto-filled if empty).
            completed_at:            ISO-8601 end timestamp (auto-filled if empty).

        Returns:
            The manifest record dict that was written.
        """
        sha256 = ""
        size_bytes = 0
        if destination_path.exists():
            sha256 = hash_file(destination_path)
            size_bytes = destination_path.stat().st_size

        if not completed_at:
            completed_at = datetime.now(timezone.utc).isoformat()
        if not started_at:
            started_at = completed_at

        record: dict = {
            "case_id": self.case_id,
            "exhibit_id": self.exhibit_id,
            "artifact_class": artifact_class,
            "source_type": source_type,
            "source_command_or_path": source_command_or_path,
            "destination_path": str(destination_path),
            "sha256": sha256,
            "size_bytes": size_bytes,
            "started_at": started_at,
            "completed_at": completed_at,
            "status": status,
            "reason_code": reason_code or "",
            "tool_version": TOOL_VERSION,
        }

        # Append to manifest JSONL
        with open(self.manifest_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Append to sha256sums.txt (coreutils format: <hash>  <path>)
        if sha256:
            with open(self.sha256sums_path, "a", encoding="utf-8") as f:
                f.write(f"{sha256}  {destination_path}\n")

        return record

    def add_status_record(
        self,
        artifact_class: str,
        source_type: str,
        source_command_or_path: str,
        status: str,
        reason_code: str = "",
    ) -> dict:
        """Record a failed or unavailable artefact (no destination file).

        Use this when a collection step could not produce a file — for
        example because the command returned an error, or the data is not
        exposed on the device.

        Args:
            artifact_class:          Logical class of the artefact.
            source_type:             How it was attempted.
            source_command_or_path:  The command or path that was tried.
            status:                  One of the ``STATUS_*`` constants from
                                     :mod:`erakshak.config.defaults`.
            reason_code:             Machine-readable reason code.

        Returns:
            The manifest record dict that was written.
        """
        now = datetime.now(timezone.utc).isoformat()
        record: dict = {
            "case_id": self.case_id,
            "exhibit_id": self.exhibit_id,
            "artifact_class": artifact_class,
            "source_type": source_type,
            "source_command_or_path": source_command_or_path,
            "destination_path": "",
            "sha256": "",
            "size_bytes": 0,
            "started_at": now,
            "completed_at": now,
            "status": status,
            "reason_code": reason_code,
            "tool_version": TOOL_VERSION,
        }
        with open(self.manifest_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
