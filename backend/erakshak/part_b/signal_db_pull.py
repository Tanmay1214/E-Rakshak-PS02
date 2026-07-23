"""Signal Android database acquisition engine.

Attempts to pull Signal private SQLite databases and sidecars from installed
Signal package variants. On unrooted devices this is expected to record
``not_accessible`` instead of producing chat data.
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
from erakshak.part_b.signal_paths import (
    SIGNAL_PROFILES,
    SQLITE_SIDECAR_EXTENSIONS,
    SignalDbGroup,
    SignalProfile,
)

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


@dataclass(frozen=True)
class RemoteProbeResult:
    state: str
    remote_size: int | None = None
    stderr: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_remote_path(adb: "ADBClient", remote_path: str) -> RemoteProbeResult:
    result = adb.shell(
        ["ls", "-la", remote_path],
        timeout=DEFAULT_ADB_TIMEOUT,
        audit_action=f"signal_probe_{Path(remote_path).name}",
    )
    stderr_lower = result.stderr.lower()
    stdout_lower = result.stdout.lower()

    if result.timed_out or result.return_code == -127:
        return RemoteProbeResult("probe_failed", stderr=result.stderr[:500])
    if "permission denied" in stderr_lower or "permission denied" in stdout_lower:
        return RemoteProbeResult("inaccessible", stderr=result.stderr[:500])
    if (
        "no such file or directory" in stderr_lower
        or "no such file or directory" in stdout_lower
        or ("not found" in stderr_lower and result.return_code != 0)
    ):
        return RemoteProbeResult("not_present", stderr=result.stderr[:500])
    if result.return_code != 0 and not result.stdout.strip():
        return RemoteProbeResult("probe_failed", stderr=result.stderr[:500])

    entries = parse_ls_output(result.stdout, current_dir_hint=str(Path(remote_path).parent))
    remote_size = None
    for entry in entries:
        if entry.get("type") == "file":
            remote_size = entry.get("size")
            break
    return RemoteProbeResult("accessible", remote_size=remote_size, stderr=result.stderr[:500])


def _is_package_installed(adb: "ADBClient", package: str) -> bool:
    result = adb.shell(
        ["pm", "list", "packages", "-e", package],
        timeout=DEFAULT_ADB_TIMEOUT,
        audit_action=f"signal_pm_check_{package}",
    )
    if not result.ok:
        return False
    return any(line.strip() == f"package:{package}" for line in result.stdout.splitlines())


def _pull_and_record(
    adb: "ADBClient",
    remote_path: str,
    local_path: Path,
    expected_size: int | None,
    manifest: "ManifestWriter",
    audit: "AuditLogger",
    artifact_class: str,
    started_at: str,
) -> dict:
    pull_result = adb.pull(
        remote_path,
        str(local_path),
        timeout=MEDIA_PULL_TIMEOUT,
        audit_action=f"signal_pull_{Path(remote_path).name}",
    )
    completed_at = _now_iso()

    if not pull_result.ok or not local_path.exists():
        if local_path.exists():
            try:
                local_path.unlink()
            except OSError:
                pass
        err_msg = pull_result.stderr.strip()[:500] or "pull returned non-zero exit code"
        manifest.add_status_record(artifact_class, "adb_pull", remote_path, STATUS_FAILED, "pull_failed")
        audit.log(
            action="signal_db_pull_failed",
            command_category="file_pull",
            command_redacted=f"adb pull {remote_path}",
            result="failed",
            return_code=pull_result.return_code,
            duration_ms=pull_result.duration_ms,
            output_path=str(local_path),
            error=err_msg,
        )
        return {"status": "failed", "sha256": "", "local_size": None, "volatile": False, "error": err_msg, "warning": ""}

    local_size = local_path.stat().st_size
    sha256 = hash_file(local_path)
    volatile = expected_size is not None and local_size != expected_size
    status = STATUS_PARTIAL if volatile else STATUS_ACQUIRED
    reason = "size_mismatch_volatile" if volatile else ""
    warning = (
        f"Volatile acquisition: remote size was {expected_size} bytes but local file is {local_size} bytes."
        if volatile else ""
    )
    manifest.add_file(
        artifact_class,
        "adb_pull",
        remote_path,
        local_path,
        status=status,
        reason_code=reason,
        started_at=started_at,
        completed_at=completed_at,
    )
    audit.log(
        action="signal_db_pulled",
        command_category="file_pull",
        command_redacted=f"adb pull {remote_path}",
        result=status,
        return_code=pull_result.return_code,
        duration_ms=pull_result.duration_ms,
        output_path=str(local_path),
        warning=warning,
    )
    return {"status": "volatile" if volatile else STATUS_ACQUIRED, "sha256": sha256, "local_size": local_size, "volatile": volatile, "error": "", "warning": warning}


def _acquire_db_group(
    adb: "ADBClient",
    profile: SignalProfile,
    db_group: SignalDbGroup,
    dest_dir: Path,
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    remote_path = f"{profile.private_data_root}/{db_group.relative_path}"
    artifact_class = f"signal_db_{profile.package}_{Path(db_group.relative_path).stem}"
    summary = {"remote_path": remote_path, "db_status": "failed", "sha256": "", "volatile": False, "sidecars": [], "warnings": [], "errors": []}

    probe = _probe_remote_path(adb, remote_path)
    if probe.state == "not_present":
        if db_group.required:
            manifest.add_status_record(artifact_class, "adb_shell", remote_path, STATUS_NOT_ACCESSIBLE, "not_present")
        summary["db_status"] = "not_present"
        return summary
    if probe.state == "inaccessible":
        manifest.add_status_record(artifact_class, "adb_shell", remote_path, STATUS_NOT_ACCESSIBLE, "permission_denied")
        audit.log(
            action="signal_db_inaccessible",
            command_category="file_pull",
            command_redacted=f"adb shell ls -la {remote_path}",
            result="inaccessible",
            warning="Permission denied. Root, filesystem image, or import lane is required for Signal Android chats.",
        )
        summary["db_status"] = "inaccessible"
        return summary
    if probe.state == "probe_failed":
        manifest.add_status_record(artifact_class, "adb_shell", remote_path, STATUS_FAILED, "probe_failed")
        summary["db_status"] = "probe_failed"
        summary["errors"].append(f"Probe failed for {remote_path}: {probe.stderr}")
        return summary

    local_filename = db_group.relative_path.replace("/", "_")
    local_path = dest_dir / local_filename
    pull_info = _pull_and_record(adb, remote_path, local_path, probe.remote_size, manifest, audit, artifact_class, _now_iso())
    summary["db_status"] = pull_info["status"]
    summary["sha256"] = pull_info["sha256"]
    summary["volatile"] = pull_info["volatile"]
    if pull_info["warning"]:
        summary["warnings"].append(pull_info["warning"])
    if pull_info["error"]:
        summary["errors"].append(pull_info["error"])

    for ext in SQLITE_SIDECAR_EXTENSIONS:
        sidecar_remote = remote_path + ext
        sidecar_local = dest_dir / (local_filename + ext)
        sidecar_probe = _probe_remote_path(adb, sidecar_remote)
        if sidecar_probe.state == "not_present":
            summary["sidecars"].append({"remote_path": sidecar_remote, "status": "not_present", "sha256": ""})
            continue
        if sidecar_probe.state in ("inaccessible", "probe_failed"):
            summary["sidecars"].append({"remote_path": sidecar_remote, "status": sidecar_probe.state, "sha256": ""})
            continue
        sidecar_info = _pull_and_record(adb, sidecar_remote, sidecar_local, sidecar_probe.remote_size, manifest, audit, f"{artifact_class}_sidecar{ext.replace('-', '_')}", _now_iso())
        summary["sidecars"].append({"remote_path": sidecar_remote, "status": sidecar_info["status"], "sha256": sidecar_info["sha256"], "volatile": sidecar_info["volatile"]})
    return summary


def _inventory_shared_media(adb: "ADBClient", profile: SignalProfile, audit: "AuditLogger") -> dict:
    inventory: list[dict] = []
    warnings: list[str] = []
    for media_root in profile.shared_media_roots:
        result = adb.shell(["ls", "-laR", media_root], timeout=LONG_ADB_TIMEOUT, audit_action=f"signal_media_ls_{Path(media_root).name}")
        if not result.ok:
            err = (result.stderr + result.stdout).lower()
            if "no such file" in err or "not found" in err:
                continue
            if "permission denied" in err:
                warnings.append(f"Permission denied listing {media_root}")
                continue
            warnings.append(f"ls failed for {media_root}: {result.stderr[:200]}")
            continue
        for entry in parse_ls_output(result.stdout, current_dir_hint=media_root):
            entry["media_root"] = media_root
            entry["package"] = profile.package
            inventory.append(entry)
    audit.log(action="signal_media_inventory", command_category="file_listing", result="partial" if warnings else STATUS_ACQUIRED, warning="; ".join(warnings))
    return {"roots_found": len({e.get("media_root", "") for e in inventory}), "files_found": sum(1 for e in inventory if e.get("type") == "file"), "inventory": inventory, "warnings": warnings}


def _pull_support_files(
    adb: "ADBClient",
    profile: SignalProfile,
    dest_dir: Path,
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Pull selected non-database Signal support artifacts.

    These files can be useful for version/config/key-storage analysis. They are
    evidence artifacts, not guaranteed database keys.
    """
    support_summary = {"files": [], "warnings": []}
    support_roots = ("shared_prefs", "no_backup")
    for root in support_roots:
        remote_root = f"{profile.private_data_root}/{root}"
        listing = adb.shell(["ls", "-la", remote_root], timeout=DEFAULT_ADB_TIMEOUT, audit_action=f"signal_ls_{root}")
        if not listing.ok:
            combined = (listing.stderr + listing.stdout).lower()
            if "no such file" in combined or "not found" in combined:
                continue
            support_summary["warnings"].append(f"Could not list {remote_root}: {listing.stderr[:200]}")
            continue

        entries = parse_ls_output(listing.stdout, current_dir_hint=remote_root)
        local_root = dest_dir / root
        local_root.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            if entry.get("type") != "file":
                continue
            remote_path = entry.get("path") or f"{remote_root}/{entry.get('filename', '')}"
            filename = Path(str(remote_path)).name
            if not filename:
                continue
            local_path = local_root / filename
            info = _pull_and_record(
                adb=adb,
                remote_path=str(remote_path),
                local_path=local_path,
                expected_size=entry.get("size"),
                manifest=manifest,
                audit=audit,
                artifact_class=f"signal_support_{profile.package}_{root}_{Path(filename).stem}",
                started_at=_now_iso(),
            )
            support_summary["files"].append({"remote_path": remote_path, "status": info["status"], "sha256": info["sha256"]})
            if info.get("warning"):
                support_summary["warnings"].append(info["warning"])
    return support_summary


