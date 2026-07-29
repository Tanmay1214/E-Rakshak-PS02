from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any

from erakshak.case.hashing import verify_sha256sums

logger = logging.getLogger(__name__)

def verify_case_hashes(exhibit_root: Path) -> Dict[str, Any]:
    hashes_file = exhibit_root / "hashes" / "sha256sums.txt"
    if not hashes_file.exists():
        logger.warning(f"Hash file missing at {hashes_file}")
        return {"total": 0, "verified": 0, "missing": 0, "mismatched": 0, "details": []}
    
    return verify_sha256sums(hashes_file)
