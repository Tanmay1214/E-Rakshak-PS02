"""Tests for browser evidence acquisition module in E-RAKSHAK."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from erakshak.acquisition.browser_evidence import acquire_browser_evidence
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger


def test_non_root_browser_detection(tmp_path: Path) -> None:
    # Set up temp folders
    case_folder = CaseFolder(tmp_path, "CASE001", "EXHIBIT001")
    case_folder.create()

    # Manifest and Audit log files
    manifest_path = case_folder.exhibit_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = case_folder.exhibit_path / "hashes" / "sha256sums.txt"
    audit_path = case_folder.exhibit_path / "acquisition" / "audit.jsonl"
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = ManifestWriter(manifest_path, sha256sums_path, "CASE001", "EXHIBIT001")
    audit = AuditLogger(audit_path, "CASE001", "EXHIBIT001")

    # Mock ADB client returning list of packages including Chrome
    mock_adb = MagicMock()
    mock_adb.serial = "emulator-5554"
    mock_adb.shell.return_value = MagicMock(
        ok=True,
        stdout="package:com.android.chrome\npackage:com.brave.browser\n",
        stderr=""
    )

    summary = acquire_browser_evidence(
        adb=mock_adb,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit,
        mode="non-root",
        case_id="CASE001",
        exhibit_id="EXHIBIT001"
    )

    # Check installed browsers were detected
    assert "com.android.chrome" in summary["installed_browsers"]
    assert "com.brave.browser" in summary["installed_browsers"]
    # Check parsed browsers is empty (non-root cannot access history database)
    assert summary["parsed_browsers"] == []
    assert "com.android.chrome" in summary["not_accessible"]
    assert summary["mode"] == "non-root"

    # Verify that the output files exist
    assert (case_folder.derived_dir / "browser_history.jsonl").is_file()
    assert (case_folder.derived_dir / "browser_searches.jsonl").is_file()
    assert (case_folder.derived_dir / "browser_downloads.jsonl").is_file()
    assert (case_folder.derived_dir / "browser_summary.json").is_file()

    # Verify summary contents
    with open(case_folder.derived_dir / "browser_summary.json", "r", encoding="utf-8") as fh:
        data = json.load(fh)
        assert data["mode"] == "non-root"
        assert len(data["installed_browsers"]) == 2
        assert "Chrome history not accessible in non-root mode due to Android app sandboxing." in data["warnings"]
