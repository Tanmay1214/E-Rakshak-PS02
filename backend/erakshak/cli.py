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
            filter_date_format=args.date_format
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

    # ── whatsapp-auto-decrypt ─────────────────────────────────────────
    sp_wa_auto = subparsers.add_parser("whatsapp-auto-decrypt", help="Automated key capture and decrypt WhatsApp backup")
    sp_wa_auto.add_argument("--case", required=True, help="Case identifier")
    sp_wa_auto.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_auto.add_argument("--backup", required=True, help="Path to encrypted WhatsApp backup file")
    sp_wa_auto.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_auto.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_auto.add_argument("--adb-path", default="adb", help="Path to ADB binary")
    sp_wa_auto.set_defaults(func=cmd_whatsapp_auto_decrypt)

    # ── whatsapp-decrypt ──────────────────────────────────────────────
    sp_wa_dec = subparsers.add_parser("whatsapp-decrypt", help="Decrypt WhatsApp backup using manual key")
    sp_wa_dec.add_argument("--case", required=True, help="Case identifier")
    sp_wa_dec.add_argument("--exhibit", required=True, help="Exhibit identifier")
    sp_wa_dec.add_argument("--backup", required=True, help="Path to encrypted WhatsApp backup file")
    sp_wa_dec.add_argument("--hex-key", required=True, help="64-character WhatsApp backup encryption key")
    sp_wa_dec.add_argument("--output", default="cases", help="Output root directory")
    sp_wa_dec.add_argument("--serial", default="auto", help="ADB device serial or 'auto'")
    sp_wa_dec.add_argument("--adb-path", default="adb", help="Path to ADB binary")
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
    sp_wa_parse.add_argument("--date-format", default="%Y-%m-%d", help="Format for the date filter (default: %Y-%m-%d)")
    sp_wa_parse.set_defaults(func=cmd_parse_whatsapp)


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