def acquire_signal_databases(adb: "ADBClient", case_folder: "CaseFolder", manifest: "ManifestWriter", audit: "AuditLogger") -> dict:
    """Pull Signal Android databases and inventory shared media roots."""
    audit.log(action="signal_acquisition_start", command_category="lifecycle", result="started")
    summary = {"status": STATUS_ACQUIRED, "packages_found": [], "packages_not_found": [], "db_results": {}, "media_inventory": {}, "volatile_count": 0, "warnings": [], "errors": []}
    any_acquired = False
    any_error = False

    for profile in SIGNAL_PROFILES:
        if not _is_package_installed(adb, profile.package):
            summary["packages_not_found"].append(profile.package)
            audit.log(action="signal_package_not_found", command_category="package_check", command_redacted=f"pm list packages -e {profile.package}", result="not_found")
            continue

        summary["packages_found"].append(profile.package)
        audit.log(action="signal_package_found", command_category="package_check", command_redacted=f"pm list packages -e {profile.package}", result="found")
        pkg_dir = case_folder.raw_apps_signal_dir / profile.package
        pkg_dir.mkdir(parents=True, exist_ok=True)

        db_results = []
        for db_group in profile.db_groups:
            db_summary = _acquire_db_group(adb, profile, db_group, pkg_dir, manifest, audit)
            db_results.append(db_summary)
            if db_summary["volatile"]:
                summary["volatile_count"] += 1
            if db_summary["db_status"] == STATUS_ACQUIRED:
                any_acquired = True
            elif db_summary["db_status"] in ("failed", "probe_failed"):
                any_error = True
            summary["warnings"].extend(db_summary.get("warnings", []))
            summary["errors"].extend(db_summary.get("errors", []))
        summary["db_results"][profile.package] = db_results

        media_info = _inventory_shared_media(adb, profile, audit)
        summary["media_inventory"][profile.package] = media_info
        summary["warnings"].extend(media_info.get("warnings", []))

        support_info = _pull_support_files(adb, profile, pkg_dir, manifest, audit)
        summary.setdefault("support_files", {})[profile.package] = support_info
        summary["warnings"].extend(support_info.get("warnings", []))

    if not summary["packages_found"]:
        summary["status"] = STATUS_FAILED
        summary["warnings"].append("No Signal packages found on device.")
    elif any_error and any_acquired:
        summary["status"] = STATUS_PARTIAL
    elif any_error and not any_acquired:
        summary["status"] = STATUS_FAILED
    elif summary["volatile_count"] > 0:
        summary["status"] = STATUS_PARTIAL
    else:
        summary["status"] = STATUS_ACQUIRED

    audit.log(action="signal_acquisition_complete", command_category="lifecycle", result=summary["status"], warning="; ".join(summary["warnings"][:5]), error="; ".join(summary["errors"][:5]))
    return summary
