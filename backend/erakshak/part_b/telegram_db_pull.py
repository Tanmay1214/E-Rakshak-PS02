"""Telegram SQLite database acquisition engine — Phase B.2.2.

Pulls the primary ``cache4.db`` database (and its WAL/SHM/journal sidecars)
from every installed Telegram variant's private data directory, and
inventories world-readable shared media roots accessible without root.

Design constraints
------------------
- **Read-only on device**: no shell writes, no ``adb push``, no privilege
  escalation.  All state changes happen only on the local (examiner) machine.
- **Honest about partial success**: an artifact is never recorded as
  ``acquired`` unless the local file was actually written and hashed.
- **Volatile detection**: when the remote file size reported by ``ls -la``
  does not match the local file size after pull, the artifact is marked
  volatile and a warning is recorded in the manifest and audit log.
- **Sidecar optional**: missing WAL/SHM/journal files are skipped silently;
  only the absence of a *required* primary DB is treated as significant.
- **Partial cleanup**: if a pull leaves the local file absent, the empty/
  partial path is removed and the artifact is never reported as acquired.

Usage::

    from erakshak.adb.client import ADBClient
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter
    from erakshak.case.audit import AuditLogger
    from erakshak.part_b.telegram_db_pull import acquire_telegram_databases

    result = acquire_telegram_databases(adb, case_folder, manifest, audit)
    print(result["status"], result["packages_found"])
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from erakshak.adb.parsers import parse_ls_output
from erakshak.case.hashing import hash_file
from erakshak.config.defaults import (
    DEFAULT_ADB_TIMEOUT,
    LONG_ADB_TIMEOUT,
    MEDIA_PULL_TIMEOUT,
    STATUS_ACQUIRED,
    STATUS_FAILED,
    STATUS_NOT_ACCESSIBLE,
    STATUS_PARTIAL,
)
from erakshak.part_b.telegram_paths import (
    SQLITE_SIDECAR_EXTENSIONS,
    TELEGRAM_PROFILES,
    TelegramDbGroup,
    TelegramProfile,
)

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


# ── Remote path probe result ─────────────────────────────────────────────────

@dataclass(frozen=True)
class RemoteProbeResult:
    """Typed result from probing a single remote path via ``ls -la``.

    Attributes
    ----------
    state:
        One of: ``"accessible"``, ``"inaccessible"``, ``"not_present"``,
        ``"probe_failed"``.
    remote_size:
        File size in bytes as reported by ``ls -la``, or ``None`` when the
        size could not be determined (directory, permission denied, failure).
    stderr:
        Raw stderr from the probe command, truncated to 500 chars.
    """

    state: str            # accessible | inaccessible | not_present | probe_failed
    remote_size: int | None = None
    stderr: str = ""


# ── Private helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_remote_path(adb: "ADBClient", remote_path: str) -> RemoteProbeResult:
    """Probe *remote_path* via ``adb shell ls -la`` and classify the result.

    Returns a :class:`RemoteProbeResult` with one of four states:

    - ``"accessible"``   — file exists and ls returned readable output.
    - ``"inaccessible"`` — path exists but permission was denied.
    - ``"not_present"``  — path does not exist on the device.
    - ``"probe_failed"`` — ADB timed out, binary missing, or unknown error.

    Notes: ADB ``shell ls`` exits 0 even for some error conditions on older
    Android versions; stderr content is therefore the primary signal.
    """
    result = adb.shell(
        ["ls", "-la", remote_path],
        timeout=DEFAULT_ADB_TIMEOUT,
        audit_action=f"probe_{Path(remote_path).name}",
    )

    stderr_lower = result.stderr.lower()
    stdout_lower = result.stdout.lower()

    # ── timeout / binary not found ─────────────────────────────────────────
    if result.timed_out or result.return_code == -127:
        return RemoteProbeResult(state="probe_failed", stderr=result.stderr[:500])

    # ── permission denied ──────────────────────────────────────────────────
    if "permission denied" in stderr_lower or "permission denied" in stdout_lower:
        return RemoteProbeResult(state="inaccessible", stderr=result.stderr[:500])

    # ── path not found ─────────────────────────────────────────────────────
    if (
        "no such file or directory" in stderr_lower
        or "no such file or directory" in stdout_lower
        or ("not found" in stderr_lower and result.return_code != 0)
    ):
        return RemoteProbeResult(state="not_present", stderr=result.stderr[:500])

    # ── non-zero exit with no parseable stdout ─────────────────────────────
    if result.return_code != 0 and not result.stdout.strip():
        return RemoteProbeResult(state="probe_failed", stderr=result.stderr[:500])

    # ── parse ls output to extract file size ───────────────────────────────
    # Provide a directory hint so parse_ls_output can construct the full
    # path even when the output lacks a directory header (single-file ls).
    parent_dir = str(Path(remote_path).parent)
    entries = parse_ls_output(result.stdout, current_dir_hint=parent_dir)

    remote_size: int | None = None
    for entry in entries:
        if entry.get("type") == "file":
            remote_size = entry.get("size")
            break

    return RemoteProbeResult(
        state="accessible",
        remote_size=remote_size,
        stderr=result.stderr[:500],
    )


def _is_package_installed(adb: "ADBClient", package: str) -> bool:
    """Return True if *package* is present in ``pm list packages -e``.

    Uses the enabled-packages filter for speed.  Returns False on any ADB
    error to avoid false positives.
    """
    result = adb.shell(
        ["pm", "list", "packages", "-e", package],
        timeout=DEFAULT_ADB_TIMEOUT,
        audit_action=f"pm_check_{package}",
    )
    if not result.ok:
        return False
    target = f"package:{package}"
    for line in result.stdout.splitlines():
        if line.strip() == target:
            return True
    return False


def _pull_and_record(
    adb: "ADBClient",
    remote_path: str,
    local_path: Path,
    expected_size: int | None,
    manifest: "ManifestWriter",
    audit: "AuditLogger",
    artifact_class: str,
    started_at: str,
    *,
    optional: bool = False,
) -> dict:
    """Pull *remote_path* to *local_path*, hash it, and record in manifest.

    An artifact is recorded as *acquired* only when the local file exists
    after the pull and has been successfully hashed.  On failure a status
    record is written — never a false-positive acquired entry.

    Returns
    -------
    dict
        Keys: ``status``, ``sha256``, ``local_size``, ``remote_size``,
        ``volatile``, ``warning``, ``error``.
    """
    pull_result = adb.pull(
        remote_path,
        str(local_path),
        timeout=MEDIA_PULL_TIMEOUT,
        audit_action=f"pull_{Path(remote_path).name}",
    )
    completed_at = _now_iso()

    # ── pull failed or file missing after pull ─────────────────────────────
    if not pull_result.ok or not local_path.exists():
        if local_path.exists():
            try:
                local_path.unlink()
            except OSError:
                pass
        err_msg = (
            pull_result.stderr.strip()[:500]
            or "pull returned non-zero exit code"
        )
        manifest.add_status_record(
            artifact_class=artifact_class,
            source_type="adb_pull",
            source_command_or_path=remote_path,
            status=STATUS_FAILED,
            reason_code="pull_failed",
        )
        audit.log(
            action="telegram_db_pull_failed",
            command_category="file_pull",
            command_redacted=f"adb pull {remote_path}",
            result="failed",
            return_code=pull_result.return_code,
            duration_ms=pull_result.duration_ms,
            output_path=str(local_path),
            error=err_msg,
        )
        return {
            "status": "failed",
            "sha256": "",
            "local_size": None,
            "remote_size": expected_size,
            "volatile": False,
            "warning": "",
            "error": err_msg,
        }

    # ── pull succeeded — hash and check for size mismatch ──────────────────
    local_size = local_path.stat().st_size
    sha256 = hash_file(local_path)

    volatile = expected_size is not None and local_size != expected_size
    warning_msg = ""
    manifest_status: str
    reason_code = ""

    if volatile:
        warning_msg = (
            f"Volatile acquisition: remote size was {expected_size} bytes "
            f"before pull but local file is {local_size} bytes. "
            "The database may have been written to during acquisition."
        )
        manifest_status = STATUS_PARTIAL
        reason_code = "size_mismatch_volatile"
    else:
        manifest_status = STATUS_ACQUIRED

    manifest.add_file(
        artifact_class=artifact_class,
        source_type="adb_pull",
        source_command_or_path=remote_path,
        destination_path=local_path,
        status=manifest_status,
        reason_code=reason_code,
        started_at=started_at,
        completed_at=completed_at,
    )
    audit.log(
        action="telegram_db_pulled",
        command_category="file_pull",
        command_redacted=f"adb pull {remote_path}",
        result=manifest_status,
        return_code=pull_result.return_code,
        duration_ms=pull_result.duration_ms,
        output_path=str(local_path),
        warning=warning_msg,
    )

    return {
        "status": "volatile" if volatile else STATUS_ACQUIRED,
        "sha256": sha256,
        "local_size": local_size,
        "remote_size": expected_size,
        "volatile": volatile,
        "warning": warning_msg,
        "error": "",
    }


def _acquire_db_group(
    adb: "ADBClient",
    profile: TelegramProfile,
    db_group: TelegramDbGroup,
    dest_dir: Path,
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Pull one DB group (primary DB + sidecars) for *profile*.

    Returns
    -------
    dict
        Keys: ``remote_path``, ``db_status``, ``sha256``, ``volatile``,
        ``sidecars``, ``warnings``, ``errors``.
    """
    remote_path = f"{profile.private_data_root}/{db_group.relative_path}"
    artifact_class = (
        f"telegram_db_{profile.package}_{Path(db_group.relative_path).stem}"
    )
    started_at = _now_iso()

    summary: dict = {
        "remote_path": remote_path,
        "db_status": "failed",
        "sha256": "",
        "volatile": False,
        "sidecars": [],
        "warnings": [],
        "errors": [],
    }

    # ── probe the primary DB ────────────────────────────────────────────────
    probe = _probe_remote_path(adb, remote_path)

    if probe.state == "not_present":
        if db_group.required:
            manifest.add_status_record(
                artifact_class=artifact_class,
                source_type="adb_shell",
                source_command_or_path=remote_path,
                status=STATUS_NOT_ACCESSIBLE,
                reason_code="not_present",
            )
        summary["db_status"] = "not_present"
        return summary

    if probe.state == "inaccessible":
        manifest.add_status_record(
            artifact_class=artifact_class,
            source_type="adb_shell",
            source_command_or_path=remote_path,
            status=STATUS_NOT_ACCESSIBLE,
            reason_code="permission_denied",
        )
        audit.log(
            action="telegram_db_inaccessible",
            command_category="file_pull",
            command_redacted=f"adb shell ls -la {remote_path}",
            result="inaccessible",
            warning=(
                f"Permission denied for {remote_path}. "
                "Root or allowbackup ADB access is required."
            ),
        )
        summary["db_status"] = "inaccessible"
        return summary

    if probe.state == "probe_failed":
        manifest.add_status_record(
            artifact_class=artifact_class,
            source_type="adb_shell",
            source_command_or_path=remote_path,
            status=STATUS_FAILED,
            reason_code="probe_failed",
        )
        summary["db_status"] = "probe_failed"
        summary["errors"].append(
            f"Probe failed for {remote_path}: {probe.stderr}"
        )
        return summary

    # ── probe.state == "accessible" — pull it ──────────────────────────────
    local_filename = db_group.relative_path.replace("/", "_")
    local_path = dest_dir / local_filename

    pull_info = _pull_and_record(
        adb=adb,
        remote_path=remote_path,
        local_path=local_path,
        expected_size=probe.remote_size,
        manifest=manifest,
        audit=audit,
        artifact_class=artifact_class,
        started_at=started_at,
    )

    summary["db_status"] = pull_info["status"]
    summary["sha256"] = pull_info["sha256"]
    summary["volatile"] = pull_info["volatile"]
    if pull_info.get("warning"):
        summary["warnings"].append(pull_info["warning"])
    if pull_info.get("error"):
        summary["errors"].append(pull_info["error"])

    # ── pull sidecars (WAL / SHM / journal) ────────────────────────────────
    for ext in SQLITE_SIDECAR_EXTENSIONS:
        sidecar_remote = remote_path + ext
        sidecar_local = dest_dir / (local_filename + ext)
        sidecar_started = _now_iso()

        sidecar_probe = _probe_remote_path(adb, sidecar_remote)

        if sidecar_probe.state == "not_present":
            summary["sidecars"].append({
                "remote_path": sidecar_remote,
                "status": "not_present",
                "sha256": "",
            })
            continue

        if sidecar_probe.state in ("inaccessible", "probe_failed"):
            summary["sidecars"].append({
                "remote_path": sidecar_remote,
                "status": sidecar_probe.state,
                "sha256": "",
            })
            summary["warnings"].append(
                f"Sidecar {sidecar_remote}: {sidecar_probe.state}"
            )
            continue

        sidecar_artifact_class = (
            f"{artifact_class}_sidecar{ext.replace('-', '_')}"
        )
        sidecar_info = _pull_and_record(
            adb=adb,
            remote_path=sidecar_remote,
            local_path=sidecar_local,
            expected_size=sidecar_probe.remote_size,
            manifest=manifest,
            audit=audit,
            artifact_class=sidecar_artifact_class,
            started_at=sidecar_started,
            optional=True,
        )
        summary["sidecars"].append({
            "remote_path": sidecar_remote,
            "status": sidecar_info["status"],
            "sha256": sidecar_info["sha256"],
            "volatile": sidecar_info["volatile"],
        })
        if sidecar_info.get("warning"):
            summary["warnings"].append(sidecar_info["warning"])

    return summary


