# E-RAKSHAK

### Android Rapid Evidence Triage & Forensic Preview Tool

> **Phase 1 · Part A** — ADB-Based Forensic Acquisition

---

## Overview

**E-RAKSHAK** is an authorized forensic triage tool designed for cybersecurity investigations on Android devices. It performs rapid, read-only evidence acquisition over ADB (Android Debug Bridge) to collect device identity, installed applications, user accounts, activity timelines, system logs, network state, and media inventories — all without modifying any data on the target device.

This is a **hackathon prototype** implementing Phase 1 Part A: non-root ADB acquisition. The tool is built as a modular Python package with a CLI interface, JSONL manifests, SHA-256 integrity hashing, and a full audit trail of every command executed against the device.

| Attribute        | Value                                              |
| ---------------- | -------------------------------------------------- |
| **Phase**        | 1 — Core Acquisition                               |
| **Part**         | A — ADB Shell (non-root, no companion app required)|
| **Language**     | Python 3.12+ (standard library only)               |
| **Interface**    | CLI (`python -m erakshak.cli`)                      |
| **Dependencies** | Android Platform Tools (ADB), pytest (dev only)    |
| **License**      | Prototype — hackathon use only                     |

---

## Features

| Category                     | Description                                                                 |
| ---------------------------- | --------------------------------------------------------------------------- |
| **Device Identity**          | Model, manufacturer, serial, IMEI, Android version, build, security patch   |
| **Software Inventory**       | All installed packages with versions, install dates, and requested permissions |
| **Account & Email Leads**    | Registered accounts discoverable via `dumpsys account`                      |
| **Activity Timeline**        | Recent tasks, usage stats, battery stats, and boot/shutdown events          |
| **System Logs**              | Buffered logcat dump, event logs, and kernel messages                       |
| **Network Information**      | Wi-Fi config, IP addresses, active connections, and saved networks          |
| **Media Inventory**          | File listing of DCIM, Pictures, Downloads, Documents with metadata          |
| **Optional Media Pull**      | Selective `adb pull` of media files filtered by age and size cap            |
| **Collector App Import**     | Placeholder import path for a future companion APK's JSONL exports         |
| **SHA-256 Integrity**        | Every acquired artifact is hashed; hashes recorded in manifest and checksum file |
| **JSONL Manifest**           | Machine-readable acquisition manifest (`acquisition_manifest.jsonl`)        |
| **Audit Trail**              | Every ADB command logged with timestamps, return codes, and durations       |
| **Independent Verification** | `verify` subcommand re-hashes all files and compares against recorded sums  |

---

## Requirements

| Requirement                        | Details                                                        |
| ---------------------------------- | -------------------------------------------------------------- |
| **Python**                         | 3.12 or later                                                  |
| **Android Platform Tools**         | ADB binary accessible via `PATH` or explicit path              |
| **Android Device**                 | USB debugging enabled, host computer authorized                 |
| **USB Cable**                      | Data-capable USB cable (not charge-only)                       |
| **Operating System**               | Windows 10/11, macOS, or Linux                                 |

---

## Setup

### 1. Clone or Download

```bash
git clone <repository-url>
cd "E-RAKSHAK PROJECT/backend"
```

### 2. Install Dev Dependencies

```bash
pip install -r requirements.txt   # installs pytest only
```

> [!NOTE]
> E-RAKSHAK uses **only the Python standard library** at runtime. The `requirements.txt` file contains `pytest` for running tests.

### 3. ADB Setup

