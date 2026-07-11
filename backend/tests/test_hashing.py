"""Tests for erakshak.case.hashing — SHA-256 hashing and verification."""
from __future__ import annotations

import pytest
from pathlib import Path


def test_hash_file_known_value(tmp_path: Path) -> None:
    """Test SHA-256 of known content ``hello\\n``."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello\n")
    from erakshak.case.hashing import hash_file
    result = hash_file(f)
    assert result == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"


def test_hash_bytes() -> None:
    """Test in-memory SHA-256 of known bytes."""
    from erakshak.case.hashing import hash_bytes
    result = hash_bytes(b"hello\n")
    assert result == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"


def test_verify_sha256sums_all_match(tmp_path: Path) -> None:
    """Write files, create sha256sums.txt, verify all match."""
    from erakshak.case.hashing import hash_file, verify_sha256sums

    # Create test files
    f1 = tmp_path / "a.txt"
    f1.write_text("alpha")
    f2 = tmp_path / "b.txt"
    f2.write_text("beta")

    # Create sha256sums.txt
    sums = tmp_path / "sha256sums.txt"
    with open(sums, "w") as sf:
        sf.write(f"{hash_file(f1)}  {f1}\n")
        sf.write(f"{hash_file(f2)}  {f2}\n")

    result = verify_sha256sums(sums)
    assert result["total"] == 2
    assert result["verified"] == 2
    assert result["missing"] == 0
    assert result["mismatched"] == 0


def test_verify_sha256sums_mismatch(tmp_path: Path) -> None:
    """Modify a file after hashing, verify mismatch is detected."""
    from erakshak.case.hashing import hash_file, verify_sha256sums

    f1 = tmp_path / "a.txt"
    f1.write_text("alpha")

    sums = tmp_path / "sha256sums.txt"
    with open(sums, "w") as sf:
        sf.write(f"{hash_file(f1)}  {f1}\n")

    # Modify the file *after* its hash was recorded
    f1.write_text("modified!")

    result = verify_sha256sums(sums)
    assert result["mismatched"] == 1


def test_verify_sha256sums_missing(tmp_path: Path) -> None:
    """Reference a file that doesn't exist, verify missing is detected."""
    from erakshak.case.hashing import verify_sha256sums

    sums = tmp_path / "sha256sums.txt"
    with open(sums, "w") as sf:
        sf.write(f"deadbeef  {tmp_path / 'nonexistent.txt'}\n")

    result = verify_sha256sums(sums)
    assert result["missing"] == 1