def _inventory_shared_media(
    adb: "ADBClient",
    profile: TelegramProfile,
    audit: "AuditLogger",
) -> dict:
    """Inventory (list only, no pull) shared media roots for *profile*.

    Returns
    -------
    dict
        Keys: ``roots_found``, ``files_found``, ``inventory``, ``warnings``.
    """
    inventory: list[dict] = []
    warnings: list[str] = []

    for media_root in profile.shared_media_roots:
        ls_result = adb.shell(
            ["ls", "-laR", media_root],
            timeout=LONG_ADB_TIMEOUT,
            audit_action=f"telegram_media_ls_{Path(media_root).name}",
        )

        if not ls_result.ok:
            stderr_lower = ls_result.stderr.lower()
            stdout_lower = ls_result.stdout.lower()
            if (
                "no such file" in stderr_lower
                or "no such file" in stdout_lower
                or "not found" in stderr_lower
            ):
                continue
            if "permission denied" in stderr_lower:
                warnings.append(f"Permission denied listing {media_root}")
                continue
            warnings.append(
                f"ls failed for {media_root}: {ls_result.stderr[:200]}"
            )
            continue

        entries = parse_ls_output(ls_result.stdout, current_dir_hint=media_root)
        for entry in entries:
            entry["media_root"] = media_root
            entry["package"] = profile.package
        inventory.extend(entries)

    audit.log(
        action="telegram_media_inventory",
        command_category="file_listing",
        command_redacted=(
            "adb shell ls -laR " + " ".join(profile.shared_media_roots)
        ),
        result="partial" if warnings else STATUS_ACQUIRED,
        warning="; ".join(warnings) if warnings else "",
    )

    return {
        "roots_found": len({e.get("media_root", "") for e in inventory}),
        "files_found": sum(1 for e in inventory if e.get("type") == "file"),
        "inventory": inventory,
        "warnings": warnings,
    }


