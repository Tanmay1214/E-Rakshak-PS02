"""ADB client wrapper for E-RAKSHAK.

Provides a forensically-safe, audit-logged interface to the Android Debug
Bridge.  Every command is run as a subprocess with capture, timing and
optional audit logging.  No shell=True is ever used.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from erakshak.config.defaults import DEFAULT_ADB_TIMEOUT, MEDIA_PULL_TIMEOUT


# ── Audit logger protocol ───────────────────────────────────────────────────

@runtime_checkable
class AuditLogger(Protocol):
    """Protocol that any audit-logger implementation must satisfy."""

    def log(self, record: dict[str, Any]) -> None:
        """Persist a single audit record."""
        ...


# ── ADB result dataclass ────────────────────────────────────────────────────

@dataclass
class ADBResult:
    """Immutable result of a single ADB command execution."""

    command: list[str]
    stdout: str
    stderr: str
    return_code: int
    started_at: str          # ISO-8601 UTC
    completed_at: str        # ISO-8601 UTC
    duration_ms: float
    timed_out: bool = False

    # ── helpers ──────────────────────────────────────────────────────────
    @property
    def ok(self) -> bool:
        """True when the command exited 0 and did not time out."""
        return self.return_code == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        """Serialise the result to a plain dict (for JSON logging)."""
        return {
            "command": self.command,
            "stdout_len": len(self.stdout),
            "stderr_len": len(self.stderr),
            "return_code": self.return_code,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
        }


# ── Commands that must NOT carry a device serial ────────────────────────────

_GLOBAL_COMMANDS: frozenset[str] = frozenset({
    "version",
    "devices",
    "start-server",
    "kill-server",
    "help",
})


def _is_global_command(args: list[str]) -> bool:
    """Return True if *args* represents a command that must not include -s."""
    if not args:
        return False
    # First positional argument (ignoring flags) determines the command.
    return args[0] in _GLOBAL_COMMANDS


# ── ADB client ──────────────────────────────────────────────────────────────

class ADBClient:
    """Thin, forensically-safe wrapper around the ``adb`` binary.

    Parameters
    ----------
    serial:
        Device serial number.  Pass ``"auto"`` to auto-detect when exactly
        one device is connected.
    audit_logger:
        Any object satisfying the :class:`AuditLogger` protocol.  May be
        ``None`` to skip audit logging.
    adb_path:
        Path (or bare name) of the ``adb`` executable.  Defaults to
        ``"adb"`` which relies on ``PATH``.
    """

    def __init__(
        self,
        serial: str = "auto",
        audit_logger: AuditLogger | None = None,
        adb_path: str = "adb",
    ) -> None:
        self.adb_path: str = adb_path
        self.audit_logger: AuditLogger | None = audit_logger

        if serial == "auto":
            self.serial: str = self.resolve_serial()
        else:
            self.serial = serial

    # ── serial resolution ────────────────────────────────────────────────

    def resolve_serial(self) -> str:
        """Detect the single connected device and return its serial.

        Raises
        ------
        RuntimeError
            If zero or more than one device is attached.
        FileNotFoundError
            If the ``adb`` binary cannot be found.
        """
        result = self.get_devices()

        if result.timed_out:
            raise RuntimeError("Timed out while listing ADB devices.")

        if result.return_code != 0:
            raise RuntimeError(
                f"'adb devices -l' failed (rc={result.return_code}): "
                f"{result.stderr.strip()}"
            )

        # Parse output – skip the header line.
        devices: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])

        if len(devices) == 0:
            raise RuntimeError(
                "No ADB devices found. "
                "Connect a device and ensure USB debugging is enabled."
            )
        if len(devices) > 1:
            raise RuntimeError(
                f"Multiple ADB devices found ({', '.join(devices)}). "
                "Specify the target serial explicitly with --serial."
            )

        return devices[0]

    # ── core execution ───────────────────────────────────────────────────

    def run(
        self,
        args: list[str],
        timeout: int = DEFAULT_ADB_TIMEOUT,
        audit_action: str = "",
    ) -> ADBResult:
        """Execute an ADB command and return an :class:`ADBResult`.

        Parameters
        ----------
        args:
            Arguments after ``adb``, e.g. ``["shell", "getprop"]``.
        timeout:
            Maximum wall-clock seconds before the process is killed.
        audit_action:
            Human-readable label recorded in the audit log.

        Returns
        -------
        ADBResult
            Always returns (never raises for expected failures).
        """
        # Build the full command list.
        cmd: list[str] = [self.adb_path]
        if not _is_global_command(args):
            cmd.extend(["-s", self.serial])
        cmd.extend(args)

        started_at = datetime.now(timezone.utc)
        started_iso = started_at.isoformat()

        timed_out = False
        stdout = ""
        stderr = ""
        return_code = -1

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            return_code = proc.returncode

        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
            return_code = -1

        except FileNotFoundError:
            stderr = (
                f"ADB binary not found at '{self.adb_path}'. "
                "Ensure ADB is installed and on the system PATH."
            )
            return_code = -127

        completed_at = datetime.now(timezone.utc)
        completed_iso = completed_at.isoformat()
        duration_ms = (completed_at - started_at).total_seconds() * 1000.0

        result = ADBResult(
            command=cmd,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            started_at=started_iso,
            completed_at=completed_iso,
            duration_ms=round(duration_ms, 2),
            timed_out=timed_out,
        )

        # Audit logging
        if self.audit_logger is not None:
            audit_record: dict[str, Any] = {
                "action": audit_action or " ".join(args[:3]),
                "command": cmd,
                "return_code": return_code,
                "timed_out": timed_out,
                "started_at": started_iso,
                "completed_at": completed_iso,
                "duration_ms": result.duration_ms,
                "stdout_bytes": len(stdout),
                "stderr_bytes": len(stderr),
            }
            self.audit_logger.log(audit_record)

        return result

    # ── convenience wrappers ─────────────────────────────────────────────

    def shell(
        self,
        shell_cmd: list[str],
        timeout: int = DEFAULT_ADB_TIMEOUT,
        audit_action: str = "",
    ) -> ADBResult:
        """Run a command inside the device's shell.

        Equivalent to ``adb -s <serial> shell <shell_cmd ...>``.
        """
        return self.run(
            ["shell"] + shell_cmd,
            timeout=timeout,
            audit_action=audit_action,
        )

    def pull(
        self,
        remote_path: str,
        local_path: str,
        timeout: int = MEDIA_PULL_TIMEOUT,
        audit_action: str = "",
    ) -> ADBResult:
        """Pull a file from the device to the local filesystem.

        Equivalent to ``adb -s <serial> pull <remote> <local>``.
        """
        return self.run(
            ["pull", remote_path, str(local_path)],
            timeout=timeout,
            audit_action=audit_action or f"pull {remote_path}",
        )

    def get_adb_version(self) -> ADBResult:
        """Return the ADB client version string (global command, no serial)."""
        return self.run(["version"], audit_action="adb_version")

    def get_devices(self) -> ADBResult:
        """List connected devices with details (global command, no serial)."""
        return self.run(["devices", "-l"], audit_action="list_devices")
