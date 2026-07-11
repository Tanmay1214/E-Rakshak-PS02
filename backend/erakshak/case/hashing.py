"""Hashing utilities for forensic integrity verification.

Provides functions to compute file and byte hashes, and to verify
sha256sums.txt files against their referenced artifacts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_file(filepath: Path, algorithm: str = "sha256",
              chunk_size: int = 8192) -> str:
    """Compute the cryptographic hash of a file on disk.

    Reads the file in chunks to handle large files without
    excessive memory consumption.

    Args:
        filepath:   Path to the file to hash.
        algorithm:  Hash algorithm name accepted by :func:`hashlib.new`.
        chunk_size: Bytes to read per iteration.

    Returns:
        Lowercase hex-digest string.

    Raises:
        FileNotFoundError: If *filepath* does not exist.
        ValueError:        If *algorithm* is not supported by hashlib.
    """
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Compute the cryptographic hash of an in-memory bytes object.

    Args:
        data:      The raw bytes to hash.
        algorithm: Hash algorithm name accepted by :func:`hashlib.new`.

    Returns:
        Lowercase hex-digest string.
    """
    return hashlib.new(algorithm, data).hexdigest()


def verify_sha256sums(sha256sums_path: Path) -> dict:
    """Read a ``sha256sums.txt`` file, recompute hashes, and compare.

    The file is expected to follow the coreutils format::

        <hex-hash>  <file-path>

    (two spaces separating hash from path).

    Args:
        sha256sums_path: Path to the sha256sums.txt file.

    Returns:
        A dict with keys:

        - **total** (*int*) – number of entries processed.
        - **verified** (*int*) – entries whose hash matched.
        - **missing** (*int*) – entries whose file was not found on disk.
        - **mismatched** (*int*) – entries whose recomputed hash differs.
        - **details** (*list[dict]*) – per-entry records with keys
          ``path``, ``expected``, ``actual``, and ``status``.
    """
    results: dict = {
        "total": 0,
        "verified": 0,
        "missing": 0,
        "mismatched": 0,
        "details": [],
    }

    if not sha256sums_path.exists():
        return results

    with open(sha256sums_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Format: <hash>  <path>  (two-space separator)
            parts = line.split("  ", 1)
            if len(parts) != 2:
                continue

            expected_hash, file_path_str = parts
            file_path = Path(file_path_str)
            results["total"] += 1

            detail: dict = {
                "path": file_path_str,
                "expected": expected_hash,
                "actual": "",
                "status": "",
            }

            if not file_path.exists():
                detail["status"] = "missing"
                results["missing"] += 1
            else:
                actual_hash = hash_file(file_path)
                detail["actual"] = actual_hash
                if actual_hash == expected_hash:
                    detail["status"] = "verified"
                    results["verified"] += 1
                else:
                    detail["status"] = "mismatched"
                    results["mismatched"] += 1

            results["details"].append(detail)

    return results
