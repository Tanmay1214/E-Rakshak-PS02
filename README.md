# E-RAKSHAK

<p align="center">
  <strong>Android Rapid Evidence Triage &amp; Forensic Preview Tool</strong><br>
  <em>Phase 1 · Part A — ADB-Based Forensic Acquisition</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?logo=python" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Cross-platform"/>
  <img src="https://img.shields.io/badge/ADB-Required-orange?logo=android" alt="ADB Required"/>
  <img src="https://img.shields.io/badge/Access-Non--Root%20ADB-green" alt="Non-Root"/>
  <img src="https://img.shields.io/badge/License-Prototype%20%2F%20Hackathon-red" alt="Hackathon Prototype"/>
</p>

---

## What is E-RAKSHAK?

**E-RAKSHAK** (Rapid Evidence Triage &amp; Forensic Preview) is a Python-based forensic acquisition tool for cybersecurity investigations on Android devices. It performs a **complete, read-only evidence triage** over ADB (Android Debug Bridge), collecting:

- Device hardware and software identity
- Installed applications and their permissions
- Registered accounts and email leads
- Activity timelines and usage history
- System logs (logcat)
- Network state and saved Wi-Fi networks
- Media file inventories (and optional selective pull)

All of this is packaged with a **full chain-of-custody audit trail**, **SHA-256 integrity hashing** of every file, and a **machine-readable JSONL manifest** — without ever modifying a single byte on the target device.