1. **Download Android Platform Tools**
   - Windows: [platform-tools-latest-windows.zip](https://developer.android.com/studio/releases/platform-tools)
   - macOS: `brew install android-platform-tools`
   - Linux: `sudo apt install adb` or download from the link above

2. **Add to PATH** (or specify the path explicitly via `--adb-path`)

3. **Enable USB Debugging on the Android device**
   - Go to **Settings → About Phone**
   - Tap **Build Number** 7 times to unlock Developer Options
   - Go to **Settings → Developer Options**
   - Enable **USB Debugging**

4. **Connect the device via USB** and authorize the computer when prompted on the device screen

5. **Verify connectivity**
   ```bash
   adb devices
   ```
   The device should appear as `<serial>   device` (not `unauthorized`).

---

## Usage

### Preflight Check

Run a preflight check to verify ADB connectivity, device authorization, and basic device info before acquisition:

```bash
python -m erakshak.cli preflight \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial auto
```

| Flag          | Description                                                        |
| ------------- | ------------------------------------------------------------------ |
| `--case`      | Case identifier (alphanumeric, e.g. `CASE001`)                    |
| `--exhibit`   | Exhibit/evidence identifier (e.g. `EXHIBIT001`)                   |
| `--serial`    | Device serial number, or `auto` to use the only connected device  |

---

### Full Part A Acquisition

Execute the complete non-root acquisition pipeline:

```bash
python -m erakshak.cli acquire-part-a \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial auto \
    --output cases
```

| Flag         | Description                                            |
| ------------ | ------------------------------------------------------ |
| `--output`   | Root output directory (default: `cases`)               |

---

### With Media Pull

Pull recent media files from the device (filtered by age and total size cap):

```bash
python -m erakshak.cli acquire-part-a \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial auto \
    --output cases \
    --pull-media true \
    --media-days 7 \
    --media-max-bytes 2147483648
```

| Flag                  | Description                                           |
| --------------------- | ----------------------------------------------------- |
| `--pull-media`        | Enable media file pulling (`true` / `false`)          |
| `--media-days`        | Only pull files modified within the last N days       |
| `--media-max-bytes`   | Maximum total bytes to pull (default: 2 GB)           |

---

### Import Collector App Export

Import JSONL exports from the companion Android collector app (future):

```bash
python -m erakshak.cli acquire-part-a \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial auto \
    --output cases \
    --collector-export-folder /path/to/exports
```

| Flag                        | Description                                        |
| --------------------------- | -------------------------------------------------- |
| `--collector-export-folder` | Path to the companion app's exported JSONL files   |

---

### Verify Case Integrity

Re-hash all acquired artifacts and compare against recorded SHA-256 sums:

```bash
python -m erakshak.cli verify \
    --case-folder cases/CASE001/EXHIBIT001
```

Returns exit code `0` if all hashes match, non-zero if any file has been modified or is missing.

---

### Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

---

## Output Folder Structure

After a successful acquisition, the output directory is organized as follows:

```
cases/
└── CASE001/
    └── EXHIBIT001/
        └── 20260707T140000Z/                    ← Timestamped acquisition run
            ├── acquisition_manifest.jsonl        ← Master manifest (one JSON object per artifact)
            ├── audit.jsonl                       ← Full audit trail of every ADB command
            ├── sha256sums.txt                    ← BSD-style checksum file for all artifacts
            ├── case_metadata.json                ← Case/exhibit/device summary
            │
            ├── device_identity/
            │   ├── getprop_full.txt              ← Raw `getprop` output
            │   ├── device_identity.json          ← Parsed device identity fields
            │   └── build_info.json               ← Build fingerprint and security patch
            │
            ├── installed_apps/
            │   ├── packages_list.txt             ← Raw `pm list packages -f`
            │   ├── packages_detailed.jsonl        ← Per-package detail (version, installer, permissions)
            │   └── dangerous_permissions.json     ← Apps with dangerous permissions flagged
            │
            ├── accounts/
            │   ├── dumpsys_account.txt            ← Raw `dumpsys account` output
            │   └── accounts.json                  ← Parsed account types and names
            │
            ├── activity_timeline/
            │   ├── dumpsys_usagestats.txt          ← Raw usage stats
            │   ├── dumpsys_batterystats.txt        ← Raw battery stats
            │   ├── recent_tasks.json              ← Parsed recent tasks
            │   └── timeline_events.jsonl           ← Merged timeline events
            │
            ├── logs/
            │   ├── logcat_main.txt                ← Main logcat buffer
            │   ├── logcat_events.txt              ← Events logcat buffer
            │   ├── logcat_kernel.txt              ← Kernel log buffer (if accessible)
            │   └── log_summary.json               ← Log statistics and notable entries
            │
            ├── network/
            │   ├── dumpsys_wifi.txt               ← Raw Wi-Fi dump
            │   ├── ifconfig.txt                   ← Network interfaces
            │   ├── ip_addr.txt                    ← IP address info
            │   ├── netstat.txt                    ← Active connections
            │   └── network_info.json              ← Parsed network summary
            │
            ├── media_inventory/
            │   ├── dcim_listing.jsonl              ← DCIM directory file listing
            │   ├── pictures_listing.jsonl          ← Pictures directory file listing
            │   ├── downloads_listing.jsonl         ← Downloads directory file listing
            │   └── media_summary.json             ← Total counts, sizes, types
            │
            ├── pulled_media/                      ← (Only if --pull-media true)
            │   ├── DCIM/
            │   │   └── ...                        ← Pulled media files preserving structure
            │   ├── Pictures/
            │   └── Downloads/
            │
            └── collector_import/                  ← (Only if --collector-export-folder provided)
                └── ...                            ← Imported JSONL files from companion app
```

> [!TIP]
> The timestamped subdirectory (`20260707T140000Z`) ensures multiple acquisition runs against the same exhibit are preserved independently.

---

## Acquisition Modules

| Module                  | File                            | Description                                                           |
| ----------------------- | ------------------------------- | --------------------------------------------------------------------- |
| **Device Identity**     | `mod_device_identity.py`        | Extracts model, manufacturer, serial, IMEI, Android version, build fingerprint, security patch level, and hardware info via `getprop` and `dumpsys` |
| **Installed Apps**      | `mod_installed_apps.py`         | Enumerates all packages with `pm list packages`, collects per-package details including version, installer, install time, and requested/granted permissions |
| **Accounts**            | `mod_accounts.py`              | Discovers registered accounts (Google, Samsung, WhatsApp, etc.) via `dumpsys account` for investigative leads |
| **Activity Timeline**   | `mod_activity_timeline.py`     | Collects usage statistics, recent tasks, battery history, and boot events to reconstruct a device activity timeline |
| **System Logs**         | `mod_logs.py`                  | Dumps main, events, and kernel logcat buffers for forensic log analysis |
| **Network Info**        | `mod_network.py`               | Gathers Wi-Fi state, IP configuration, active connections, and saved network history |
| **Media Inventory**     | `mod_media_inventory.py`       | Lists files in standard media directories (DCIM, Pictures, Downloads, Documents) with sizes and timestamps |
| **Media Pull**          | `mod_media_pull.py`            | Optionally pulls media files from the device, filtered by modification date and total size cap |
| **Collector Import**    | `mod_collector_import.py`      | Placeholder module for importing JSONL exports from the future companion Android app |
| **ADB Client**          | `adb_client.py`                | Low-level ADB command wrapper with timeout, retry, error handling, and audit logging |
| **Parsers**             | `parsers.py`                   | Pure-function parsers for `getprop`, `dumpsys`, `pm`, and other ADB output formats |
| **Hasher**              | `hasher.py`                    | SHA-256 file hashing and checksum file generation |
| **Manifest Writer**     | `manifest.py`                  | JSONL manifest and audit trail writer |
| **CLI**                 | `cli.py`                       | `argparse`-based CLI with `preflight`, `acquire-part-a`, and `verify` subcommands |

---

## Limitations

### Why Call Logs and SMS Require a Future Collector APK

Modern Android (6.0+) restricts access to call logs and SMS messages to applications that hold the `READ_CALL_LOG` and `READ_SMS` permissions **and** are registered as the default dialer or SMS handler. The ADB shell user does not satisfy these requirements.

- `content query --uri content://call_log/calls` fails or returns empty on most Android 9+ devices
- `content query --uri content://sms` is similarly blocked by runtime permission enforcement
- OEM customizations (Samsung Knox, Xiaomi MIUI, etc.) add further restrictions

**Solution:** A companion Android app (built with Android Studio / Kotlin) will:
1. Request `READ_CALL_LOG` and `READ_SMS` permissions transparently via the standard permission dialog
2. Export the data as JSONL files to external storage
3. E-RAKSHAK imports those files via `--collector-export-folder`

---

### Why WhatsApp / Telegram / Signal Private Data Is Not Part A

Android's application sandbox prevents any process — including the ADB shell — from reading another app's private data directory without root access:

| App       | Private Database Location                        |
| --------- | ------------------------------------------------ |
| WhatsApp  | `/data/data/com.whatsapp/databases/msgstore.db`  |
| Telegram  | `/data/data/org.telegram.messenger/...`          |
| Signal    | `/data/data/org.thoughtcrime.securesms/...`      |

These paths are protected by Linux DAC permissions (`rwx------`) and SELinux MAC policy. Accessing them requires either:
- **Root access** (which E-RAKSHAK never escalates to), or
- **The app's own cooperation** (e.g., WhatsApp's built-in export, or a forensic agent installed on the device)

