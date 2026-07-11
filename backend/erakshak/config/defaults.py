"""Default configuration constants for E-RAKSHAK.

All timeouts are in seconds. All size limits are in bytes.
Status constants describe the outcome of individual collection steps.
"""

from __future__ import annotations

# ── Tool identity ────────────────────────────────────────────────────────────
TOOL_VERSION: str = "0.1.0"
TOOL_NAME: str = "E-RAKSHAK"

# ── Hashing ──────────────────────────────────────────────────────────────────
HASH_ALGORITHM: str = "sha256"

# ── ADB timeouts (seconds) ──────────────────────────────────────────────────
DEFAULT_ADB_TIMEOUT: int = 30
LONG_ADB_TIMEOUT: int = 120
DUMPSYS_TIMEOUT: int = 60
LOGCAT_TIMEOUT: int = 60
MEDIA_PULL_TIMEOUT: int = 300

# ── Media collection defaults ────────────────────────────────────────────────
DEFAULT_MEDIA_DAYS: int = 7
DEFAULT_MEDIA_MAX_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB

MEDIA_TARGET_FOLDERS: list[str] = [
    "/sdcard/DCIM",
    "/sdcard/Pictures",
    "/sdcard/Movies",
    "/sdcard/Download",
    "/sdcard/WhatsApp/Media",
    "/sdcard/Android/media",
]

# ── Collector expected output files ──────────────────────────────────────────
COLLECTOR_EXPECTED_FILES: list[str] = [
    "calls.jsonl",
    "sms.jsonl",
    "mms.jsonl",
    "media_index.jsonl",
]

# ── Collection status constants ──────────────────────────────────────────────
STATUS_ACQUIRED: str = "acquired"
STATUS_PARTIAL: str = "partial"
STATUS_FAILED: str = "failed"
STATUS_UNAVAILABLE: str = "unavailable"
STATUS_NOT_ACCESSIBLE: str = "not_accessible"
STATUS_COMMAND_UNAVAILABLE: str = "command_unavailable"
STATUS_PERMISSION_DENIED: str = "permission_denied"
STATUS_UNSUPPORTED: str = "unsupported"
STATUS_NOT_EXPOSED: str = "not_exposed"
