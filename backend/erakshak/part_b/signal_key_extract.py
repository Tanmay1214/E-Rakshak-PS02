"""Root-only Signal Android SQLCipher key extraction helper."""

from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from erakshak.config.defaults import DEFAULT_ADB_TIMEOUT, LONG_ADB_TIMEOUT

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger


SIGNAL_PACKAGE = "org.thoughtcrime.securesms"
REMOTE_DEX = f"/data/data/{SIGNAL_PACKAGE}/code_cache/erakshak-signal-key-helper.dex"
REMOTE_TMP_DEX = "/data/local/tmp/erakshak-signal-key-helper.dex"

SIGNAL_KEY_HELPER_DEX_B64 = (
    "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Ew0+WgJrHQABAAAADAAAAAEAAAAAAAAAAgAAAAsAJAACAAAABQAFAAIAAAAMACQAAgAAAAwAIwACAAAADAAlAAIAAAAMABYAAQAAAAUAAAADAAAAAAATABkAAAACAAAAAAAiAAEAAAALAAAAAQAAABUAAAACAAAAIgAMAAEAAAAlAAAAAgAAAAwAAAABAAAAEQAAAAEAAAAiAAEiAAQlMDJ4AAEmAAUmYW1wOwAGJnF1b3Q7AF0vZGF0YS9kYXRhL29yZy50aG91Z2h0Y3JpbWUuc2VjdXJlc21zL3NoYXJlZF9wcmVmcy9vcmcudGhvdWdodGNyaW1lLnNlY3VyZXNtc19wcmVmZXJlbmNlcy54bWwABjxpbml0PgA+PHN0cmluZyBuYW1lPSJwcmVmX2RhdGFiYXNlX2VuY3J5cHRlZF9zZWNyZXQiPihbXjxdKyk8L3N0cmluZz4AEUFFUy9HQ00vTm9QYWRkaW5nAA9BbmRyb2lkS2V5U3RvcmUAAUkAAUwAAkxJAAJMTAADTExJAANMTEwAEUxTaWduYWxEYktleUR1bXA7ABVMYW5kcm9pZC91dGlsL0Jhc2U2NDsAGkxkYWx2aWsvYW5ub3RhdGlvbi9UaHJvd3M7ABVMamF2YS9pby9QcmludFN0cmVhbTsAGExqYXZhL2xhbmcvQ2hhclNlcXVlbmNlOwARTGphdmEvbGFuZy9DbGFzczsAIkxqYXZhL2xhbmcvQ2xhc3NOb3RGb3VuZEV4Y2VwdGlvbjsAFUxqYXZhL2xhbmcvRXhjZXB0aW9uOwAhTGphdmEvbGFuZy9JbGxlZ2FsU3RhdGVFeGNlcHRpb247ABNMamF2YS9sYW5nL0ludGVnZXI7ABJMamF2YS9sYW5nL09iamVjdDsAEkxqYXZhL2xhbmcvU3RyaW5nOwAZTGphdmEvbGFuZy9TdHJpbmdCdWlsZGVyOwASTGphdmEvbGFuZy9TeXN0ZW07ABpMamF2YS9sYW5nL3JlZmxlY3QvTWV0aG9kOwAVTGphdmEvbmlvL2ZpbGUvRmlsZXM7ABRMamF2YS9uaW8vZmlsZS9QYXRoOwAVTGphdmEvbmlvL2ZpbGUvUGF0aHM7ABNMamF2YS9zZWN1cml0eS9LZXk7AB5MamF2YS9zZWN1cml0eS9LZXlTdG9yZSRFbnRyeTsAK0xqYXZhL3NlY3VyaXR5L0tleVN0b3JlJExvYWRTdG9yZVBhcmFtZXRlcjsALExqYXZhL3NlY3VyaXR5L0tleVN0b3JlJFByb3RlY3Rpb25QYXJhbWV0ZXI7ACdMamF2YS9zZWN1cml0eS9LZXlTdG9yZSRTZWNyZXRLZXlFbnRyeTsAGExqYXZhL3NlY3VyaXR5L0tleVN0b3JlOwArTGphdmEvc2VjdXJpdHkvc3BlYy9BbGdvcml0aG1QYXJhbWV0ZXJTcGVjOwAZTGphdmEvdXRpbC9yZWdleC9NYXRjaGVyOwAZTGphdmEvdXRpbC9yZWdleC9QYXR0ZXJuOwAVTGphdmF4L2NyeXB0by9DaXBoZXI7ABhMamF2YXgvY3J5cHRvL1NlY3JldEtleTsAJExqYXZheC9jcnlwdG8vc3BlYy9HQ01QYXJhbWV0ZXJTcGVjOwAVTG9yZy9qc29uL0pTT05PYmplY3Q7AAlQUkVGX1BBVEgAFFNpZ25hbERiS2V5RHVtcC5qYXZhAAxTaWduYWxTZWNyZXQABVVURi04AAFWAAJWSQADVklMAARWSUxMAAJWTAADVkxMAAFaAAJbQgASW0xqYXZhL2xhbmcvQ2xhc3M7ABNbTGphdmEvbGFuZy9PYmplY3Q7ABNbTGphdmEvbGFuZy9TdHJpbmc7ADFhbmRyb2lkLnNlY3VyaXR5LmtleXN0b3JlLkFuZHJvaWRLZXlTdG9yZVByb3ZpZGVyADJhbmRyb2lkLnNlY3VyaXR5LmtleXN0b3JlMi5BbmRyb2lkS2V5U3RvcmVQcm92aWRlcgAGYXBwZW5kAAdjb21waWxlAARkYXRhAAZkZWNvZGUAB2RvRmluYWwABGZpbmQAB2Zvck5hbWUABmZvcm1hdAADZ2V0AAhnZXRFbnRyeQALZ2V0SW5zdGFuY2UACWdldE1ldGhvZAAMZ2V0U2VjcmV0S2V5AAlnZXRTdHJpbmcABWdyb3VwAARpbml0AAdpbnN0YWxsAAZpbnZva2UAAml2AARsb2FkAARtYWluAAdtYXRjaGVyAANvdXQAKHByZWZfZGF0YWJhc2VfZW5jcnlwdGVkX3NlY3JldCBub3QgZm91bmQAB3ByaW50bG4ADHJlYWRBbGxCeXRlcwAHcmVwbGFjZQAFdmFsdWUAB3ZhbHVlT2YAnQF+fkQ4eyJiYWNrZW5kIjoiZGV4IiwiY29tcGlsYXRpb24tbW9kZSI6ImRlYnVnIiwiaGFzLWNoZWNrc3VtcyI6ZmFsc2UsIm1pbi1hcGkiOjIzLCJzaGEtMSI6ImE3YWQxOGE3MDQ2MGI3OTlkMDQ4MmU0OTdjMTA5YTc1YmY3ZjkxZGUiLCJ2ZXJzaW9uIjoiOC4xMC45LWRldiJ9AAIDAVscARgIAQACAAAaAIGABIQKAQmcCgEXBQAAAAEAAACqDgAAAAAAAAAAAAABAAAAAAAAAAEAAADIDgAAEQAAAAAAAAABAAAAAAAAAAEAAABeAAAAcAAAAAIAAAAmAAAA6AEAAAMAAAAdAAAAgAIAAAQAAAACAAAA3AMAAAUAAAAfAAAA7AMAAAYAAAABAAAA5AQAAAEgAAACAAAABAUAAAMgAAACAAAA5AYAAAEQAAASAAAAEAcAAAIgAABeAAAAogcAAAQgAAABAAAAqg4AAAAgAAABAAAAsg4AAAUgAAABAAAAwg4AAAMQAAABAAAAyA4AAAYgAAABAAAA0A4AAAAQAAABAAAA6A4AAA=="
)