**What Part A _does_ collect:**
- Whether the app is installed (package name, version, install date)
- Shared media folders (e.g., `/sdcard/WhatsApp/Media/`) — these are world-readable
- Account leads (e.g., phone numbers registered in account manager)

**Part B** handles selected app-private acquisition paths from rooted devices, rooted emulators, imported filesystem images, or other authorized sources.

#### Signal Rooted Acquisition

On an already-rooted device or rooted emulator, Signal chats can be extracted and normalized in one command:

```bash
python -m erakshak.cli signal-acquire \
    --case CASE001 \
    --exhibit EXHIBIT001 \
    --serial DEVICE_SERIAL \
    --output cases \
    --signal-auto-key
```

The message JSONL is written to:

```text
cases/CASE001/EXHIBIT001/derived/apps/signal/org.thoughtcrime.securesms/databases_signal_messages.jsonl
```

Rows contain only the normalized fields `date`, `contact_name`, `received`, `sent`, and `message`. `sent` and `received` are booleans describing whether the acquired phone sent or received the message. The Signal database key is extracted in memory and is not written to the case output.

---

### Other Limitations

| Limitation                       | Impact                                                         |
| -------------------------------- | -------------------------------------------------------------- |
| OEM-restricted `dumpsys`         | Some manufacturers suppress certain `dumpsys` services         |
| Hidden system properties         | Some `getprop` keys are not exposed on all builds              |
| SELinux enforcement              | `enforcing` mode may block certain shell commands              |
| Non-standard ADB behavior       | Some devices (Amazon Fire, some Huawei) have modified ADB      |
| USB debugging auto-revocation    | Android 12+ revokes USB debugging after inactivity             |

