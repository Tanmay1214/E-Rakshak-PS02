"""Streaming JSONL audit logger for E-RAKSHAK.

Records every forensic action (ADB commands, file pulls, parsing steps,
errors) to an append-only ``audit.jsonl`` file.  Each line is a
self-contained JSON object so the log can be consumed incrementally and
is resilient against incomplete writes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLogger:
    """Streaming JSONL audit logger.

    Every significant action — successful or failed — is recorded with a
    UTC timestamp, the originating case/exhibit identifiers, and relevant
    metadata.  The file is opened in *append* mode for each write so the
    logger never truncates previous records.

    Typical usage::

        audit = AuditLogger(Path("audit.jsonl"), "CASE-001", "EXH-001")
        audit.log("preflight_start", command_category="lifecycle")
        audit.log("adb_shell", command_category="adb_command",
                  command_redacted="adb shell getprop ro.build.fingerprint",
                  result="acquired", return_code=0, duration_ms=42.3)
    """

    def __init__(self, audit_path: Path, case_id: str, exhibit_id: str) -> None:
        self.audit_path = audit_path
        self.case_id = case_id
        self.exhibit_id = exhibit_id
        # Ensure the parent directory exists so the first write won't fail.
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    # ── core logging ─────────────────────────────────────────────────────────

    def log(
        self,
        action: str,
        command_category: str = "",
        command_redacted: str = "",
        result: str = "",
        return_code: int | None = None,
        duration_ms: float | None = None,
        output_path: str = "",
        warning: str = "",
        error: str = "",
    ) -> None:
        """Append one audit record to the JSONL file.

        Args:
            action:            Human-readable action name (e.g. ``"adb_shell"``).
            command_category:  Broad category (``"adb_command"``, ``"file_pull"``, …).
            command_redacted:  Sanitised command string (no passwords/tokens).
            result:            Outcome descriptor (``"acquired"``, ``"failed"``, …).
            return_code:       Process return code, if applicable.
            duration_ms:       Wall-clock duration of the action in milliseconds.
            output_path:       Path to the artefact file created, if any.
            warning:           Warning message, if any.
            error:             Error message, if any.
        """
        record: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_id": self.case_id,
            "exhibit_id": self.exhibit_id,
            "action": action,
            "command_category": command_category,
            "command_redacted": command_redacted,
            "result": result,
            "return_code": return_code,
            "duration_ms": duration_ms,
            "output_path": output_path,
            "warning": warning,
            "error": error,
        }
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── convenience: log from an ADBResult ───────────────────────────────────

    def log_adb_result(
        self,
        adb_result: object,
        action: str,
        command_category: str = "adb_command",
        output_path: str = "",
    ) -> None:
        """Log an action using fields pulled from an ``ADBResult`` object.

        ``adb_result`` is expected to expose:

        - ``command`` (*list[str]*) – the raw command tokens.
        - ``return_code`` (*int*) – process exit code.
        - ``duration_ms`` (*float*) – wall-clock duration in ms.
        - ``success`` (*bool*) – whether the command succeeded.
        - ``stderr`` (*str*) – standard-error output (used for warnings/errors).

        Any missing attribute is silently replaced with a safe default so
        the logger never raises on an unexpected object shape.

        Args:
            adb_result:       The result object to extract data from.
            action:           Human-readable action name.
            command_category: Category string (default ``"adb_command"``).
            output_path:      Destination file path, if any.
        """
        # Safely extract attributes with fallbacks
        command_parts: list[str] = getattr(adb_result, "command", [])
        command_redacted = " ".join(str(p) for p in command_parts)
        return_code: int | None = getattr(adb_result, "return_code", None)
        duration_ms: float | None = getattr(adb_result, "duration_ms", None)
        success: bool = getattr(adb_result, "ok", False)
        stderr: str = getattr(adb_result, "stderr", "")

        result_str = "acquired" if success else "failed"
        warning = ""
        error = ""

        if not success and stderr:
            error = stderr.strip()[:500]  # cap to 500 chars
        elif success and stderr:
            warning = stderr.strip()[:500]

        self.log(
            action=action,
            command_category=command_category,
            command_redacted=command_redacted,
            result=result_str,
            return_code=return_code,
            duration_ms=duration_ms,
            output_path=output_path,
            warning=warning,
            error=error,
        )