def extract_signal_db_key(adb: "ADBClient", audit: "AuditLogger", package: str = SIGNAL_PACKAGE) -> tuple[str | None, str]:
    """Return the Signal SQLCipher key from a rooted device without saving it."""
    if package != SIGNAL_PACKAGE:
        return None, f"Auto key extraction currently supports only {SIGNAL_PACKAGE}."

    uid = _get_package_uid(adb, package)
    if not uid:
        return None, f"Could not determine app uid for {package}."
    su_user = _uid_to_android_user(uid)

    with tempfile.TemporaryDirectory() as temp_dir:
        local_dex = Path(temp_dir) / "erakshak-signal-key-helper.dex"
        local_dex.write_bytes(base64.b64decode(SIGNAL_KEY_HELPER_DEX_B64))
        push = adb.run(["push", str(local_dex), REMOTE_TMP_DEX], timeout=DEFAULT_ADB_TIMEOUT, audit_action="signal_key_helper_push")
        if not push.ok:
            return None, _short_error("Failed to push Signal key helper", push.stderr)

    setup_commands = [
        ["su", "0", "mkdir", "-p", f"/data/data/{package}/code_cache"],
        ["su", "0", "cp", REMOTE_TMP_DEX, REMOTE_DEX],
        ["su", "0", "chown", f"{su_user}:{su_user}", REMOTE_DEX],
        ["su", "0", "chmod", "400", REMOTE_DEX],
    ]
    for command in setup_commands:
        result = adb.shell(command, timeout=DEFAULT_ADB_TIMEOUT, audit_action="signal_key_helper_setup")
        if not result.ok:
            return None, _short_error("Failed to stage Signal key helper", result.stderr or result.stdout)

    run = adb.shell(
        ["su", su_user, "env", f"CLASSPATH={REMOTE_DEX}", "app_process", "/system/bin", "SignalDbKeyDump"],
        timeout=LONG_ADB_TIMEOUT,
        audit_action="signal_key_extract",
    )
    adb.shell(["su", "0", "rm", "-f", REMOTE_TMP_DEX, REMOTE_DEX], timeout=DEFAULT_ADB_TIMEOUT, audit_action="signal_key_helper_cleanup")

    if not run.ok:
        audit.log(
            action="signal_key_extract_failed",
            command_category="adb_command",
            command_redacted="adb shell su <signal_uid> app_process SignalDbKeyDump",
            result="failed",
            return_code=run.return_code,
            duration_ms=run.duration_ms,
            error=(run.stderr or run.stdout).strip()[:500],
        )
        return None, _short_error("Signal key extraction failed", run.stderr or run.stdout)

    match = re.search(r"\b[0-9a-fA-F]{64}\b", run.stdout)
    if not match:
        return None, "Signal key helper did not return a 64-character hex key."

    audit.log(action="signal_key_extract", command_category="adb_command", command_redacted="app_process SignalDbKeyDump", result="success")
    return match.group(0).lower(), ""


def _get_package_uid(adb: "ADBClient", package: str) -> str | None:
    result = adb.shell(["dumpsys", "package", package], timeout=DEFAULT_ADB_TIMEOUT, audit_action="signal_package_uid")
    if result.ok:
        for pattern in (r"\buserId=(\d+)\b", r"\buid=(\d+)\b"):
            match = re.search(pattern, result.stdout)
            if match:
                return match.group(1)
    result = adb.shell(["su", "0", "stat", "-c", "%u", f"/data/data/{package}"], timeout=DEFAULT_ADB_TIMEOUT, audit_action="signal_package_uid_stat")
    if result.ok and result.stdout.strip().isdigit():
        return result.stdout.strip()
    return None


def _uid_to_android_user(uid: str) -> str:
    app_id = int(uid)
    if app_id >= 10000:
        return f"u0_a{app_id - 10000}"
    return uid


def _short_error(prefix: str, detail: str) -> str:
    detail = detail.strip()[:500]
    return f"{prefix}: {detail}" if detail else prefix
