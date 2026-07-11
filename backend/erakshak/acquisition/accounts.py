"""Acquire registered accounts from the Android device.

Runs ``adb shell dumpsys account``, parses the output to extract account
entries (name + type), categorises them by provider, and pulls out any
email addresses that can serve as investigative leads.

Output artefacts
----------------
- ``raw/system/dumpsys_account.txt``  – verbatim dumpsys output
- ``derived/accounts.jsonl``          – one JSON object per account
- ``derived/account_email_leads.jsonl``– one JSON object per unique e-mail
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+", re.ASCII
)

_CATEGORY_HINTS: list[tuple[str, list[str]]] = [
    ("google",    ["google", "com.google"]),
    ("samsung",   ["samsung", "com.samsung", "com.sec"]),
    ("microsoft", ["microsoft", "com.microsoft"]),
    ("xiaomi",    ["xiaomi", "com.xiaomi", "com.miui"]),
    ("huawei",    ["huawei", "com.huawei"]),
    ("oppo",      ["oppo", "com.oppo", "com.coloros"]),
    ("vivo",      ["vivo", "com.vivo"]),
    ("oneplus",   ["oneplus", "com.oneplus"]),
    ("facebook",  ["facebook", "com.facebook"]),
    ("whatsapp",  ["whatsapp", "com.whatsapp"]),
    ("telegram",  ["telegram", "org.telegram"]),
]


def _categorise(account_type: str) -> str:
    """Return a human-readable category for *account_type*."""
    lower = account_type.lower()
    for category, hints in _CATEGORY_HINTS:
        for hint in hints:
            if hint in lower:
                return category
    return "other"


def _extract_emails_from_text(text: str) -> list[str]:
    """Pull unique e-mail addresses from free-form text."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _EMAIL_RE.finditer(text):
        addr = match.group(0).lower()
        if addr not in seen:
            seen.add(addr)
            result.append(addr)
    return result


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def acquire_accounts(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
) -> dict:
    """Collect registered accounts.

    Runs ``adb shell dumpsys account``, extracts account entries and
    e-mail leads, then writes structured JSONL output.

    Parameters
    ----------
    adb : ADBClient
        Connected ADB wrapper.
    case_folder : CaseFolder
        Open case folder with pre-created sub-directories.
    manifest : ManifestWriter
        Manifest writer for chain-of-custody records.
    audit : AuditLogger
        Audit logger for forensic audit trail.

    Returns
    -------
    dict
        Summary with keys ``status``, ``account_count``,
        ``email_count``, ``warnings``.
    """
    from erakshak.adb.parsers import parse_dumpsys_account, extract_emails
    from erakshak.config.defaults import (
        DUMPSYS_TIMEOUT,
        STATUS_ACQUIRED,
        STATUS_FAILED,
        STATUS_COMMAND_UNAVAILABLE,
    )

    results: dict = {
        "status": STATUS_ACQUIRED,
        "account_count": 0,
        "email_count": 0,
        "warnings": [],
    }
    started_at = datetime.now(timezone.utc).isoformat()

    # ---- run dumpsys account ------------------------------------------------
    acct_result = adb.shell(
        ["dumpsys", "account"],
        timeout=DUMPSYS_TIMEOUT,
        audit_action="dumpsys_account",
    )

    raw_path: Path = case_folder.raw_system_dir / "dumpsys_account.txt"

    if acct_result.return_code != 0 or acct_result.timed_out:
        reason = (
            "timed_out"
            if acct_result.timed_out
            else f"rc={acct_result.return_code}"
        )
        manifest.add_status_record(
            "accounts", "adb_command", "dumpsys account",
            STATUS_FAILED, reason,
        )
        results["status"] = STATUS_FAILED
        results["warnings"].append(f"dumpsys account failed: {reason}")
        audit.log(
            action="accounts_failed",
            command_category="accounts",
            result="failed",
            warning=reason,
        )
        return results

    # ---- save raw output ----------------------------------------------------
    raw_path.write_text(acct_result.stdout, encoding="utf-8")
    manifest.add_file(
        "accounts_raw", "adb_command", "dumpsys account",
        raw_path, started_at=started_at,
    )

    text: str = acct_result.stdout

    # ---- check for redacted / empty output ----------------------------------
    if len(text.strip()) < 20 or "Permission Denial" in text:
        manifest.add_status_record(
            "accounts_parsed", "adb_command", "dumpsys account",
            "not_accessible", "output_redacted",
        )
        results["status"] = "not_accessible"
        results["warnings"].append("Account data appears redacted")
        return results

    # ---- parse accounts -----------------------------------------------------
    parsed: dict = parse_dumpsys_account(text)
    accounts: list[dict] = parsed.get("accounts", [])
    emails_from_parser: list[str] = parsed.get("emails", [])

    # Also sweep the raw text for any e-mails the parser might have missed.
    emails_from_text: list[str] = _extract_emails_from_text(text)
    # Merge, preserving order, without duplicates.
    seen_emails: set[str] = set()
    all_emails: list[str] = []
    for addr in emails_from_parser + emails_from_text:
        normalised = addr.strip().lower()
        if normalised and normalised not in seen_emails:
            seen_emails.add(normalised)
            all_emails.append(normalised)

    # ---- categorise accounts ------------------------------------------------
    categorised: list[dict] = []
    for acct in accounts:
        acct_name = acct.get("name", "")
        acct_type = acct.get("type", "")
        categorised.append({
            "name": acct_name,
            "type": acct_type,
            "category": _categorise(acct_type),
        })

    # ---- write derived/accounts.jsonl ---------------------------------------
    accounts_path: Path = case_folder.derived_dir / "accounts.jsonl"
    with open(accounts_path, "w", encoding="utf-8") as fh:
        for acct in categorised:
            fh.write(json.dumps(acct, ensure_ascii=False) + "\n")
    manifest.add_file("accounts", "parsed", "dumpsys account", accounts_path)

    # ---- write derived/account_email_leads.jsonl ----------------------------
    email_leads_path: Path = case_folder.derived_dir / "account_email_leads.jsonl"
    with open(email_leads_path, "w", encoding="utf-8") as fh:
        for email in all_emails:
            fh.write(
                json.dumps(
                    {"email": email, "source": "dumpsys_account"},
                    ensure_ascii=False,
                )
                + "\n"
            )
    manifest.add_file(
        "account_email_leads", "parsed", "dumpsys account", email_leads_path,
    )

    # ---- populate results ---------------------------------------------------
    results["account_count"] = len(categorised)
    results["email_count"] = len(all_emails)

    audit.log(
        action="accounts_acquired",
        command_category="accounts",
        result=STATUS_ACQUIRED,
        output_path=str(accounts_path),
    )

    return results
