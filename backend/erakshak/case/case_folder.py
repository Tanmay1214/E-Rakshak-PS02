"""Case / exhibit folder structure manager.

Creates and exposes the standardised directory tree used by every
E-RAKSHAK acquisition run:

    <output_root>/<case_id>/<exhibit_id>/
        acquisition/          ← preflight report, session metadata
        raw/
            system/           ← ADB shell / dumpsys output
            media/            ← pulled media files
            collector/        ← on-device collector output
        derived/              ← post-processed / parsed artefacts
        hashes/               ← sha256sums.txt
"""

from __future__ import annotations

from pathlib import Path


class CaseFolder:
    """Manages the case/exhibit folder structure.

    Typical usage::

        cf = CaseFolder("/evidence", "CASE-001", "EXH-001")
        cf.create()
        # use cf.raw_system_dir, cf.manifest_path, etc.
    """

    def __init__(self, output_root: str, case_id: str, exhibit_id: str) -> None:
        self.output_root = Path(output_root)
        self.case_id = case_id
        self.exhibit_id = exhibit_id
        self.exhibit_path = self.output_root / case_id / exhibit_id

    # ── creation ─────────────────────────────────────────────────────────────

    def create(self) -> Path:
        """Create the full folder tree and return the exhibit root path.

        Safe to call multiple times; existing directories are left intact.
        """
        dirs = [
            self.acquisition_dir,
            self.raw_system_dir,
            self.raw_media_dir,
            self.raw_collector_dir,
            self.raw_apps_telegram_dir,
            self.derived_dir,
            self.hashes_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        return self.exhibit_path

    # ── directory properties ─────────────────────────────────────────────────

    @property
    def acquisition_dir(self) -> Path:
        """Directory for preflight report and session metadata."""
        return self.exhibit_path / "acquisition"

    @property
    def raw_system_dir(self) -> Path:
        """Directory for raw ADB shell / dumpsys output files."""
        return self.exhibit_path / "raw" / "system"

    @property
    def raw_media_dir(self) -> Path:
        """Directory for pulled media files (photos, videos, etc.)."""
        return self.exhibit_path / "raw" / "media"

    @property
    def raw_collector_dir(self) -> Path:
        """Directory for on-device collector output (calls, SMS, etc.)."""
        return self.exhibit_path / "raw" / "collector"

    @property
    def raw_apps_dir(self) -> Path:
        """Directory for raw acquired application database groups."""
        return self.exhibit_path / "raw" / "apps"

    @property
    def raw_apps_telegram_dir(self) -> Path:
        """Directory for raw acquired Telegram database groups."""
        return self.raw_apps_dir / "telegram"

    @property
    def derived_dir(self) -> Path:
        """Directory for post-processed / parsed artefacts."""
        return self.exhibit_path / "derived"

    @property
    def hashes_dir(self) -> Path:
        """Directory for hash verification files."""
        return self.exhibit_path / "hashes"

    # ── well-known file properties ───────────────────────────────────────────

    @property
    def preflight_path(self) -> Path:
        """Path to the preflight report JSON file."""
        return self.acquisition_dir / "preflight.json"

    @property
    def manifest_path(self) -> Path:
        """Path to the manifest JSONL file."""
        return self.exhibit_path / "manifest.jsonl"

    @property
    def audit_path(self) -> Path:
        """Path to the audit log JSONL file."""
        return self.exhibit_path / "audit.jsonl"

    @property
    def sha256sums_path(self) -> Path:
        """Path to the sha256sums.txt file inside hashes/."""
        return self.hashes_dir / "sha256sums.txt"