# ── Public entry point ────────────────────────────────────────────────────────

def acquire_telegram_databases(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Pull Telegram SQLite databases and inventory shared media.

    Iterates :data:`~erakshak.part_b.telegram_paths.TELEGRAM_PROFILES` and
    for each installed variant:

    1. Checks installation via ``pm list packages -e``.
    2. Probes each DB group with ``ls -la`` (accessible/inaccessible/absent).
    3. Pulls accessible DBs and sidecars into ``raw/apps/telegram/<package>/``.
    4. Hashes every successfully pulled file and records it in the manifest.
    5. Inventories world-readable shared media roots (no pull, list only).

    Parameters
    ----------
    adb:
        Initialised :class:`~erakshak.adb.client.ADBClient`.
    case_folder:
        Open :class:`~erakshak.case.case_folder.CaseFolder`.
    manifest:
        :class:`~erakshak.case.manifest.ManifestWriter`.
    audit:
        :class:`~erakshak.case.audit.AuditLogger`.

    Returns
    -------
    dict
        Keys: ``status``, ``packages_found``, ``packages_not_found``,
        ``db_results``, ``media_inventory``, ``volatile_count``,
        ``warnings``, ``errors``.
    """
    audit.log(
        action="telegram_acquisition_start",
        command_category="lifecycle",
        result="started",
    )

    summary: dict = {
        "status": STATUS_ACQUIRED,
        "packages_found": [],
        "packages_not_found": [],
        "db_results": {},
        "media_inventory": {},
        "volatile_count": 0,
        "warnings": [],
        "errors": [],
    }

    any_acquired = False
    any_error = False

    for profile in TELEGRAM_PROFILES:
        pkg = profile.package

        # ── 1. Check installation ───────────────────────────────────────────
        if not _is_package_installed(adb, pkg):
            summary["packages_not_found"].append(pkg)
            audit.log(
                action="telegram_package_not_found",
                command_category="package_check",
                command_redacted=f"pm list packages -e {pkg}",
                result="not_found",
            )
            continue

        summary["packages_found"].append(pkg)
        audit.log(
            action="telegram_package_found",
            command_category="package_check",
            command_redacted=f"pm list packages -e {pkg}",
            result="found",
        )

        # ── 2. Create per-package output directory ──────────────────────────
        pkg_dir = case_folder.raw_apps_telegram_dir / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # ── 3. Pull each DB group ───────────────────────────────────────────
        db_results_for_pkg: list[dict] = []
        for db_group in profile.db_groups:
            db_summary = _acquire_db_group(
                adb=adb,
                profile=profile,
                db_group=db_group,
                dest_dir=pkg_dir,
                manifest=manifest,
                audit=audit,
            )
            db_results_for_pkg.append(db_summary)

            if db_summary["volatile"]:
                summary["volatile_count"] += 1

            db_status = db_summary["db_status"]
            if db_status == STATUS_ACQUIRED:
                any_acquired = True
            elif db_status in ("failed", "probe_failed"):
                any_error = True

            summary["warnings"].extend(db_summary.get("warnings", []))
            summary["errors"].extend(db_summary.get("errors", []))

        summary["db_results"][pkg] = db_results_for_pkg

        # ── 4. Inventory shared media ───────────────────────────────────────
        media_info = _inventory_shared_media(adb, profile, audit)
        summary["media_inventory"][pkg] = media_info
        summary["warnings"].extend(media_info.get("warnings", []))

    # ── Derive overall status ───────────────────────────────────────────────
    if not summary["packages_found"]:
        summary["status"] = STATUS_FAILED
        summary["warnings"].append("No Telegram packages found on device.")
    elif any_error and any_acquired:
        summary["status"] = STATUS_PARTIAL
    elif any_error and not any_acquired:
        summary["status"] = STATUS_FAILED
    elif summary["volatile_count"] > 0:
        summary["status"] = STATUS_PARTIAL
    else:
        summary["status"] = STATUS_ACQUIRED

    audit.log(
        action="telegram_acquisition_complete",
        command_category="lifecycle",
        result=summary["status"],
        warning="; ".join(summary["warnings"][:5]) if summary["warnings"] else "",
        error="; ".join(summary["errors"][:5]) if summary["errors"] else "",
    )

    return summary
