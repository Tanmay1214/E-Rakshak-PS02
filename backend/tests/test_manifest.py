"""Tests for erakshak.case.manifest — ManifestWriter."""
from __future__ import annotations

import json
import pytest
from pathlib import Path


def test_manifest_add_file(tmp_path: Path) -> None:
    """Test adding a real file to the manifest."""
    from erakshak.case.manifest import ManifestWriter

    manifest_path = tmp_path / "manifest.jsonl"
    sha256sums_path = tmp_path / "sha256sums.txt"
    m = ManifestWriter(manifest_path, sha256sums_path, "CASE001", "EX001")

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    record = m.add_file("test_artifact", "test_source", "test_command", test_file)

    assert record["case_id"] == "CASE001"
    assert record["exhibit_id"] == "EX001"
    assert record["sha256"] != ""
    assert record["size_bytes"] > 0
    assert record["status"] == "acquired"

    # Verify JSONL was written
    lines = manifest_path.read_text().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["artifact_class"] == "test_artifact"

    # Verify sha256sums.txt was written
    sums_content = sha256sums_path.read_text()
    assert record["sha256"] in sums_content


def test_manifest_add_status_record(tmp_path: Path) -> None:
    """Test adding a status-only record (no file)."""
    from erakshak.case.manifest import ManifestWriter

    manifest_path = tmp_path / "manifest.jsonl"
    sha256sums_path = tmp_path / "sha256sums.txt"
    m = ManifestWriter(manifest_path, sha256sums_path, "CASE001", "EX001")

    record = m.add_status_record(
        "failed_artifact", "adb_command", "dumpsys wifi", "failed", "timed_out"
    )

    assert record["status"] == "failed"
    assert record["reason_code"] == "timed_out"
    assert record["sha256"] == ""
    assert record["destination_path"] == ""