> **Designed for:** Authorized forensic investigations by security professionals, incident responders, and law enforcement personnel operating under proper legal authority.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
  - [Step 1: Preflight Check](#step-1-preflight-check)
  - [Step 2: Full Acquisition](#step-2-full-acquisition)
  - [Step 3: Verify Integrity](#step-3-verify-integrity)
  - [Optional: Pull Media Files](#optional-pull-media-files)
  - [Optional: Import Collector App Exports](#optional-import-collector-app-exports)
  - [Run Unit Tests](#run-unit-tests)
- [Output Folder Structure](#output-folder-structure)
- [Acquisition Modules](#acquisition-modules)
- [Forensic Design Principles](#forensic-design-principles)
- [Limitations & Why](#limitations--why)
- [Future Roadmap](#future-roadmap)
- [Legal & Ethical Notice](#legal--ethical-notice)

---

## Features

| Category | Detail |
|---|---|
| **Device Identity** | Model, manufacturer, serial number, IMEI (if accessible), Android version, build fingerprint, security patch level, kernel version |
| **Software Inventory** | All installed packages (system + third-party) with version codes, APK paths, install/update timestamps, and requested/granted permissions |
| **Account & Email Leads** | Account types and names discoverable via `dumpsys account`; regex email extraction across system output |
| **Activity Timeline** | Recent tasks, app usage stats (`dumpsys usagestats`), battery history (screen on/off, charging, boot events), alarm schedules |
| **System Logs** | Buffered logcat dump (`logcat -d`) with forensically relevant event classification (app launches, crashes, USB events, network changes, boot events) |
| **Network Information** | Wi-Fi SSID/MAC/saved networks, IP interfaces (`ip addr`), routing tables (`ip route`), active connections (`netstat`), connectivity service state, telephony state |
| **Media Inventory** | Full recursive file listing of DCIM, Pictures, Movies, Downloads, WhatsApp/Media, and Android media directories — 35,000+ files indexed in testing |
| **Optional Media Pull** | `adb pull` of media files filtered by last-modified age (e.g. last 7 days) and a configurable total byte cap (default 2 GB) |
| **Collector App Import** | Placeholder pipeline for importing JSONL exports (`calls.jsonl`, `sms.jsonl`, `mms.jsonl`) from a future companion Android app |
| **SHA-256 Integrity** | Every output file is hashed immediately after creation and recorded in both `acquisition_manifest.jsonl` and `sha256sums.txt` |
| **Audit Trail** | Every ADB command logged with UTC timestamp, return code, duration (ms), stdout/stderr byte counts, and command category |
| **Independent Verification** | `verify` CLI subcommand re-hashes all files and reports mismatches or missing files |
| **Structured Failure Records** | Blocked or inaccessible artifacts produce explicit status records (`permission_denied`, `not_accessible`, `command_unavailable`, etc.) — nothing is silently dropped |

---

## Architecture

```
E-RAKSHAK PROJECT/
├── PHASE_1_ACQUISITION_PLAN.md       ← Original acquisition design spec
├── PHASE_1_TECH_STACK.md             ← Technology and tooling decisions
└── backend/                          ← Python acquisition engine
    ├── requirements.txt              ← pytest only (stdlib-only runtime)
    ├── README.md                     ← Backend-specific usage guide
    └── erakshak/
        ├── __init__.py               ← Package init (version: 0.1.0)
        ├── __main__.py               ← python -m erakshak entry point
        ├── cli.py                    ← CLI (preflight / acquire-part-a / verify)
        │
        ├── config/
        │   └── defaults.py           ← All system constants and status codes
        │
        ├── adb/
        │   ├── client.py             ← ADBClient wrapper (subprocess, audit, timeout)
        │   └── parsers.py            ← Pure-function parsers for all ADB output formats
        │
        ├── case/
        │   ├── case_folder.py        ← CaseFolder: directory tree builder
        │   ├── manifest.py           ← ManifestWriter: JSONL manifest + sha256sums.txt
        │   ├── audit.py              ← AuditLogger: streaming audit.jsonl writer
        │   └── hashing.py            ← SHA-256 file hashing and verification
        │
        └── acquisition/
            ├── preflight.py          ← A1: Connection check, battery, clock diff, root detect
            ├── device_info.py        ← A2-A5: Hardware/software identity via getprop + dumpsys
            ├── installed_apps.py     ← A6: pm list packages + dumpsys package (per-app detail)
            ├── accounts.py           ← A7: dumpsys account + email extraction
            ├── timeline.py           ← A8: usagestats, activity recents, batterystats, alarms
            ├── system_logs.py        ← A9: logcat -d (main buffer, forensic event parsing)
            ├── network.py            ← A10: wifi, ip addr, ip route, netstat, connectivity
            ├── media.py              ← A11: Media directory inventory + optional adb pull
            └── collector_import.py   ← A12: Placeholder for companion APK JSONL import
```

### Design Principles

| Principle | How It's Implemented |
|---|---|
| **Read-only by design** | Only query-type ADB commands; no `adb root`, no file modification, no app control |
| **Standard library only** | Zero pip dependencies at runtime — Python 3.12 stdlib is sufficient |
| **Pure parsers** | All ADB output parsers are side-effect-free functions; testable in isolation |
| **Streaming JSONL** | Manifest and audit log written line-by-line; no risk of data loss on interruption |
| **Graceful degradation** | Each acquisition step is fully isolated; one failure never blocks the rest |
| **Structured failure records** | Every inaccessible artifact records its exact reason code instead of being silently skipped |
| **Forensic audit trail** | Every command sent to the device produces a permanent audit record |
| **Type-annotated** | Full `typing` annotations across the codebase |

---

## Requirements

| Requirement | Detail |
|---|---|
| **Python** | 3.12 or later |
| **Android Platform Tools** | `adb` binary accessible on PATH or via `--adb-path` |
| **Android Device** | USB Debugging enabled; host computer authorized on device |
| **USB Cable** | Data-capable (not charge-only) |
| **OS** | Windows 10/11, macOS 12+, or Linux |
| **Disk space** | Varies by case; allow 5-50 GB depending on media pull settings |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Tanmay1214/E-Rakshak-PS02.git
cd "E-Rakshak-PS02/backend"
```

### 2. Install all required dependencies

E-RAKSHAK requires a few third-party Python packages for Phase 1 Part B (decryption and chat parsing/exporting). Install them along with `pytest` (development and testing framework) via `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Set up ADB

**Download Android Platform Tools:**
- Windows: [platform-tools-latest-windows.zip](https://developer.android.com/studio/releases/platform-tools)
- macOS: `brew install --cask android-platform-tools`
- Linux: `sudo apt install adb`

**Enable USB Debugging on the target Android device:**
1. Go to **Settings → About Phone**
2. Tap **Build Number** 7 times to unlock Developer Options
3. Go to **Settings → Developer Options**
4. Enable **USB Debugging**

**Connect and authorize:**
1. Connect the device via USB
2. On the device, tap **Allow** when the "Allow USB debugging?" dialog appears
3. Verify the connection:
   ```bash
   adb devices
   ```
   The device should appear as `<serial>  device` (not `unauthorized` or `offline`).

---

## Usage

> **Note:** All commands are run from inside the `backend/` directory.

```bash
cd "E-Rakshak-PS02/backend"
```

---

### Step 1: Preflight Check

Run a preflight check to verify ADB connectivity, device authorization, battery level, and clock drift before collecting evidence:

```bash
# Linux / macOS
python -m erakshak.cli preflight \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial auto \
    --adb-path ../platform-tools/adb

# Windows
python -m erakshak.cli preflight `
    --case CASE001 `
    --exhibit EXHIBIT001 `
    --serial auto `
    --adb-path ..\platform-tools\adb.exe
```

| Flag | Default | Description |
|---|---|---|
| `--case` | required | Case identifier, e.g. `CASE001` |
| `--exhibit` | required | Exhibit identifier, e.g. `EXHIBIT001` |
| `--serial` | required | Device serial number, or `auto` to auto-detect the only connected device |
| `--adb-path` | `adb` | Path to the ADB binary |
| `--output` | `cases` | Root output directory |

**Output:** `cases/CASE001/EXHIBIT001/acquisition/preflight.json`

---

### Step 2: Full Acquisition

Run the complete Phase 1 Part A acquisition pipeline (12 sequential stages):

```bash
# Linux / macOS
python -m erakshak.cli acquire-part-a \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial auto \
    --output cases \
    --adb-path ../platform-tools/adb

# Windows
python -m erakshak.cli acquire-part-a `
    --case CASE001 `
    --exhibit EXHIBIT001 `
    --serial auto `
    --output cases `
    --adb-path ..\platform-tools\adb.exe
```

**Expected output (live device, Samsung SM-E236B, Android 13):**
```
----------------------------------------------------------------
  E-RAKSHAK  (v0.1.0)
  Android Rapid Evidence Triage & Forensic Preview Tool
----------------------------------------------------------------
[*] Acquisition Part-A - Case: CASE001  Exhibit: EXHIBIT001
[*] Started at 2026-07-12T06:00:47.609447+00:00
[AUTO] Selected device: RZCW21D538L

[1/12] Running preflight...       [OK]
[2/12] Running device_info...     [OK]
[3/12] Running installed_apps...  [OK]
[4/12] Running accounts...        [OK]
[5/12] Running timeline...        [OK]
[6/12] Running system_logs...     [OK]
[7/12] Running network...         [OK]
[8/12] Running media...           [OK]
[9/12] Running call_logs...       [OK]
[10/12] Running sms...            [OK]
[11/12] Running contacts...       [OK]
[12/12] Running collector_import.. [OK]

================================================================
  E-RAKSHAK - ACQUISITION PART-A FINAL SUMMARY
================================================================
  Device model      : SM-E236B
  Android version   : 13
  Security patch    : 2023-11-01
  Installed apps    : 581
  Account/email leads: 28 accounts / 6 emails
  Call logs         : 2000 (source: adb)
  SMS messages      : 2779 (source: adb)
  Contacts          : 465 (source: adb)
  Timeline events   : 12911
  Log events        : 39474
  Network status    : acquired
  Media inventoried : 35622
  Media pulled      : 0
  Elapsed time      : 125.2s
  Overall status    : SUCCESS
================================================================
```
---

### Step 3: Verify Integrity

Re-hash all artifact files and compare against recorded SHA-256 checksums:

```bash
python -m erakshak.cli verify --case-folder cases/CASE001/EXHIBIT001
```

**Expected output:**
```
==================================================
  INTEGRITY VERIFICATION REPORT
==================================================
  Total entries : 38
  Verified OK   : 38
  Missing files : 0
  Mismatched    : 0
==================================================

[SUCCESS] All files verified - integrity intact.
```

Returns exit code `0` if all hashes match, non-zero if any file is missing or tampered with.

---

### Optional: Pull Media Files

Enable selective media file pulling filtered by last-modified date and total byte cap:

```bash
python -m erakshak.cli acquire-part-a \
    --case CASE001 --exhibit EXHIBIT001 --serial auto --output cases \
    --pull-media true \
    --media-days 7 \
    --media-max-bytes 2147483648
```

| Flag | Default | Description |
|---|---|---|
| `--pull-media` | `false` | Enable media pulling (`true` / `false`) |
| `--media-days` | `7` | Only pull files modified within the last N days |
| `--media-max-bytes` | `2147483648` | Max total bytes to pull (default: 2 GB) |

---

### Optional: Import Collector App Exports

```bash
python -m erakshak.cli acquire-part-a \
    --case CASE001 --exhibit EXHIBIT001 --serial auto --output cases \
    --collector-export-folder /path/to/collector/exports
```
Expected files in the export folder: `calls.jsonl`, `sms.jsonl`, `mms.jsonl`, `contacts.jsonl`, `media_index.jsonl`

---

### Step 4: WhatsApp Automation & UI Key Capture (Part B)

To extract the 64-digit WhatsApp encryption key and force a fresh encrypted backup on the device:

```bash
python -m erakshak.cli whatsapp-key \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --output cases \
    --serial auto
```

This runs a visual UI automation sequence on the device, unlocks the End-to-End Encrypted settings screen, copies/scrapes the 64-digit key into memory (never writing it to files/logs), triggers a fresh backup, and monitors progress until it reaches 100%.

---

### Step 5: WhatsApp Backup Decryption (Part B)

Copy the encrypted database backup from the device and decrypt it to a plaintext database using the captured key:

```bash
python -m erakshak.cli whatsapp-decrypt \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --output cases \
    --serial auto
```

- **Staged Encrypted Path**: `cases/CASE001/EXHIBIT001/raw/apps/whatsapp/encrypted/msgstore.db.crypt15`
- **Decrypted Plaintext Path**: `cases/CASE001/EXHIBIT001/processed/apps/whatsapp/decrypted/msgstore.db`

*Note: You can also specify a key manually by appending `--key <64-character-hex-key>` to bypass the UI automation if you already have the key.*

---

### Step 6: WhatsApp Chat Parsing & Export (Part B)

Parse the decrypted plaintext database to generate HTML chat reports and a pretty-printed JSON dump:

```bash
python -m erakshak.cli parse-whatsapp \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --output cases
```

**Key Features:**
- **Dynamic Contact Mapping**: Automatically reads the Part A contacts extraction list (`derived/contacts.jsonl`), converts it into a vCard structure, and maps all WhatsApp chat phone numbers to real contact names.
- **Clean Named Reports**: Renames the output files from `<phone>-<name>.html` to strictly `<name>.html` (e.g. `Darsh-Sharda-LNMIIT.html`) for easier incident responder analysis. Unmapped numbers are left named by their phone number.
- **Pretty-Printed JSON**: Outputs `result.json` in a pretty-printed, indented format for easy viewing.
- **7-Day Default Filter**: Automatically limits chat history previews to the last 7 days to keep reports fast and compact. To export all historical chats, specify a wide filter: `--date "> 2000-01-01"`.

---

### Step 7: Signal Android Chat Extraction (Rooted Device / Emulator)

Signal stores chats inside its private app sandbox at `/data/data/org.thoughtcrime.securesms/`. Normal unrooted ADB cannot read this path. On an already-rooted device or rooted emulator, E-RAKSHAK can pull the Signal database, extract the SQLCipher key in memory, parse the database, and write simplified message JSONL in one command.

```bash
python -m erakshak.cli signal-acquire \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial DEVICE_SERIAL \
    --output cases \
    --signal-auto-key
```

For the rooted test emulator used during development:

```bash
python -m erakshak.cli signal-acquire \
    --case SIGDIR \
    --exhibit ROOTEMU \
    --serial emulator-5554 \
    --output cases \
    --signal-auto-key
```

Message output:

```text
cases/CASE001/EXHIBIT001/derived/apps/signal/org.thoughtcrime.securesms/databases_signal_messages.jsonl
```

Each message row is normalized to:

```json
{"date": "2026-07-23 19:18:53 UTC", "contact_name": "Alice", "received": false, "sent": true, "message": "Hey"}
```

- `sent: true` means the message was sent by the acquired phone.
- `received: true` means the message was received by the acquired phone.
- The raw Signal SQLCipher key is used in memory only and is not written to stdout, audit logs, manifests, or case output.
- `--signal-auto-key` requires existing root access. It temporarily stages a small helper dex in Signal's `code_cache`, runs it as the Signal app user, and removes the helper after extraction.

If you already have the Signal SQLCipher key from an authorized acquisition path, use:

```bash
python -m erakshak.cli signal-acquire \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial DEVICE_SERIAL \
    --output cases \
    --signal-db-key-file /path/to/signal_db_key.txt
```

---

### Run Unit Tests

```bash
cd backend
python -m pytest tests/ -v
```

**Expected:**
```
collected 23 items

tests/test_extensions.py .....                                           [ 21%]
tests/test_hashing.py .....                                              [ 43%]
tests/test_manifest.py ..                                                [ 52%]
tests/test_parsers.py ...........                                        [100%]

23 passed in 0.81s
```

---


## Output Folder Structure

```
cases/
└── CASE001/
    └── EXHIBIT001/
        ├── acquisition/
        │   ├── preflight.json                ← Pre-acquisition state, tool version, warnings
        │   ├── acquisition_manifest.jsonl    ← Master manifest (one JSON line per artifact)
        │   └── audit.jsonl                   ← Full audit log of every ADB command
        │
        ├── raw/
        │   ├── system/                       ← Raw ADB output files
        │   │   ├── getprop.txt               ← Full system property dump
        │   │   ├── cpuinfo.txt
        │   │   ├── proc_version.txt
        │   │   ├── uname.txt
        │   │   ├── dumpsys_package.txt       ← Package manager dump (10+ MB)
        │   │   ├── dumpsys_account.txt
        │   │   ├── dumpsys_activity.txt
        │   │   ├── dumpsys_activity_recents.txt
        │   │   ├── dumpsys_usagestats.txt
        │   │   ├── dumpsys_batterystats.txt
        │   │   ├── dumpsys_alarm.txt
        │   │   ├── dumpsys_notification.txt
        │   │   ├── dumpsys_jobscheduler.txt
        │   │   ├── dumpsys_wifi.txt
        │   │   ├── dumpsys_connectivity.txt
        │   │   ├── dumpsys_telephony.txt
        │   │   ├── dumpsys_bluetooth.txt
        │   │   ├── content_call_log.txt      ← Raw calls content query (if successful)
        │   │   ├── content_sms.txt           ← Raw SMS content query (if successful)
        │   │   ├── content_contacts.txt      ← Raw contacts content query (if successful)
        │   │   ├── logcat.txt                ← Full buffered logcat (40+ MB in testing)
        │   │   ├── ip_addr.txt
        │   │   ├── ip_route.txt
        │   │   ├── netstat.txt
        │   │   ├── packages_all.txt
        │   │   ├── packages_third_party.txt
        │   │   └── packages_system.txt
        │   │
        │   ├── media/                        ← Pulled media files (if --pull-media true)
        │   ├── collector/                    ← Collector APK exports (if --collector-export-folder)
        │   └── apps/
        │       └── whatsapp/
        │           └── encrypted/
        │               └── msgstore.db.crypt15  ← Encrypted WhatsApp backup copied from device
        │
        ├── processed/
        │   └── apps/
        │       └── whatsapp/
        │           └── decrypted/
        │               └── msgstore.db          ← Decrypted plaintext WhatsApp database
        │
        ├── derived/                          ← Parsed/structured JSON/JSONL outputs
        │   ├── device_identity.json
        │   ├── software_summary.json
        │   ├── installed_apps.jsonl          ← Per-app records with permissions
        │   ├── app_permission_summary.json   ← Apps with dangerous permissions flagged
        │   ├── accounts.jsonl
        │   ├── account_email_leads.jsonl
        │   ├── call_logs.jsonl               ← Parsed call logs (ADB or collector source)
        │   ├── sms_messages.jsonl            ← Parsed SMS messages (ADB or collector source)
        │   ├── contacts.jsonl                ← Parsed contacts list (ADB or collector source)
        │   ├── device_timeline_events.jsonl  ← Merged timeline from all sources
        │   ├── app_usage_summary.jsonl
        │   ├── logcat_events.jsonl           ← Classified forensic log events
        │   ├── network_summary.json
        │   ├── network_connections.jsonl
        │   ├── media_index.jsonl             ← Full recursive file inventory
        │   ├── whatsapp_preview_summary.json  ← Summary of WhatsApp chat message counts
        │   └── whatsapp_exporter/
        │       ├── contacts.vcf              ← Dynamically generated vCard file
        │       ├── result.json               ← Pretty-printed JSON dump of all chats
        │       └── html/
        │           ├── contact-name-saved-in-phone.html <-- Clean named HTML chat files
        │           └── phone-number.html
        │
        └── hashes/
            └── sha256sums.txt                ← SHA-256 checksums (coreutils-compatible)
```

> `sha256sums.txt` is compatible with `sha256sum -c sha256sums.txt` on Linux/macOS.

---

## Acquisition Modules

| Stage | Module | Key Commands | Output |
|---|---|---|---|
| **A1 Preflight** | `preflight.py` | `adb version`, `adb devices -l`, `shell date`, `shell dumpsys battery`, `shell su -c id` | `preflight.json` |
| **A2-A5 Device Info** | `device_info.py` | `shell getprop`, `shell cat /proc/cpuinfo`, `shell uname -a` | `device_identity.json`, `software_summary.json` |
| **A6 Installed Apps** | `installed_apps.py` | `shell pm list packages --user 0 -f -U --show-versioncode`, `shell dumpsys package` | `installed_apps.jsonl`, `app_permission_summary.json` |
| **A7 Accounts** | `accounts.py` | `shell dumpsys account` | `accounts.jsonl`, `account_email_leads.jsonl` |
| **A8 Timeline** | `timeline.py` | `shell dumpsys usagestats`, `shell dumpsys activity recents`, `shell dumpsys batterystats`, `shell dumpsys alarm` | `device_timeline_events.jsonl`, `app_usage_summary.jsonl` |
| **A9 System Logs** | `system_logs.py` | `shell logcat -d` | `logcat.txt`, `logcat_events.jsonl` |
| **A10 Network** | `network.py` | `shell ip addr`, `shell ip route`, `shell netstat`, `shell dumpsys wifi`, `shell dumpsys connectivity`, `shell dumpsys telephony.registry` | `network_summary.json`, `network_connections.jsonl` |
| **A11 Media** | `media.py` | `shell ls -la` (6 target dirs), `pull` (if enabled) | `media_index.jsonl`, optional pulled files |
| **A12 Call Logs** | `call_logs.py` | `shell content query --uri content://call_log/calls` | `content_call_log.txt`, `call_logs.jsonl` |
| **A13 SMS Messages** | `sms.py` | `shell content query --uri content://sms` | `content_sms.txt`, `sms_messages.jsonl` |
| **A14 Contacts** | `contacts.py` | `shell content query --uri content://com.android.contacts/contacts` | `content_contacts.txt`, `contacts.jsonl` |
| **A15 Collector** | `collector_import.py` | Host-side only | Copies JSONL files from export folder |

---

## Forensic Design Principles

### Read-Only Posture

The following commands are **never** executed by E-RAKSHAK:

| Forbidden Command | Why Forbidden |
|---|---|
| `adb root` | Re-mounts system as root — device-modifying |
| `adb shell su` | Privilege escalation |
| `adb shell am force-stop` | Terminates running apps |
| `adb shell pm clear` | Clears app data |
| `adb shell settings put` | Modifies system settings |
| `adb shell logcat -c` | Clears log buffers — destroys evidence |
| `adb install` | Installs software on device |
| `adb shell rm` / `mv` / `cp` | File modification or deletion |

> [!CAUTION]
> The only root-related check is `su -c id` to **detect** if root is already available. This does not escalate privileges — it only observes and records.

### Chain of Custody

| File | Format | Content |
|---|---|---|
| `acquisition_manifest.jsonl` | JSONL | One record per artifact: class, source command, SHA-256, size, timestamps, status |
| `audit.jsonl` | JSONL | One record per ADB command: timestamp, return code, duration_ms |
| `sha256sums.txt` | BSD format | `<hash>  <path>` entries, verifiable with `sha256sum -c` |

### Structured Failure Codes

| Code | Meaning |
|---|---|
| `acquired` | Successfully collected |
| `partial` | Partially collected |
| `not_accessible` | Permission denied by OS |
| `not_exposed` | Data not available via ADB shell |
| `command_unavailable` | Command doesn't exist on this device/Android version |
| `permission_denied` | SecurityException returned |
| `unsupported` | Device/OEM does not support this feature |
| `failed` | Unexpected error during acquisition |

---

## Limitations & Why

### Call Logs and SMS Require the Companion App

Android 6.0+ restricts `READ_CALL_LOG` and `READ_SMS` to apps that are the default dialer or SMS handler. The ADB shell does not qualify, so `content://call_log/calls` returns empty or a SecurityException on most Android 9+ devices.

**Solution:** A companion Kotlin/Android Studio app (Phase 1 Collector APK) requests these permissions via the standard dialog, exports data as JSONL to `/sdcard/`, and E-RAKSHAK imports it via `--collector-export-folder`.

### WhatsApp / Telegram / Signal Private Data

Android's sandbox prevents reading another app's private directory without root:

| App | Protected Path |
|---|---|
| WhatsApp | `/data/data/com.whatsapp/databases/msgstore.db` |
| Telegram | `/data/data/org.telegram.messenger/` |
| Signal | `/data/data/org.thoughtcrime.securesms/` |

Part A does collect: installation status (version, permissions, install date) and shared media folders (`/sdcard/WhatsApp/Media/` — world-readable). Part B can collect Signal private databases only from rooted devices, rooted emulators, imported filesystem images, or another authorized source that provides the database and key.

### Other Known Limitations

| Limitation | Impact |
|---|---|
| OEM-restricted `dumpsys` | Some manufacturers suppress certain services |
| Samsung Knox enrollment | Additional permission restrictions on Knox devices |
| SELinux enforcing mode | May block certain shell commands on hardened devices |
| Android 12+ USB auth revocation | USB debugging authorization revoked after inactivity |
| Multi-user/work profiles | `pm list packages` requires `--user 0` to avoid SecurityException |

---

## Future Roadmap

| Phase | Feature | Description |
|---|---|---|
| **Phase 1 Part B** | Root/Image Acquisition | WhatsApp, Telegram, Signal from rooted devices or filesystem images |
| **Collector APK** | Companion Android App | Kotlin app for call logs, SMS, MMS, contacts |
| **Phase 2** | Timeline Merger | Unified forensic timeline across all acquisition sources |
| **Phase 3** | Web Dashboard | FastAPI + React case management UI with evidence browser |
| **Phase 3** | Automated Reporting | PDF/HTML forensic report generation |
| **Packaging** | PyInstaller Bundle | Single-executable for non-technical investigators |
| **Deployment** | Portable USB Mode | Self-contained USB stick deployment |
| **Chain of Custody** | Digital Signatures | Examiner identity and custody transfer records |

---

## WhatsApp Part B Decryption

E-RAKSHAK includes a Part B WhatsApp decryption pipeline that copy-stages encrypted backups and processes them using a captured or manually supplied 64-character hex key.

### Prerequisites

- **wa-crypt-tools**: Requires the `wa-crypt-tools` command-line utility to be installed on the host:
  ```bash
  pip install wa-crypt-tools
  ```
- **Encrypted Backup File**: Requires an encrypted WhatsApp backup database file, typically named `msgstore.db.crypt14` or `msgstore.db.crypt15`.

### Decryption Key Modes

The 64-character backup key can be acquired in two ways:
1. **Automated Key Capture**: Automates standard WhatsApp settings UI navigation on a connected Android phone over ADB using XML layout tree scraping and clipboard fallbacks.
2. **Manual Key Entry**: Explicitly provided by the forensic investigator via CLI argument.

### Security and Forensic Compliance

- **No Passcode/Security Bypass**: The automated capture requires the device to be unlocked and USB debugging authorized.
- **No Stealth/Exploitation**: The navigation sequence runs visibly on screen; no backdoors or privilege escalations are performed.
- **Strict Key Protection**: Raw key secrets are processed in-memory only and are strictly redacted from stdout, stderr, manifest lists, audit events, and CLI output.
- **Verification & Staging**: staging puts encrypted backup in `raw/` and records safe key metadata (`key_sha256`), then decrypts to `processed/apps/whatsapp/decrypted/msgstore.db`. Plaintext msgstore.db can be safely indexed or processed using forensic databases like `chat4n6`.

---

## WhatsApp Parsing with Whatsapp-Chat-Exporter

E-RAKSHAK includes a parsing stage that processes the decrypted plaintext `msgstore.db` using `Whatsapp-Chat-Exporter` (`wtsexporter`) to generate HTML/JSON preview reports as derived forensic evidence.

### Prerequisites

- **whatsapp-chat-exporter**: Requires the package to be installed on the host:
  ```bash
  pip install whatsapp-chat-exporter
  ```
- **Plaintext Database**: The stage expects the decrypted SQLite database file:
  ```
  processed/apps/whatsapp/decrypted/msgstore.db
  ```

### Optional Inputs

- **Contacts Database (`wa.db`)**: Enrich chats with real contact names.
- **WhatsApp Media Folder**: Source directories for voice notes, images, and attachments.
- **vCard Contacts File**: Google contacts export (`contacts.vcf`) to resolve missing names.

### Execution

To run the parsing pipeline:
```bash
python -m erakshak.cli parse-whatsapp --case CASE001 --exhibit EXHIBIT001 --output cases
```

### Advanced Staging & Parameters

- **7-Day Default Filter**: If no date filter is passed, the tool defaults to filtering messages from the last 7 days (`> YYYY-MM-DD`). To override and parse everything, pass an explicit filter:
  ```bash
  python -m erakshak.cli parse-whatsapp --case CASE001 --exhibit EXHIBIT001 --output cases --date "> 2000-01-01"
  ```
- **Containment of Temp Files**: E-RAKSHAK forces the target media directory (`-m`) to `derived/whatsapp_exporter/media_temp/`. This prevents `wtsexporter` from creating a `WhatsApp` folder (containing thumbnails and vcards) in the E-RAKSHAK project root or Python working directory.

---

## WhatsApp Unified Pipeline (Single Command)

E-RAKSHAK provides a unified pipeline subcommand that automates the entire end-to-end flow: **UI automation settings navigation to scrape key -> encrypted database copying/pulling -> decryption -> contacts vCard mapping -> chat parsing & report generation** under a single step.

### Execution

To run the unified pipeline on a connected device:

```bash
python -m erakshak.cli whatsapp-unified --case CASE001 --exhibit EXHIBIT001 --output cases
```

**What it does sequentially:**
1. Runs UI automation to unlock the End-to-End Encrypted settings screen and copy/scrape the 64-digit key into memory.
2. Triggers a fresh backup on the device and monitors its progress until it reaches 100%.
3. Pulls the latest encrypted database backup (`msgstore.db.crypt15`) from the device.
4. Decrypts it using the in-memory key into `processed/apps/whatsapp/decrypted/msgstore.db`.
5. Automatically reads the Part A contacts extraction list (`contacts.jsonl`), converts it to vCard, and maps all numbers to real contact names.
6. Runs `wtsexporter` to generate pretty-printed JSON results and HTML chat preview files named cleanly by their mapped contact names.
7. Deletes duplicate nested media directories inside the HTML reports folder to ensure pristine directory outputs.

*Note: If you already have the 64-character key and want to bypass the UI automation capture, append `--hex-key <64-character-key>` to the command.*

---

## WhatsApp Root & Import Acquisition (Part B)

E-RAKSHAK supports directly acquiring private app databases, key files, preferences, and media from rooted Android devices over ADB or imported forensic filesystem dumps (logical or physical extractions).

### Rooted ADB Acquisition

If the connected device is already rooted (either running `su` or with `adb root` access), you can run:

```bash
python -m erakshak.cli acquire-whatsapp-root --case CASE001 --exhibit EX001 --package com.whatsapp
```

**Parameters:**
- `--case` (required): Case ID.
- `--exhibit` (required): Exhibit ID.
- `--package`: Package variant to acquire: `com.whatsapp` (default) or `com.whatsapp.w4b` (WhatsApp Business).
- `--include-cache` / `--no-include-cache` (default: True): Whether to pull application cache files.
- `--include-files` / `--no-include-files` (default: True): Whether to pull files directory (containing key files).
- `--include-shared-media` / `--no-include-shared-media` (default: True): Whether to acquire `/sdcard` media folders.
- `--max-cache-bytes` (default: None): Limit total cache bytes pulled.
- `--timeout-seconds` (default: 600): Execution timeout.

**What it does sequentially:**
1. Checks root access non-destructively using `id` and `su -c id` (without running `adb root`).
2. Detects if the target package (`com.whatsapp` or `com.whatsapp.w4b`) is installed.
3. Performs a binary-safe `exec-out + tar` extraction (falling back to standard `adb pull` on failure) to copy private folders.
4. Enforces strict member validation to block path traversal (`..`), symlinks, hardlinks, absolute paths, and Windows drive letters.
5. Hashes every file, streams records to `acquisition/acquisition_manifest.jsonl`, and hashes to `hashes/sha256sums.txt`.
6. Safe-logs key files: key contents are never logged; only metadata (hashes) is written to the audit log.
7. Stages parser-ready files under `processed/apps/whatsapp/rooted/<package_name>/` and writes `derived/whatsapp_root_summary.json`.

---

### Imported Filesystem Acquisition

If you have already acquired a logical/physical filesystem dump of the device, you can import it into the case:

```bash
python -m erakshak.cli import-whatsapp-root --case CASE001 --exhibit EX001 --import-root /path/to/extracted/dump --package com.whatsapp
```

**What it does sequentially:**
1. Recursively searches the provided `import-root` folder to find private WhatsApp paths (`/data/data/com.whatsapp`) and external media (`/sdcard/WhatsApp`).
2. Copies all databases, sidecars, files, preferences, and media into the raw exhibit directory.
3. Records all copied files and handles missing files/directories by writing `not_present` manifest records.
4. Stages the parsed files under `processed/apps/whatsapp/rooted/<package_name>/`.

---

### Parsing Root/Import Acquired Data

Once acquired or imported, you can parse the plaintext databases and media directory directly using:

```bash
python -m erakshak.cli parse-whatsapp --case CASE001 --exhibit EX001 --source rooted --package com.whatsapp
```

This parses the staged database (`processed/apps/whatsapp/rooted/com.whatsapp/msgstore.db`) with contact enrichment (`wa.db`) and media mappings, generating derived HTML reports and JSON results under `derived/whatsapp_exporter/`.

---

### WhatsApp Root Unified Command (`whatsapp-root-unified`)

For rapid triage of rooted devices or root emulators, E-RAKSHAK provides a unified command that runs both data acquisition and chat exporting sequentially in a single step:

```bash
python -m erakshak.cli whatsapp-root-unified --case CASE001 --exhibit EX001 --serial DEVICE_SERIAL --package com.whatsapp
```

**What it does sequentially:**
1. Performs a live root detection check.
2. Runs native SQLite `.backup` command on the device to flush active transactions and creates a clean snapshot.
3. Pulls the database (`msgstore_clean.db`), media, and configurations.
4. Performs deleted messages recovery mapping and database injection.
5. Invokes `wtsexporter` to generate fully enriched, named HTML/JSON preview reports immediately.

---

### WhatsApp Forensic Carving & Deleted Message Restoral (`carve-whatsapp`)

To recover deleted chat history from a device's plaintext databases, incident responders can run:

```bash
python -m erakshak.cli carve-whatsapp --case CASE001 --exhibit EX001 --serial DEVICE_SERIAL --output cases
```

**Forensic Capabilities:**
- **FTS Residues Recovery**: Scans SQLite Write-Ahead Logs (`msgstore.db-wal`) and FTS virtual content tables (`message_ftsv2_content`) to scrape deleted text residues.
- **Delete for Everyone & Delete for Me Recovery**: 
  - For *"Delete for Everyone"* messages (which leaves a placeholder type `7` row in the active database), the tool replaces the blank field with the carved text.
  - For *"Delete for Me"* messages (where the active database row has been completely deleted), the tool mathematically decodes the JID token (`c1fts_jid`) back to its original `chat_row_id` and reconstructs an approximate message timestamp by checking consecutive message IDs. It then inserts the recovered row back into the database.
- **Auto-Injection & Date Filtering**: Integrates recovered messages with a custom marker (`🔴 [DELETED MESSAGE RECOVERED]`) directly into the HTML timeline. Uses the specified date filter (default 7 days) to limit updates to the targeted time window, bringing execution speeds down to milliseconds.

---

### Telegram Android Chat Extraction (`telegram-acquire`)

Telegram caches contacts, chats, and channels inside private sandboxed database paths. On an authorized rooted device or emulator, E-RAKSHAK can pull and index this data automatically:

```bash
python -m erakshak.cli telegram-acquire --case CASE001 --exhibit EXHIBIT001 --serial DEVICE_SERIAL --output cases
```

**What it does sequentially:**
1. Stages the primary Telegram database `cache4.db` (along with `-wal`, `-shm`, and `-journal` sidecars) into the raw exhibit directory.
2. Mounts the staging copy using standard SQLite `?mode=ro` URI connections to prevent sidecar pollution and spoliation.
3. Decodes the Telegram TL-serialized binary byte blocks (`data` and `message` blobs) using a customized regex pattern (`[\x20-\x7e]{3,}`) to extract readable chat text.
4. Normalizes and writes structured logs: `cache4_users.jsonl`, `cache4_messages.jsonl`, and `cache4_dialogs.jsonl` under `derived/apps/telegram/`.

---

## Legal & Ethical Notice

> [!IMPORTANT]
> **E-RAKSHAK is a forensic prototype developed for an authorized cybersecurity hackathon. It is designed exclusively for use by authorized personnel on devices for which they have lawful access and proper legal authority.**

- Never modifies data on the target device
- Never escalates privileges or roots a device
- Never installs or persists software on the target device
- Never bypasses lock screens or passcodes
- Never communicates over the network (all data stays local)
- Records every action in a tamper-evident audit log

Rooted Part B commands are explicit exceptions to the Part A read-only model: they require an already-rooted target and may temporarily stage helper files to acquire app-private evidence. These helpers are removed after use and are documented in the command-specific sections above.

**Unauthorized use may violate computer fraud, wiretapping, and privacy laws. Always obtain proper legal authorization before connecting to or acquiring data from any device.**

---

<p align="center">
  <strong>E-RAKSHAK</strong> · Android Rapid Evidence Triage &amp; Forensic Preview Tool<br>
  <em>Phase 1 · Part A — Built for PS-02 Cybersecurity Hackathon</em>
</p>