> [!IMPORTANT]
> E-RAKSHAK records all blocked, unavailable, or inaccessible artifacts with structured reason codes: `not_accessible`, `not_exposed`, `command_unavailable`, `permission_denied`, `unsupported`, or `failed`. No data is silently dropped.

---

## Forensic Cautions

### Read-Only Intent

E-RAKSHAK is designed with a strict **read-only** posture. Every ADB command used is a query, never a mutation:

| Allowed Commands                              | Purpose                    |
| --------------------------------------------- | -------------------------- |
| `adb shell getprop`                           | Device properties          |
| `adb shell dumpsys <service>`                 | System service state       |
| `adb shell pm list packages` / `pm dump`      | Package information        |
| `adb shell logcat -d`                         | Dump buffered logs         |
| `adb shell ls -la`                            | File listings              |
| `adb shell cat`                               | Read file contents         |
| `adb shell settings get`                      | System settings            |
| `adb shell ip addr` / `ifconfig` / `netstat`  | Network state              |
| `adb pull`                                    | Copy files to host         |

**Never executed:**
- ❌ `adb root` — no privilege escalation
- ❌ `adb shell su` — no root access (detection only)
- ❌ `adb shell am force-stop` — no app termination
- ❌ `adb shell pm clear` — no data clearing
- ❌ `adb shell settings put` — no settings modification
- ❌ `adb shell logcat -c` — no log clearing
- ❌ `adb install` — no app installation
- ❌ `adb shell rm` / `mv` / `cp` — no file modification

> [!CAUTION]
> The `su` binary detection check (`which su`, `ls /system/xbin/su`) only determines whether root access is **already available** on the device. It does **not** escalate privileges, install rooting tools, or exploit any vulnerability.

---

### Integrity

- Every acquired file is hashed with **SHA-256** immediately after creation
- Hashes are recorded in:
  - `acquisition_manifest.jsonl` — per-artifact entry with hash, size, and timestamp
  - `sha256sums.txt` — BSD-style checksum file compatible with `sha256sum -c`
- The `verify` subcommand independently re-hashes all files and compares against recorded values
- Any mismatch or missing file is reported with details

---

