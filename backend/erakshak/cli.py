#!/usr/bin/env python3
"""
E-RAKSHAK CLI — Android Rapid Evidence Triage & Forensic Preview Tool.

Subcommands:
    preflight        Run pre-flight checks on a connected Android device.
    acquire-part-a   Perform full Phase-1 Part-A acquisition.
    verify           Verify SHA-256 integrity of a case folder.

Usage examples:
    python -m erakshak preflight --case CASE001 --exhibit EX001
    python -m erakshak acquire-part-a --case CASE001 --exhibit EX001 --output cases
    python -m erakshak verify --case-folder cases/CASE001/EX001
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── project imports ──────────────────────────────────────────────────
from erakshak.config.defaults import TOOL_VERSION, TOOL_NAME, DEFAULT_ADB_TIMEOUT
from erakshak.adb.client import ADBClient
from erakshak.case.case_folder import CaseFolder
from erakshak.case.manifest import ManifestWriter
from erakshak.case.audit import AuditLogger
from erakshak.case.hashing import verify_sha256sums

from erakshak.acquisition.preflight import run_preflight
from erakshak.acquisition.device_info import acquire_device_info
from erakshak.acquisition.installed_apps import acquire_installed_apps
from erakshak.acquisition.accounts import acquire_accounts
from erakshak.acquisition.timeline import acquire_timeline
from erakshak.acquisition.system_logs import acquire_system_logs
from erakshak.acquisition.network import acquire_network
from erakshak.acquisition.media import acquire_media
from erakshak.acquisition.collector_import import import_collector_export
from erakshak.acquisition.call_logs import acquire_call_logs
from erakshak.acquisition.sms import acquire_sms
from erakshak.acquisition.contacts import acquire_contacts


# ═════════════════════════════════════════════════════════════════════
# Banner
# ═════════════════════════════════════════════════════════════════════
BANNER = r"""
╔═══════════════════════════════════════════════════════════════╗
║   _____ ____  ___   _  _______ _   _   _    _  __           ║
║  | ____|  _ \/ _ \ | |/ / ___|| | | | / \  | |/ /           ║
║  |  _| | |_) | |_| ||   /\___ \| |_| |/ _ \ | ' /            ║
║  | |___|  _ <|  _  || |\ \ ___) |  _  / ___ \| . \            ║
║  |_____|_| \_\_| |_||_| \_\____/|_| |_/_/   \_\_|\_\           ║
║                                                               ║
║  Android Rapid Evidence Triage & Forensic Preview Tool        ║
║  Version {ver:<52s}║
╚═══════════════════════════════════════════════════════════════╝
""".format(ver=TOOL_VERSION)


def print_banner() -> None:
    """Print the E-RAKSHAK startup banner."""
    try:
        print(BANNER)
    except UnicodeEncodeError:
        print("-" * 64)
        print(f"  E-RAKSHAK  (v{TOOL_VERSION})")
        print("  Android Rapid Evidence Triage & Forensic Preview Tool")
        print("-" * 64)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _resolve_serial(serial_arg: str, adb_path: str = "adb") -> str:
    """Resolve the *serial* argument.

    If ``serial_arg`` is ``"auto"`` we ask ADB for the list of attached
    devices and pick the first one.  Otherwise we use it verbatim.
    """
    if serial_arg.lower() != "auto":
        return serial_arg

    import subprocess
    try:
        result = subprocess.run(
            [adb_path, "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_ADB_TIMEOUT,
        )
        from erakshak.adb.parsers import parse_adb_devices
        devices = parse_adb_devices(result.stdout)
        if not devices:
            print("[ERROR] No ADB devices found. Connect a device and try again.")
            sys.exit(1)
        if len(devices) > 1:
            print("[WARNING] Multiple devices detected — using the first one.")
            for d in devices:
                print(f"  * {d.get('serial', '?')}  ({d.get('state', '?')})")
        serial = devices[0]["serial"]
        print(f"[AUTO] Selected device: {serial}")
        return serial
    except FileNotFoundError:
        print("[ERROR] ADB binary not found. Set --adb-path or add ADB to PATH.")
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] Failed to auto-detect device: {exc}")
        sys.exit(1)


def _safe_get(data: dict[str, Any] | None, *keys: str, default: str = "N/A") -> str:
    """Safely traverse nested dicts / plain dicts."""
    if data is None:
        return default
    obj: Any = data
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, None)
        else:
            return default
        if obj is None:
            return default
    return str(obj) if obj is not None else default


# ═════════════════════════════════════════════════════════════════════
# Sub-command handlers
# ═════════════════════════════════════════════════════════════════════

def cmd_preflight(args: argparse.Namespace) -> None:
    """Run pre-flight checks only."""
    print_banner()
    print(f"[*] Preflight - Case: {args.case}  Exhibit: {args.exhibit}")

    adb_path = getattr(args, "adb_path", "adb")
    serial = _resolve_serial(args.serial, adb_path=adb_path)
    output_root = Path(args.output).resolve()

    # Infrastructure ---------------------------------------------------
    case_folder = CaseFolder(output_root, args.case, args.exhibit)
    case_path = case_folder.create()

    audit_path = case_path / "acquisition" / "audit.jsonl"
    manifest_path = case_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = case_path / "hashes" / "sha256sums.txt"
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)

    audit = AuditLogger(audit_path, args.case, args.exhibit)
    manifest = ManifestWriter(manifest_path, sha256sums_path, args.case, args.exhibit)
    client = ADBClient(serial, audit, adb_path)

    # Execute ----------------------------------------------------------
    print("[*] Running preflight checks...")
    pf_result = run_preflight(
        adb=client,
        case_folder=case_folder,
        case_id=args.case,
        exhibit_id=args.exhibit,
        manifest=manifest,
        audit=audit,
    )

    # Summary ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("  PREFLIGHT SUMMARY")
    print("=" * 60)
    print(f"  Case folder  : {case_path}")
    print(f"  Device serial: {serial}")
    print(f"  Model        : {_safe_get(pf_result, 'device_model')}")
    print(f"  Android ver  : {_safe_get(pf_result, 'android_version')}")
    print(f"  ADB status   : {_safe_get(pf_result, 'device_state')}")
    print(f"  Battery level: {_safe_get(pf_result, 'battery_summary', 'level')}%")
    print(f"  SELinux      : {_safe_get(pf_result, 'selinux_status')}")
    print(f"  Root avail   : {_safe_get(pf_result, 'root_available')}")
    warnings = pf_result.get("warnings", []) if isinstance(pf_result, dict) else []
    if warnings:
        print("  [WARNINGS]:")
        for w in warnings:
            print(f"     * {w}")
    print("=" * 60)
    print("[SUCCESS] Preflight complete.\n")


def cmd_acquire_part_a(args: argparse.Namespace) -> None:  # noqa: C901 — intentionally sequential
    """Run full Phase-1 Part-A acquisition."""
    print_banner()
    start_time = datetime.now(timezone.utc)
    print(f"[*] Acquisition Part-A - Case: {args.case}  Exhibit: {args.exhibit}")
    print(f"[*] Started at {start_time.isoformat()}")

    adb_path = getattr(args, "adb_path", "adb")
    serial = _resolve_serial(args.serial, adb_path=adb_path)
    output_root = Path(args.output).resolve()

    # Infrastructure ---------------------------------------------------
    case_folder = CaseFolder(output_root, args.case, args.exhibit)
    case_path = case_folder.create()

    audit_path = case_path / "acquisition" / "audit.jsonl"
    manifest_path = case_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = case_path / "hashes" / "sha256sums.txt"
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)

    audit = AuditLogger(audit_path, args.case, args.exhibit)
    manifest = ManifestWriter(manifest_path, sha256sums_path, args.case, args.exhibit)
    client = ADBClient(serial, audit, adb_path)

    # Shared state for the summary ------------------------------------
    results: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []

    # Helper to run a module safely -----------------------------------
    def _run(name: str, fn, **kwargs) -> Any:  # type: ignore[no-untyped-def]
        print(f"\n[{len(results)+1}/12] Running {name}...")
        try:
            r = fn(**kwargs)
            results[name] = r
            print(f"  [OK] {name} completed.")
            return r
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"{name} failed: {exc}"
            errors.append(msg)
            results[name] = {"status": "failed", "error": str(exc)}
            print(f"  [FAIL] {msg}")
            print(f"      {tb.splitlines()[-1]}")
            audit.log(action="module_error", result="failed", error=msg)
            return None

    # 1. Preflight -----------------------------------------------------
    _run(
        "preflight",
        run_preflight,
        adb=client,
        case_folder=case_folder,
        case_id=args.case,
        exhibit_id=args.exhibit,
        manifest=manifest,
        audit=audit,
    )

    # 2. Device info ---------------------------------------------------
    _run("device_info", acquire_device_info, adb=client, case_folder=case_folder, manifest=manifest, audit=audit)

    # 3. Installed apps ------------------------------------------------
    _run("installed_apps", acquire_installed_apps, adb=client, case_folder=case_folder, manifest=manifest, audit=audit)

    # 4. Accounts ------------------------------------------------------
    _run("accounts", acquire_accounts, adb=client, case_folder=case_folder, manifest=manifest, audit=audit)

    # 5. Timeline ------------------------------------------------------
    _run("timeline", acquire_timeline, adb=client, case_folder=case_folder, manifest=manifest, audit=audit)

    # 6. System logs ---------------------------------------------------
    _run("system_logs", acquire_system_logs, adb=client, case_folder=case_folder, manifest=manifest, audit=audit)

    # 7. Network -------------------------------------------------------
    _run("network", acquire_network, adb=client, case_folder=case_folder, manifest=manifest, audit=audit)

    # 8. Media ---------------------------------------------------------
    media_kwargs: dict[str, Any] = {
        "adb": client,
        "case_folder": case_folder,
        "manifest": manifest,
        "audit": audit,
    }
    if hasattr(args, "media_days") and args.media_days is not None:
        media_kwargs["media_days"] = args.media_days
    if hasattr(args, "media_max_bytes") and args.media_max_bytes is not None:
        media_kwargs["media_max_bytes"] = args.media_max_bytes
    if hasattr(args, "pull_media") and args.pull_media is not None:
        media_kwargs["pull_media"] = args.pull_media
    _run("media", acquire_media, **media_kwargs)

    # 9. Call logs -----------------------------------------------------
    _run(
        "call_logs",
        acquire_call_logs,
        adb=client,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit,
        collector_folder=args.collector_export_folder,
    )

    # 10. SMS Messages -------------------------------------------------
    _run(
        "sms",
        acquire_sms,
        adb=client,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit,
        collector_folder=args.collector_export_folder,
    )

    # 11. Contacts -----------------------------------------------------
    _run(
        "contacts",
        acquire_contacts,
        adb=client,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit,
        collector_folder=args.collector_export_folder,
    )

    # 12. Collector import (optional) ----------------------------------
    collector_kwargs: dict[str, Any] = {
        "collector_folder": args.collector_export_folder,
        "case_folder": case_folder,
        "manifest": manifest,
        "audit": audit,
    }
    _run("collector_import", import_collector_export, **collector_kwargs)

    # ── Aggregate warnings from module results ────────────────────────
    for name, r in results.items():
        if isinstance(r, dict):
            for w in r.get("warnings", []):
                warnings.append(f"[{name}] {w}")

    # ── Final Summary ─────────────────────────────────────────────────
    end_time = datetime.now(timezone.utc)
    elapsed = (end_time - start_time).total_seconds()

    pf = results.get("preflight") or {}
    di = results.get("device_info") or {}
    ia = results.get("installed_apps") or {}
    ac = results.get("accounts") or {}
    tl = results.get("timeline") or {}
    sl = results.get("system_logs") or {}
    nw = results.get("network") or {}
    md = results.get("media") or {}
    cl = results.get("call_logs") or {}
    sm = results.get("sms") or {}
    co = results.get("contacts") or {}

    overall = "SUCCESS" if not errors else "COMPLETED_WITH_ERRORS"

    print("\n")
    print("=" * 64)
    print("  E-RAKSHAK - ACQUISITION PART-A FINAL SUMMARY")
    print("=" * 64)
    print(f"  Case folder       : {case_path}")
    print(f"  Device model      : {_safe_get(di, 'device_identity', 'model')}")
    print(f"  Android version   : {_safe_get(di, 'software_summary', 'android_release')}")
    print(f"  Security patch    : {_safe_get(di, 'software_summary', 'security_patch')}")
    print(f"  Installed apps    : {_safe_get(ia, 'app_count', default='0')}")
    print(f"  Account/email leads: {_safe_get(ac, 'account_count', default='0')} accounts / {_safe_get(ac, 'email_count', default='0')} emails")
    print(f"  Call logs         : {_safe_get(cl, 'call_count', default='0')} (source: {_safe_get(cl, 'source', default='none')})")
    print(f"  SMS messages      : {_safe_get(sm, 'message_count', default='0')} (source: {_safe_get(sm, 'source', default='none')})")
    print(f"  Contacts          : {_safe_get(co, 'contact_count', default='0')} (source: {_safe_get(co, 'source', default='none')})")
    print(f"  Timeline events   : {_safe_get(tl, 'timeline_event_count', default='0')}")
    print(f"  Log events        : {_safe_get(sl, 'event_count', default='0')}")
    print(f"  Network status    : {_safe_get(nw, 'status', default='N/A')}")
    inventoried = _safe_get(md, "files_inventoried", default="0")
    pulled = _safe_get(md, "files_pulled", default="0")
    print(f"  Media inventoried : {inventoried}")
    print(f"  Media pulled      : {pulled}")
    print(f"  Elapsed time      : {elapsed:.1f}s")
    print(f"  Overall status    : {overall}")
    if warnings:
        print("  --- Warnings ---")
        for w in warnings:
            print(f"    [WARN] {w}")
    if errors:
        print("  --- Errors ---")
        for e in errors:
            print(f"    [ERROR] {e}")
    print("=" * 64)
    print("[SUCCESS] Acquisition Part-A finished.\n")


def cmd_telegram_acquire(args: argparse.Namespace) -> None:
    """Run Telegram MVP acquisition and parsing pipeline."""
    print_banner()
    start_time = datetime.now(timezone.utc)
    print(f"[*] Telegram MVP - Case: {args.case}  Exhibit: {args.exhibit}")
    print(f"[*] Started at {start_time.isoformat()}")

    adb_path = getattr(args, "adb_path", "adb")
    serial = _resolve_serial(args.serial, adb_path=adb_path)
    output_root = Path(args.output).resolve()

    # Infrastructure
    case_folder = CaseFolder(output_root, args.case, args.exhibit)
    case_path = case_folder.create()

    audit_path = case_path / "acquisition" / "audit.jsonl"
    manifest_path = case_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = case_path / "hashes" / "sha256sums.txt"
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)

    audit = AuditLogger(audit_path, args.case, args.exhibit)
    manifest = ManifestWriter(manifest_path, sha256sums_path, args.case, args.exhibit)
    client = ADBClient(serial, audit, adb_path)

    from erakshak.part_b.telegram_pipeline import run_telegram_pipeline

    print("\n" + "=" * 60)
    print("  TELEGRAM ACQUISITION & PARSING")
    print("=" * 60)
    
    summary = run_telegram_pipeline(
        adb=client,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit
    )

    end_time = datetime.now(timezone.utc)
    elapsed = (end_time - start_time).total_seconds()

    acq = summary.get("acquisition", {})
    pars = summary.get("parsing", {})

    print("\n" + "=" * 60)
    print("  TELEGRAM MVP FINAL SUMMARY")
    print("=" * 60)
    print(f"  Packages found    : {len(acq.get('packages_found', []))}")
    print(f"  Packages missing  : {len(acq.get('packages_not_found', []))}")
    print(f"  Databases acquired: {len(pars.get('parsed_dbs', [])) + len(pars.get('unsupported_dbs', []))}")
    print(f"  Parsed successfully: {len(pars.get('parsed_dbs', []))}")
    print(f"  Unsupported schemas: {len(pars.get('unsupported_dbs', []))}")
    print(f"  Extracted users   : {pars.get('total_users', 0)}")
    print(f"  Extracted messages: {pars.get('total_messages', 0)}")
    print(f"  Extracted dialogs : {pars.get('total_dialogs', 0)}")
    print(f"  Output directory  : {summary.get('output_dir', 'N/A')}")
    print(f"  Elapsed time      : {elapsed:.1f}s")
    
    warnings = acq.get("warnings", []) + pars.get("warnings", [])
    errors = acq.get("errors", []) + pars.get("errors", [])
    
    if warnings:
        print("  --- Warnings ---")
        for w in warnings:
            print(f"    [WARN] {w}")
    if errors:
        print("  --- Errors ---")
        for e in errors:
            print(f"    [ERROR] {e}")
            
    if errors:
        print("=" * 60)
        print("[COMPLETED WITH ERRORS] Telegram MVP finished.\n")
        sys.exit(1)
    else:
        print("=" * 60)
        print("[SUCCESS] Telegram MVP finished.\n")
        sys.exit(0)


def cmd_signal_acquire(args: argparse.Namespace) -> None:
    """Run Signal Android acquisition and parsing pipeline."""
    print_banner()
    start_time = datetime.now(timezone.utc)
    print(f"[*] Signal MVP - Case: {args.case}  Exhibit: {args.exhibit}")
    print(f"[*] Started at {start_time.isoformat()}")

    adb_path = getattr(args, "adb_path", "adb")
    serial = _resolve_serial(args.serial, adb_path=adb_path)
    output_root = Path(args.output).resolve()

    case_folder = CaseFolder(output_root, args.case, args.exhibit)
    case_path = case_folder.create()

    audit_path = case_path / "acquisition" / "audit.jsonl"
    manifest_path = case_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = case_path / "hashes" / "sha256sums.txt"
    sha256sums_path.parent.mkdir(parents=True, exist_ok=True)

    audit = AuditLogger(audit_path, args.case, args.exhibit)
    audit_path.touch(exist_ok=True)
    manifest = ManifestWriter(manifest_path, sha256sums_path, args.case, args.exhibit)
    client = ADBClient(serial, audit, adb_path)

    from erakshak.part_b.signal_pipeline import run_signal_pipeline

    signal_db_key = None
    if getattr(args, "signal_db_key", None):
        signal_db_key = args.signal_db_key.strip()
    if getattr(args, "signal_db_key_file", None):
        try:
            signal_db_key = Path(args.signal_db_key_file).read_text(encoding="utf-8").strip().splitlines()[0]
        except Exception as exc:
            print(f"[ERROR] Could not read --signal-db-key-file: {exc}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("  SIGNAL ACQUISITION & PARSING")
    print("=" * 60)

    summary = run_signal_pipeline(
        adb=client,
        case_folder=case_folder,
        manifest=manifest,
        audit=audit,
        signal_db_key=signal_db_key,
        auto_extract_key=getattr(args, "signal_auto_key", False),
    )

    end_time = datetime.now(timezone.utc)
    elapsed = (end_time - start_time).total_seconds()

    acq = summary.get("acquisition", {})
    pars = summary.get("parsing", {})

    print("\n" + "=" * 60)
    print("  SIGNAL MVP FINAL SUMMARY")
    print("=" * 60)
    print(f"  Packages found    : {len(acq.get('packages_found', []))}")
    print(f"  Packages missing  : {len(acq.get('packages_not_found', []))}")
    print(f"  Databases acquired: {len(pars.get('parsed_dbs', [])) + len(pars.get('unsupported_dbs', []))}")
    print(f"  Parsed successfully: {len(pars.get('parsed_dbs', []))}")
    print(f"  Unsupported schemas: {len(pars.get('unsupported_dbs', []))}")
    print(f"  Extracted recipients: {pars.get('total_recipients', 0)}")
    print(f"  Extracted threads : {pars.get('total_threads', 0)}")
    print(f"  Extracted messages: {pars.get('total_messages', 0)}")
    key_info = summary.get("key_extraction", {})
    if key_info.get("attempted"):
        print(f"  Auto key extracted: {'yes' if key_info.get('success') else 'no'}")
    print(f"  Output directory  : {summary.get('output_dir', 'N/A')}")
    print(f"  Elapsed time      : {elapsed:.1f}s")

    warnings = acq.get("warnings", []) + pars.get("warnings", [])
    errors = acq.get("errors", []) + pars.get("errors", [])
    if warnings:
        print("  --- Warnings ---")
        for w in warnings:
            print(f"    [WARN] {w}")
    if errors:
        print("  --- Errors ---")
        for e in errors:
            print(f"    [ERROR] {e}")

    print("=" * 60)
    if errors:
        print("[COMPLETED WITH ERRORS] Signal MVP finished.\n")
        sys.exit(1)
    print("[SUCCESS] Signal MVP finished.\n")
    sys.exit(0)


def cmd_verify(args: argparse.Namespace) -> None:
    """Verify SHA-256 integrity of an existing case folder."""
    print_banner()
    case_folder = Path(args.case_folder).resolve()
    sha256sums_path = case_folder / "hashes" / "sha256sums.txt"

    if not sha256sums_path.exists():
        print(f"[ERROR] SHA-256 sums file not found: {sha256sums_path}")
        sys.exit(1)

    print(f"[*] Verifying integrity - {sha256sums_path}")
    result = verify_sha256sums(sha256sums_path)

    total = result.get("total", 0)
    verified = result.get("verified", 0)
    missing = result.get("missing", 0)
    mismatched = result.get("mismatched", 0)

    print("\n" + "=" * 50)
    print("  INTEGRITY VERIFICATION REPORT")
    print("=" * 50)
    print(f"  Total entries : {total}")
    print(f"  Verified OK   : {verified}")
    print(f"  Missing files : {missing}")
    print(f"  Mismatched    : {mismatched}")
    print("=" * 50)

    if mismatched > 0 or missing > 0:
        details = result.get("details", [])
        for d in details:
            status = d.get("status", "")
            if status in ("missing", "mismatched"):
                print(f"  [FAIL] [{status.upper()}] {d.get('file', '?')}")
        print("\n[FAIL] INTEGRITY CHECK FAILED.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All files verified - integrity intact.\n")
        sys.exit(0)


def cmd_whatsapp_auto_decrypt(args: argparse.Namespace) -> None:
    """Run WhatsApp automated key capture and decryption pipeline."""
    print_banner()
    print("[WARNING] This will run authorized WhatsApp UI automation on the connected phone.")
    print("Ensure legal authority and keep the device unlocked.")
    print("Key will be used in memory and will not be printed.")

    from erakshak.part_b.whatsapp_pipeline import run_whatsapp_key_capture_and_decrypt

    # Run pipeline
    res = run_whatsapp_key_capture_and_decrypt(
        case_id=args.case,
        exhibit_id=args.exhibit,
        encrypted_backup_path=Path(args.backup),
        output_root=Path(args.output),
        adb_path=args.adb_path,
        serial=args.serial if args.serial != "auto" else None,
    )

    if res["status"] == "success":
        print("\n" + "=" * 50)
        print("  WhatsApp Decryption Successful")
        print("=" * 50)
        print(f"  Encrypted backup copied path: {res['encrypted_backup_path']}")
        print(f"  Decrypted msgstore.db path  : {res['decrypted_db_path']}")
        print(f"  SHA-256 of encrypted backup : {res['encrypted_sha256']}")
        print(f"  SHA-256 of decrypted DB     : {res['decrypted_sha256']}")
        print(f"  SQLite verification status  : {res['sqlite_verified']}")
        print("=" * 50 + "\n")
        sys.exit(0)
    else:
        err = res.get("error", "Decryption failed.")
        print(f"\n[ERROR] WhatsApp Decryption Failed: {err}\n")
        sys.exit(1)


def cmd_whatsapp_decrypt(args: argparse.Namespace) -> None:
    """Run WhatsApp decryption using a manually supplied hex key."""
    print_banner()
    print("Key will be used in memory and will not be printed.")

    from erakshak.part_b.whatsapp_pipeline import run_whatsapp_key_capture_and_decrypt

    # Run pipeline
    res = run_whatsapp_key_capture_and_decrypt(
        case_id=args.case,
        exhibit_id=args.exhibit,
        encrypted_backup_path=Path(args.backup),
        output_root=Path(args.output),
        adb_path=args.adb_path,
        serial=args.serial if args.serial != "auto" else None,
        hex_key_manual=args.hex_key,
    )


    if res["status"] == "success":
        print("\n" + "=" * 50)
        print("  WhatsApp Decryption Successful")
        print("=" * 50)
        print(f"  Encrypted backup copied path: {res['encrypted_backup_path']}")
        print(f"  Decrypted msgstore.db path  : {res['decrypted_db_path']}")
        print(f"  SHA-256 of encrypted backup : {res['encrypted_sha256']}")
        print(f"  SHA-256 of decrypted DB     : {res['decrypted_sha256']}")
        print(f"  SQLite verification status  : {res['sqlite_verified']}")
        print("=" * 50 + "\n")
        sys.exit(0)
    else:
        err = res.get("error", "Decryption failed.")
        print(f"\n[ERROR] WhatsApp Decryption Failed: {err}\n")
        sys.exit(1)


def cmd_parse_whatsapp(args: argparse.Namespace) -> None:
    """Parse decrypted WhatsApp database with Whatsapp-Chat-Exporter."""
    print_banner()
    print("[*] Parsing decrypted WhatsApp database with Whatsapp-Chat-Exporter")

    from erakshak.part_b.whatsapp_parse_pipeline import parse_decrypted_whatsapp

    input_dir = Path(args.input) if args.input else None
    wa_db = Path(args.wa_db) if args.wa_db else None
    media_dir = Path(args.media) if args.media else None
    vcard_path = Path(args.vcard) if args.vcard else None
    time_offset = int(args.time_offset) if args.time_offset is not None else None
    
    source = getattr(args, "source", None)
    package = getattr(args, "package", "com.whatsapp")

    # For --source rooted, ensure the processed folder exists
    if source == "rooted" and input_dir is None:
        rooted_dir = Path(args.output) / args.case / args.exhibit / "processed" / "apps" / "whatsapp" / "rooted" / package
        if not rooted_dir.is_dir():
            print(f"\n[ERROR] Rooted WhatsApp parser-ready folder not found. Run acquire-whatsapp-root or import-whatsapp-root first.\n")
            sys.exit(1)
        input_dir = rooted_dir

    try:
        res = parse_decrypted_whatsapp(
            case_id=args.case,
            exhibit_id=args.exhibit,
            output_root=Path(args.output),
            input_dir=input_dir,
            wa_db=wa_db,
            media_dir=media_dir,
            vcard_path=vcard_path,
            time_offset=time_offset,
            filter_date=args.date,
            filter_date_format=args.date_format,
            source=source,
            package=package
        )

        
        if res["status"] == "success":
            print("\n" + "=" * 50)
            print("  WhatsApp Chat Parsing Successful")
            print("=" * 50)
            print(f"  Plaintext msgstore.db used  : {res['msgstore_db']}")
            print(f"  Contact wa.db database used : {res['wa_db'] or 'None'}")
            print(f"  WhatsApp Media folder used  : {res['media_dir'] or 'None'}")
            print(f"  Output HTML report directory: {res['html_output_dir']}")
            print(f"  Output JSON results path    : {res['json_output_path']}")
            print(f"  Total generated files count : {res['generated_file_count']}")
            print("=" * 50 + "\n")
            sys.exit(0)
        else:
            err = res.get("stderr", "Parsing failed.")
            print(f"\n[ERROR] WhatsApp Chat Export Failed: {err}\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] WhatsApp Chat Export Failed: {str(e)}\n")
        sys.exit(1)




def cmd_whatsapp_unified(args: argparse.Namespace) -> None:
    """Run the complete unified WhatsApp pipeline: key capture -> decrypt -> parse."""
    print_banner()
    print("[*] Initiating unified WhatsApp pipeline: key capture -> decrypt -> parse")
    print("Key will be used in memory and will not be printed.")

    from erakshak.part_b.whatsapp_pipeline import run_whatsapp_unified_pipeline

    try:
        res = run_whatsapp_unified_pipeline(
            case_id=args.case,
            exhibit_id=args.exhibit,
            encrypted_backup_path=Path(args.backup),
            output_root=Path(args.output),
            adb_path=args.adb_path,
            serial=args.serial if args.serial != "auto" else None,
            hex_key_manual=args.hex_key,
            time_offset=args.time_offset,
            filter_date=args.date,
            filter_date_format=args.date_format
        )

        if res["status"] == "success":
            dec = res["decryption"]
            parse = res["parsing"]
            print("\n" + "=" * 50)
            print("  Unified WhatsApp Pipeline Successful")
            print("=" * 50)
            print(f"  Decrypted msgstore.db path  : {dec['decrypted_db_path']}")
            print(f"  SHA-256 of decrypted DB     : {dec['decrypted_sha256']}")
            print(f"  Output HTML report directory: {parse['html_output_dir']}")
            print(f"  Output JSON results path    : {parse['json_output_path']}")
            print(f"  Total generated files count : {parse['generated_file_count']}")
            print("=" * 50 + "\n")
            sys.exit(0)
        else:
            err = res.get("error", "Pipeline execution failed.")
            print(f"\n[ERROR] WhatsApp Unified Pipeline Failed: {err}\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] WhatsApp Unified Pipeline Failed: {str(e)}\n")
        sys.exit(1)


def cmd_whatsapp_root_unified(args: argparse.Namespace) -> None:
    """Unified WhatsApp root pipeline: acquire private data and parse chats."""
    print_banner()
    print("[*] Initiating Unified WhatsApp Root Acquisition & Parsing Pipeline...")

    from erakshak.part_b.whatsapp_root_pipeline import run_whatsapp_root_adb_pipeline
    from erakshak.part_b.whatsapp_parse_pipeline import parse_decrypted_whatsapp

    output_root = Path(args.output).resolve()
    serial = _resolve_serial(args.serial, adb_path=args.adb_path)
    max_cache = int(args.max_cache_bytes) if args.max_cache_bytes is not None else None

    # 1. Run acquisition
    acq_res = run_whatsapp_root_adb_pipeline(
        case_id=args.case,
        exhibit_id=args.exhibit,
        serial=serial,
        output_root=output_root,
        package_name=args.package,
        include_cache=args.include_cache,
        include_files=args.include_files,
        include_shared_media=args.include_shared_media,
        max_cache_bytes=max_cache,
        timeout_seconds=args.timeout_seconds,
    )

    if acq_res["status"] not in ("success", "partial"):
        errs = ", ".join(acq_res.get("errors", ["Acquisition failed"]))
        print(f"\n[ERROR] Unified WhatsApp Root Acquisition Failed: {errs}\n")
        sys.exit(1)

    print("\n[*] Acquisition completed successfully. Initiating Chat Parsing...\n")

    # 2. Run parser
    try:
        parse_res = parse_decrypted_whatsapp(
            case_id=args.case,
            exhibit_id=args.exhibit,
            output_root=output_root,
            source="rooted",
            package=args.package
        )

        if parse_res["status"] == "success":
            print("\n" + "=" * 50)
            print("  Unified WhatsApp Root Pipeline Successful")
            print("=" * 50)
            print(f"  Plaintext msgstore.db used  : {parse_res['msgstore_db']}")
            print(f"  Contact wa.db database used : {parse_res['wa_db'] or 'None'}")
            print(f"  WhatsApp Media folder used  : {parse_res['media_dir'] or 'None'}")
            print(f"  Output HTML report directory: {parse_res['html_output_dir']}")
            print(f"  Output JSON results path    : {parse_res['json_output_path']}")
            print(f"  Total generated files count : {parse_res['generated_file_count']}")
            print("=" * 50 + "\n")
            sys.exit(0)
        else:
            err = parse_res.get("stderr", "Parsing failed.")
            print(f"\n[ERROR] Unified WhatsApp Root Chat Export Failed: {err}\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unified WhatsApp Root Chat Export Failed: {str(e)}\n")
        sys.exit(1)


def cmd_carve_whatsapp(args: argparse.Namespace) -> None:
    """Carve deleted messages from WhatsApp database and WAL sidecars."""
    print_banner()
    print("[*] Initiating WhatsApp Forensic Carving Pipeline...")

    from erakshak.part_b.whatsapp_carver import run_whatsapp_carver

    output_root = Path(args.output).resolve()
    serial = None
    if args.serial and args.serial.lower() != "none":
        try:
            serial = _resolve_serial(args.serial, adb_path=args.adb_path)
            print(f"[AUTO] Selected device: {serial}")
        except Exception:
            print("[INFO] No active ADB device resolved. Running carving offline on staged database.")

    try:
        res = run_whatsapp_carver(
            case_id=args.case,
            exhibit_id=args.exhibit,
            output_root=output_root,
            serial=serial,
            package_name=args.package,
            adb_path=args.adb_path
        )

        if res["status"] == "success":
            print("\n" + "=" * 50)
            print("  WhatsApp Forensic Carving Successful")
            print("=" * 50)
            print(f"  FTS index residues found    : {res['fts_residues_count']}")
            print(f"  Slack candidates carved     : {res['slack_candidates_count']}")
            print(f"  JSON report path            : {res['json_report']}")
            print(f"  Text report path            : {res['txt_report']}")
            print("=" * 50 + "\n")
            sys.exit(0)
        else:
            err = res.get("error", "Carving failed.")
            print(f"\n[ERROR] WhatsApp Carving Failed: {err}\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] WhatsApp Carving Failed: {str(e)}\n")
        sys.exit(1)


def cmd_acquire_whatsapp_root(args: argparse.Namespace) -> None:
    """Acquire WhatsApp data from a rooted Android device over ADB."""
    print_banner()
    print("[*] Initiating WhatsApp Root Acquisition Pipeline...")

    from erakshak.part_b.whatsapp_root_pipeline import run_whatsapp_root_adb_pipeline

    output_root = Path(args.output).resolve()
    serial = _resolve_serial(args.serial, adb_path=args.adb_path)
    max_cache = int(args.max_cache_bytes) if args.max_cache_bytes is not None else None

    try:
        res = run_whatsapp_root_adb_pipeline(
            case_id=args.case,
            exhibit_id=args.exhibit,
            serial=serial,
            output_root=output_root,
            package_name=args.package,
            include_cache=args.include_cache,
            include_files=args.include_files,
            include_shared_media=args.include_shared_media,
            max_cache_bytes=max_cache,
            timeout_seconds=args.timeout_seconds,
        )

        if res["status"] == "success" or res["status"] == "partial":
            summary = res.get("summary", {})
            print("\n" + "=" * 50)
            print("  WhatsApp Root Acquisition Successful" if res["status"] == "success" else "  WhatsApp Root Acquisition Completed with Warnings")
            print("=" * 50)
            print(f"  Package Name        : {summary.get('package_name')}")
            print(f"  Databases Found     : {', '.join(summary.get('databases_found', []))}")
            print(f"  Sidecars Found      : {', '.join(summary.get('sidecars_found', []))}")
            print(f"  Key File Found      : {'Yes' if summary.get('key_file_found') else 'No'}")
            print(f"  Media Found         : {'Yes' if summary.get('media_found') else 'No'}")
            print(f"  Parser-Ready Path   : {summary.get('parser_ready_path')}")
            print("=" * 50 + "\n")
            
            if res["warnings"]:
                print("  --- Warnings ---")
                for w in res["warnings"]:
                    print(f"    [WARN] {w}")
            sys.exit(0)
        else:
            err = res.get("error", "Acquisition failed.")
            print(f"\n[ERROR] WhatsApp Root Acquisition Failed: {err}\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] WhatsApp Root Acquisition Failed: {str(e)}\n")
        sys.exit(1)


def cmd_import_whatsapp_root(args: argparse.Namespace) -> None:
    """Import WhatsApp data from an acquired filesystem dump/folder."""
    print_banner()
    print("[*] Initiating WhatsApp Imported Filesystem Pipeline...")

    from erakshak.part_b.whatsapp_root_pipeline import run_whatsapp_root_import_pipeline

    import_root = Path(args.import_root).resolve()
    if not import_root.is_dir():
        print(f"\n[ERROR] Specified import root is not a directory: {import_root}\n")
        sys.exit(1)

    output_root = Path(args.output).resolve()

    try:
        res = run_whatsapp_root_import_pipeline(
            case_id=args.case,
            exhibit_id=args.exhibit,
            import_root=import_root,
            output_root=output_root,
            package_name=args.package,
        )

        if res["status"] == "success" or res["status"] == "partial":
            summary = res.get("summary", {})
            print("\n" + "=" * 50)
            print("  WhatsApp Import Successful" if res["status"] == "success" else "  WhatsApp Import Completed with Warnings")
            print("=" * 50)
            print(f"  Package Name        : {summary.get('package_name')}")
            print(f"  Databases Found     : {', '.join(summary.get('databases_found', []))}")
            print(f"  Sidecars Found      : {', '.join(summary.get('sidecars_found', []))}")
            print(f"  Key File Found      : {'Yes' if summary.get('key_file_found') else 'No'}")
            print(f"  Media Found         : {'Yes' if summary.get('media_found') else 'No'}")
            print(f"  Parser-Ready Path   : {summary.get('parser_ready_path')}")
            print("=" * 50 + "\n")

            if res["warnings"]:
                print("  --- Warnings ---")
                for w in res["warnings"]:
                    print(f"    [WARN] {w}")
            sys.exit(0)
        else:
            err = res.get("error", "Import failed.")
            print(f"\n[ERROR] WhatsApp Import Failed: {err}\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] WhatsApp Import Failed: {str(e)}\n")
        sys.exit(1)




# ═════════════════════════════════════════════════════════════════════
# Argument parser
# ═════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="erakshak",
        description=f"{TOOL_NAME} v{TOOL_VERSION} — Android Rapid Evidence Triage & Forensic Preview Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── preflight ─────────────────────────────────────────────────────
    sp_pf = subparsers.add_parser("preflight", help="Run pre-flight device checks")
    sp_pf.add_argument("--case", required=True, help="Case identifier (e.g. CASE001)")
    sp_pf.add_argument("--exhibit", required=True, help="Exhibit identifier (e.g. EX001)")
    sp_pf.add_argument("--serial", default="auto", help="ADB device serial or 'auto' (default: auto)")
    sp_pf.add_argument("--output", default="cases", help="Output root directory (default: cases)")
    sp_pf.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_pf.set_defaults(func=cmd_preflight)

    # ── acquire-part-a ────────────────────────────────────────────────
    sp_acq = subparsers.add_parser("acquire-part-a", help="Full Phase-1 Part-A acquisition")
    sp_acq.add_argument("--case", required=True, help="Case identifier")
    sp_acq.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_acq.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_acq.add_argument("--output", default="cases", help="Output root directory")
    sp_acq.add_argument("--adb-path", default="adb", help="Path to ADB binary")
    sp_acq.add_argument("--media-days", type=int, default=None,
                        help="Number of days of media to consider (default: module default)")
    sp_acq.add_argument("--media-max-bytes", type=int, default=None,
                        help="Max total bytes of media to pull (default: module default)")
    sp_acq.add_argument("--pull-media", type=lambda v: v.lower() in ("true", "1", "yes"),
                        default=None,
                        help="Whether to pull media files (true/false, default: module default)")
    sp_acq.add_argument("--collector-export-folder", default=None,
                        help="Path to an Android collector export folder to import")
    sp_acq.set_defaults(func=cmd_acquire_part_a)

    # ── verify ────────────────────────────────────────────────────────
    sp_ver = subparsers.add_parser("verify", help="Verify SHA-256 integrity of a case folder")
    sp_ver.add_argument("--case-folder", required=True,
                        help="Path to the case/exhibit folder (e.g. cases/CASE001/EX001)")
    sp_ver.set_defaults(func=cmd_verify)
    
    # ── telegram-acquire ──────────────────────────────────────────────
    sp_tg = subparsers.add_parser("telegram-acquire", help="Run Telegram MVP acquisition and parsing")
    sp_tg.add_argument("--case", required=True, help="Case identifier")
    sp_tg.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_tg.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_tg.add_argument("--output", default="cases", help="Output root directory")
    sp_tg.add_argument("--adb-path", default="adb", help="Path to ADB binary")
    sp_tg.set_defaults(func=cmd_telegram_acquire)

    # ── signal-acquire ────────────────────────────────────────────────
    sp_sig = subparsers.add_parser("signal-acquire", help="Run Signal Android MVP acquisition and parsing")
    sp_sig.add_argument("--case", required=True, help="Case identifier")
    sp_sig.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_sig.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_sig.add_argument("--output", default="cases", help="Output root directory")
    sp_sig.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_sig.add_argument("--signal-db-key", default=None, help="Optional Signal SQLCipher DB key (prefer --signal-db-key-file)")
    sp_sig.add_argument("--signal-db-key-file", default=None, help="Path to a file containing the Signal SQLCipher DB key")
    sp_sig.add_argument("--signal-auto-key", action="store_true", help="Root-only: extract Signal DB key in memory before parsing")
    sp_sig.set_defaults(func=cmd_signal_acquire)

    # ── whatsapp-auto-decrypt ─────────────────────────────────────────
    sp_wa_auto = subparsers.add_parser("whatsapp-auto-decrypt", help="Automated key capture and decrypt WhatsApp backup")
    sp_wa_auto.add_argument("--case", required=True, help="Case identifier")
    sp_wa_auto.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_auto.add_argument("--backup", required=True, help="Path to encrypted WhatsApp backup file")
    sp_wa_auto.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_auto.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_auto.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_wa_auto.set_defaults(func=cmd_whatsapp_auto_decrypt)

    # ── whatsapp-decrypt ──────────────────────────────────────────────
    sp_wa_dec = subparsers.add_parser("whatsapp-decrypt", help="Decrypt WhatsApp backup using manual key")
    sp_wa_dec.add_argument("--case", required=True, help="Case identifier")
    sp_wa_dec.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_dec.add_argument("--backup", required=True, help="Path to encrypted WhatsApp backup file")
    sp_wa_dec.add_argument("--hex-key", required=True, help="64-character WhatsApp backup encryption key")
    sp_wa_dec.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_dec.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_dec.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_wa_dec.set_defaults(func=cmd_whatsapp_decrypt)

    # ── parse-whatsapp ────────────────────────────────────────────────
    sp_wa_parse = subparsers.add_parser("parse-whatsapp", help="Parse decrypted WhatsApp database with Whatsapp-Chat-Exporter")
    sp_wa_parse.add_argument("--case", required=True, help="Case identifier")
    sp_wa_parse.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_parse.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_parse.add_argument("--input", default=None, help="Path to decrypted folder containing msgstore.db")
    sp_wa_parse.add_argument("--wa-db", default=None, help="Path to wa.db contacts database")
    sp_wa_parse.add_argument("--media", default=None, help="Path to WhatsApp media folder")
    sp_wa_parse.add_argument("--vcard", default=None, help="Path to contacts.vcf file")
    sp_wa_parse.add_argument("--time-offset", type=int, default=None, help="Time offset in hours")
    sp_wa_parse.add_argument("--date", default=None, help="The date filter (e.g. '> YYYY-MM-DD' or 'YYYY-MM-DD - YYYY-MM-DD')")
    sp_wa_parse.add_argument("--date-format", default="%Y-%m-%d", help="Format for the date filter (default: %%Y-%%m-%%d)")
    sp_wa_parse.add_argument("--source", choices=["decrypted", "rooted"], default="decrypted", help="Acquisition source type (default: decrypted)")
    sp_wa_parse.add_argument("--package", choices=["com.whatsapp", "com.whatsapp.w4b"], default="com.whatsapp", help="WhatsApp package variant (default: com.whatsapp)")
    sp_wa_parse.set_defaults(func=cmd_parse_whatsapp)

    # ── whatsapp-unified ──────────────────────────────────────────────
    sp_wa_un = subparsers.add_parser("whatsapp-unified", help="Unified WhatsApp pipeline: UI key capture, decrypt backup, and parse chats")
    sp_wa_un.add_argument("--case", required=True, help="Case identifier")
    sp_wa_un.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_un.add_argument("--backup", default="/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/", help="Remote Android path or local file of encrypted backup")
    sp_wa_un.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_un.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_un.add_argument("--adb-path", default="adb", help="Path to ADB binary")
    sp_wa_un.add_argument("--hex-key", default=None, help="Optionally provide 64-character hex key manually to bypass UI automation")
    sp_wa_un.add_argument("--time-offset", type=int, default=None, help="Time offset in hours")
    sp_wa_un.add_argument("--date", default=None, help="The date filter (e.g. '> YYYY-MM-DD' or 'YYYY-MM-DD - YYYY-MM-DD')")
    sp_wa_un.add_argument("--date-format", default="%Y-%m-%d", help="Format for the date filter (default: %%Y-%%m-%%d)")
    sp_wa_un.set_defaults(func=cmd_whatsapp_unified)

    # ── acquire-whatsapp-root ─────────────────────────────────────────
    sp_wa_root = subparsers.add_parser("acquire-whatsapp-root", help="Acquire WhatsApp from a rooted Android device over ADB")
    sp_wa_root.add_argument("--case", required=True, help="Case identifier")
    sp_wa_root.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_root.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_root.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_root.add_argument("--package", choices=["com.whatsapp", "com.whatsapp.w4b"], default="com.whatsapp", help="WhatsApp package variant (default: com.whatsapp)")
    
    # Boolean flags
    sp_wa_root.add_argument("--include-cache", action="store_true", dest="include_cache", default=True, help="Include cache folder (default: true)")
    sp_wa_root.add_argument("--no-include-cache", action="store_false", dest="include_cache", help="Exclude cache folder")
    
    sp_wa_root.add_argument("--include-files", action="store_true", dest="include_files", default=True, help="Include files folder (default: true)")
    sp_wa_root.add_argument("--no-include-files", action="store_false", dest="include_files", help="Exclude files folder")
    
    sp_wa_root.add_argument("--include-shared-media", action="store_true", dest="include_shared_media", default=True, help="Include shared media folder (default: true)")
    sp_wa_root.add_argument("--no-include-shared-media", action="store_false", dest="include_shared_media", help="Exclude shared media folder")
    
    sp_wa_root.add_argument("--max-cache-bytes", type=int, default=None, help="Maximum cache bytes allowed")
    sp_wa_root.add_argument("--timeout-seconds", type=int, default=600, help="Command timeout in seconds (default: 600)")
    sp_wa_root.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_wa_root.set_defaults(func=cmd_acquire_whatsapp_root)

    # ── import-whatsapp-root ──────────────────────────────────────────
    sp_wa_import = subparsers.add_parser("import-whatsapp-root", help="Import WhatsApp data from a prior filesystem dump/folder")
    sp_wa_import.add_argument("--case", required=True, help="Case identifier")
    sp_wa_import.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_import.add_argument("--import-root", required=True, help="Path to imported filesystem dump root")
    sp_wa_import.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_import.add_argument("--package", choices=["com.whatsapp", "com.whatsapp.w4b"], default="com.whatsapp", help="WhatsApp package variant (default: com.whatsapp)")
    sp_wa_import.set_defaults(func=cmd_import_whatsapp_root)

    # ── whatsapp-root-unified ─────────────────────────────────────────
    sp_wa_root_un = subparsers.add_parser("whatsapp-root-unified", help="Unified WhatsApp root pipeline: acquire private data and parse chats")
    sp_wa_root_un.add_argument("--case", required=True, help="Case identifier")
    sp_wa_root_un.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_root_un.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_root_un.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_root_un.add_argument("--package", choices=["com.whatsapp", "com.whatsapp.w4b"], default="com.whatsapp", help="WhatsApp package variant (default: com.whatsapp)")
    
    # Boolean flags
    sp_wa_root_un.add_argument("--include-cache", action="store_true", dest="include_cache", default=True, help="Include cache folder (default: true)")
    sp_wa_root_un.add_argument("--no-include-cache", action="store_false", dest="include_cache", help="Exclude cache folder")
    
    sp_wa_root_un.add_argument("--include-files", action="store_true", dest="include_files", default=True, help="Include files folder (default: true)")
    sp_wa_root_un.add_argument("--no-include-files", action="store_false", dest="include_files", help="Exclude files folder")
    
    sp_wa_root_un.add_argument("--include-shared-media", action="store_true", dest="include_shared_media", default=True, help="Include shared media folder (default: true)")
    sp_wa_root_un.add_argument("--no-include-shared-media", action="store_false", dest="include_shared_media", help="Exclude shared media folder")
    
    sp_wa_root_un.add_argument("--max-cache-bytes", type=int, default=None, help="Maximum cache bytes allowed")
    sp_wa_root_un.add_argument("--timeout-seconds", type=int, default=600, help="Command timeout in seconds (default: 600)")
    sp_wa_root_un.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_wa_root_un.set_defaults(func=cmd_whatsapp_root_unified)

    # ── carve-whatsapp ────────────────────────────────────────────────
    sp_wa_carve = subparsers.add_parser("carve-whatsapp", help="Carve deleted WhatsApp messages from database slack space and FTS index residues")
    sp_wa_carve.add_argument("--case", required=True, help="Case identifier")
    sp_wa_carve.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_carve.add_argument("--serial", default="auto", help="ADB device serial, 'auto', or 'none'")
    sp_wa_carve.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_carve.add_argument("--package", choices=["com.whatsapp", "com.whatsapp.w4b"], default="com.whatsapp", help="WhatsApp package variant (default: com.whatsapp)")
    sp_wa_carve.add_argument("--adb-path", default="adb", help="Path to ADB binary (default: adb)")
    sp_wa_carve.set_defaults(func=cmd_carve_whatsapp)

    return parser


# ═════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> None:
    """Main entry point for the E-RAKSHAK CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        print_banner()
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