### Audit Trail

Every interaction with the target device is logged in `audit.jsonl`:

```json
{
  "timestamp": "2026-07-07T14:01:23.456789+05:30",
  "command": "adb -s SERIAL shell getprop ro.product.model",
  "return_code": 0,
  "duration_ms": 142,
  "stdout_bytes": 24,
  "stderr_bytes": 0
}
```

This provides a complete, tamper-evident record of what was executed, when, and whether it succeeded.

---

### No Bypass or Exploitation

E-RAKSHAK makes the following guarantees:

- ✅ No rooting or root escalation
- ✅ No bootloader unlocking
- ✅ No passcode / lockscreen bypass
- ✅ No stealth app installation
- ✅ No malware-like behavior
- ✅ No persistence mechanisms on the device
- ✅ No covert data exfiltration
- ✅ No network communication (all data stays local)
- ✅ No encryption key extraction or bypass in Part A

Rooted Part B commands are explicit, operator-selected exceptions. For example, `signal-acquire --signal-auto-key` requires existing root access, temporarily stages a helper dex in Signal's app-private `code_cache`, runs it as the Signal app user, and removes it after extracting the database key in memory.

---

## Architecture

```
erakshak/
├── __init__.py                  ← Package init
├── cli.py                       ← CLI entry point (argparse)
├── adb_client.py                ← ADB wrapper (timeout, audit, error handling)
├── parsers.py                   ← Pure-function output parsers
├── hasher.py                    ← SHA-256 hashing utilities
├── manifest.py                  ← JSONL manifest and audit writer
├── mod_device_identity.py       ← Device identity acquisition
├── mod_installed_apps.py        ← Package enumeration
├── mod_accounts.py              ← Account discovery
├── mod_activity_timeline.py     ← Timeline reconstruction
├── mod_logs.py                  ← System log collection
├── mod_network.py               ← Network info gathering
├── mod_media_inventory.py       ← Media file inventory
├── mod_media_pull.py            ← Selective media pulling
└── mod_collector_import.py      ← Collector app import (placeholder)
```

### Design Principles

| Principle                     | Implementation                                                    |
| ----------------------------- | ----------------------------------------------------------------- |
| **Modularity**                | Each acquisition module is independent; errors don't block others |
| **Forensic Safety**           | Read-only ADB commands only; full audit trail                     |
| **Standard Library Only**     | No pip dependencies at runtime (Python 3.12+ stdlib)              |
| **Pure Parsers**              | All parsing functions are pure (no side effects, no I/O)          |
| **Streaming Output**          | JSONL format for manifest and audit (append-friendly, no corruption risk) |
| **Graceful Degradation**      | Blocked commands produce structured error records, not crashes    |
| **Type Safety**               | Full type hints throughout the codebase                           |
| **Testability**               | Parsers tested with recorded ADB output fixtures                  |

---

## Future Work

| Phase / Feature                  | Description                                                       |
| -------------------------------- | ----------------------------------------------------------------- |
| **Phase 1 Part B**               | WhatsApp, Telegram, Signal acquisition from rooted devices or imported filesystem images |
| **Collector APK**                | Android Studio / Kotlin app for call logs, SMS, contacts, and other permission-gated data |
| **Forensic Timeline Merger**     | Unified timeline combining all Part A and Part B events           |
| **Dashboard**                    | React + FastAPI web interface for case management and evidence browsing |
| **Portable USB Deployment**      | Self-contained USB stick with Python, ADB, and E-RAKSHAK          |
| **PyInstaller Packaging**        | Single-executable distribution for non-technical investigators    |
| **Report Generation**            | Automated PDF/HTML forensic report from acquisition data          |
| **Chain of Custody Logging**     | Examiner identity, digital signatures, and custody transfer records |

---

## License

> **Prototype — Hackathon Use Only**
>
> This software is developed as a hackathon prototype for authorized forensic investigations.
> It is not intended for production deployment without further validation, legal review,
> and compliance verification. Use only with proper legal authorization and on devices
> for which you have lawful access.

---

<p align="center">
  <strong>E-RAKSHAK</strong> · Android Rapid Evidence Triage & Forensic Preview Tool<br>
  <em>Phase 1 · Part A — ADB-Based Forensic Acquisition</em>
</p>
