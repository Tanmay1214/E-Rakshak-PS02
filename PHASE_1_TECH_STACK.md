# Phase 1 Tech Stack: Android Evidence Acquisition

## Purpose

Phase 1 is focused on acquisition, not full forensic analysis or dashboard polish.

The goal for Week 1 is:

- Detect a connected Android device.
- Extract available Android-level information.
- Collect accessible artifacts in a forensically careful way.
- Hash every acquired artifact.
- Store everything in a structured case folder.
- Prepare the project architecture so it can later run from a portable or bootable USB field kit.

This phase is split into two parts:

1. Android-level acquisition:
   - Mobile model name and number.
   - Manufacturer and device identifiers.
   - Android version and SDK level.
   - Build fingerprint.
   - Security patch level.
   - Wifi network history
   - Hotspot History
   - Call logs.
   - SMS/MMS 
   - Location-related sources.
   - Browser history, where technically available.
   - Media files (ONLY OF LAST 7 DAYS)

2. Emerging-app acquisition:
   - WhatsApp.
   - Telegram.
   - Signal.

Important limitation: modern Android security prevents normal non-root ADB from directly reading private app databases for WhatsApp, Telegram, Signal, Chrome, and many other apps. The prototype should clearly separate what is available through basic ADB, what requires an authorized collector APK, and what requires a rooted/test/imported evidence source.

---

## Recommended Stack Summary

| Layer | Recommended Technology | Reason |
|---|---|---|
| Core acquisition engine | Python 3.11+
 | Fast development, strong filesystem support, built-in hashing, SQLite support, good packaging options |
| Android communication | Android Debug Bridge, ADB Platform Tools | Official and standard method for USB communication with Android devices |
| Case storage | Folder structure + JSON/JSONL + SQLite inventory | Transparent, easy to inspect, easy to hash, suitable for forensic preview |
| Hashing | SHA-256 via Python `hashlib` | Simple, reliable, defensible integrity check |
| Database handling | Python `sqlite3` | Useful for Android/app SQLite artifacts and later parser plugins |
| Command interface | Python CLI using `argparse` first, optionally `Typer` later | CLI is reliable for demos and portable field use |
| Android companion app | Kotlin Android app | Needed for permission-based collection of call logs, SMS, contacts, and media index |
| Local API, later | FastAPI | Useful when the dashboard needs to call the acquisition engine |
| Dashboard, later | React + Vite | Good for fast preview UI after acquisition works |
| Portable packaging | PyInstaller one-folder build | Bundles Python runtime and dependencies for easier field deployment |
| Linux portable package, later | AppImage | Good fit for Linux-based portable deployments |
| Bootable field kit | Linux Live USB with bundled tool and ADB | Controlled offline environment for field use |

---

## Core Principle

Build the acquisition engine first.

Do not start Phase 1 with Electron, Tauri, or a heavy dashboard. Those are useful later, but the Week 1 risk is not UI. The Week 1 risk is whether the tool can reliably collect data, preserve hashes, and produce a clean case folder.

Recommended command style:

```bash
erakshak acquire --case CASE001 --device auto --profile quick
erakshak acquire --case CASE001 --device auto --profile media
erakshak verify --case CASE001
```

The dashboard can later call the same acquisition engine.

---

## Acquisition Modes

The tool should support three acquisition lanes.

### Mode A: Basic ADB Acquisition

Works when:

- The device is unlocked.
- USB debugging is enabled.
- The host computer is authorized by the device.

Can collect:

- Device model/manufacturer.
- Android version.
- SDK level.
- Security patch level.
- Build fingerprint.
- Kernel/build properties.
- Package list.
- Shared storage media, where accessible.
- Public files and directories available to shell/user access.

Usually cannot collect:

- Call logs.
- SMS.
- Private browser history.
- WhatsApp private databases.
- Telegram private databases.
- Signal private databases.

### Mode B: Authorized Collector APK

Works when:

- The device is unlocked.
- User/officer has authority to install and grant permissions to a companion app.
- The collector app requests permissions transparently.

Can collect:

- Call logs, if permission is granted.
- SMS/MMS, if permission is granted.
- Contacts, if included.
- Media index through Android MediaStore.
- Basic device information.

For forensic honesty, installing this app changes device state. The action must be recorded in the audit log.

### Mode C: Rooted Device or Imported Evidence Source

Works when:

- The device is already rooted in a test/demo setup, or
- The team imports an already-acquired logical filesystem/app data dump.

Can collect:

- App private databases.
- Browser history databases.
- WhatsApp databases, sidecar files, media, backups, and cache folders.
- Telegram app data and cache folders.
- Signal encrypted database and associated files.

The tool should not include rooting, exploitation, lock bypass, or bootloader unlocking as part of the prototype.

---

## Part 1: Android-Level Acquisition Stack

### Device Identity and Software Information

Technology:

- Python subprocess wrapper.
- ADB shell commands.
- `getprop` output parsing.

Collect:

- Serial number from ADB.
- Manufacturer.
- Brand.
- Model.
- Device name.
- Product name.
- Android release version.
- SDK level.
- Build fingerprint.
- Build ID.
- Security patch level.
- Kernel version.
- SELinux status.
- Verified boot state, where available.

Output:

```text
cases/<case_id>/<exhibit_id>/device/device_info.json
cases/<case_id>/<exhibit_id>/device/getprop_raw.txt
cases/<case_id>/<exhibit_id>/device/packages.txt
```

### Call Logs

Technology:

- Authorized Kotlin collector APK.
- Android `CallLog.Calls` provider.
- JSONL export.

Output:

```text
cases/<case_id>/<exhibit_id>/collector/call_logs.jsonl
```

Each record should include:

- Phone number.
- Contact name, if available.
- Call type.
- Timestamp.
- Duration.
- Source method.
- Extraction timestamp.

### SMS/MMS

Technology:

- Authorized Kotlin collector APK.
- Android Telephony provider.
- JSONL export.

Output:

```text
cases/<case_id>/<exhibit_id>/collector/sms.jsonl
cases/<case_id>/<exhibit_id>/collector/mms.jsonl
```

Each record should include:

- Sender/recipient.
- Message body, where permission allows.
- Timestamp.
- Message type.
- Read/status flags.
- Source method.

### Location Sources

Technology:

- Python EXIF extraction for media GPS metadata.
- ADB shared-storage scan.
- Root/import parser path for app/system location databases.

Collect in Phase 1:

- GPS EXIF metadata from photos/videos where present.
- Location-like files in shared storage, where present.
- Root/import location artifacts if a prepared dataset exists.

Do not promise Google Timeline extraction in Phase 1. That is usually cloud/account based and outside the rapid local triage scope.

### Browser History

Technology:

- Root/import only for private browser databases.
- SQLite parser later.

Important:

Chrome and other browser history databases are usually stored inside app-private folders. Normal non-root ADB should not be expected to access them.

Phase 1 target:

- Detect installed browsers.
- Record browser package names and versions.
- If root/import source is available, acquire browser database files and sidecar WAL/SHM files.

### Media Files(ONLY LAST 7 DAYS)

Technology:

- ADB pull for shared storage.
- Collector APK MediaStore index.
- Python SHA-256 hashing.

Collect:

- Recent images.
- Recent videos.
- Recent audio files.
- Thumbnails where accessible.
- Metadata inventory.

Recommended Phase 1 strategy:

- Do not blindly pull the entire phone storage.
- Start with a time-bounded or size-bounded acquisition profile.
- Example: last 7 days, maximum 2 GB, common media folders first.

Output:

```text
cases/<case_id>/<exhibit_id>/media/files/
cases/<case_id>/<exhibit_id>/media/media_index.jsonl
```

---

## Part 2: Emerging-App Acquisition Stack

### Shared App Acquisition Design

Technology:

- Python path registry.
- ADB package detection.
- Root/import artifact copier.
- SQLite sidecar preservation.

For each app:

- Detect whether the app is installed.
- Record package name.
- Record version name and version code.
- Record acquisition mode used.
- Acquire accessible shared media/cache.
- If root/import source is available, acquire private databases and sidecar files.

Always preserve:

- `.db`
- `.sqlite`
- `-wal`
- `-shm`
- `.journal`
- Preferences/config files.
- Cache folders.
- Media folders.

### WhatsApp

Likely package:

```text
com.whatsapp
```

Phase 1 target:

- Detect installation and version.
- Acquire shared WhatsApp media folders, where accessible.
- Acquire local backups, where accessible.
- In root/import mode, acquire private database files and sidecars.
- Do not promise decryption unless the required key/material is legally and technically available.

### Telegram

Likely packages:

```text
org.telegram.messenger
org.thunderdog.challegram
```

Phase 1 target:

- Detect installation and version.
- Acquire accessible Telegram media/cache folders.
- In root/import mode, acquire app-private databases/cache folders.
- Flag secret chats and unavailable encrypted content as limitations.

### Signal

Likely package:

```text
org.thoughtcrime.securesms
```

Phase 1 target:

- Detect installation and version.
- Acquire accessible media/cache only where available.
- In root/import mode, preserve encrypted databases and associated files.
- Do not promise live Signal message decryption from copied database files.
- If backup/passphrase-based import is added later, never log the passphrase.

---

## Suggested Repository Structure

```text
E-RAKSHAK/
  backend/
    erakshak/
      __init__.py
      cli.py
      adb/
        client.py
        commands.py
        parsers.py
      acquisition/
        device_info.py
        media.py
        packages.py
        collector_import.py
        app_artifacts.py
      case/
        case_folder.py
        manifest.py
        audit.py
        hashing.py
      parsers/
        sqlite_utils.py
        whatsapp.py
        telegram.py
        signal.py
      config/
        artifact_paths.yaml
    tests/
      fixtures/
      test_device_info.py
      test_manifest.py
      test_hashing.py

  android-collector/
    app/
    build.gradle
    README.md

  dashboard/
    package.json
    src/

  tools/
    platform-tools/
    packaging/

  cases/
    .gitkeep

  docs/
    acquisition_limitations.md
    field_deployment.md
```

---

## Case Folder Design

Each device should get a dedicated exhibit folder:

```text
cases/
  CASE001/
    EXHIBIT001/
      device/
      collector/
      media/
      apps/
        whatsapp/
        telegram/
        signal/
      logs/
        audit.jsonl
      manifests/
        files_manifest.jsonl
        hashes_sha256.txt
      reports/
```

Every acquired file should have a manifest record:

```json
{
  "case_id": "CASE001",
  "exhibit_id": "EXHIBIT001",
  "source_path": "/sdcard/DCIM/Camera/IMG_001.jpg",
  "stored_path": "media/files/IMG_001.jpg",
  "acquisition_method": "adb_pull",
  "sha256": "example_hash",
  "size_bytes": 123456,
  "started_at": "2026-07-07T10:00:00+05:30",
  "completed_at": "2026-07-07T10:00:02+05:30",
  "status": "acquired"
}
```

Every action should have an audit record:

```json
{
  "timestamp": "2026-07-07T10:00:00+05:30",
  "actor": "field_operator",
  "action": "adb_getprop",
  "target": "device",
  "result": "success",
  "details": {
    "command_category": "read_only_metadata"
  }
}
```

---

## Portable and Bootable Deployment Plan

The Phase 1 stack should be designed so it can later run in a field environment without installation.

### Minimum Portable Package

For early demos:

```text
E-RAKSHAK-Portable/
  erakshak.exe or erakshak
  platform-tools/
    adb
    fastboot
  collector.apk
  cases/
  logs/
  README_FIELD_USE.md
```

### Recommended Hackathon Field Kit

Use a Linux live USB with persistence:

```text
Bootable USB
  Linux live environment
  E-RAKSHAK/
    erakshak executable
    platform-tools/adb
    collector.apk
    cases/
    logs/
    docs/
```

Advantages:

- Controlled operating system.
- Offline operation.
- Predictable ADB behavior.
- No dependency installation on field laptops.
- Stronger forensic story than “run random scripts on someone’s laptop.”

### Packaging Path

1. During Week 1:
   - Run from Python source.
   - Keep dependencies minimal.

2. After acquisition works:
   - Build PyInstaller one-folder package.

3. For Linux field kit:
   - Package as an AppImage or keep as PyInstaller one-folder.
   - Bundle Android Platform Tools.

4. For final demo:
   - Place the portable package inside a persistent Linux live USB.
   - Include a sample case folder and test dataset.

---

## Dependencies to Keep Minimal

Start with Python standard library as much as possible:

- `subprocess`
- `pathlib`
- `json`
- `sqlite3`
- `hashlib`
- `datetime`
- `logging`
- `shutil`
- `csv`

Optional Phase 1 additions:

- `typer` for cleaner CLI.
- `pydantic` for structured manifest models.
- `pytest` for tests.
- `pillow` or `exifread` for image metadata later.

Avoid heavy dependencies in Week 1 unless they solve a real blocker.

---

## Why Not Electron or Tauri in Phase 1?

Electron and Tauri are both good options for a later dashboard, but they should not be the first build target.

Reasons:

- Extraction reliability matters more than UI in Week 1.
- CLI is easier to test on real devices.
- CLI is easier to package for a bootable USB.
- The same backend can later power a dashboard.
- A broken UI should never block evidence acquisition.

Recommended approach:

```text
Week 1: Python CLI acquisition engine
Week 2: Parsers + preview data model
Week 3: Dashboard
Week 4: Packaging, bootable USB, demo polish
```

---

## Phase 1 Acceptance Checklist

By the end of Phase 1, the team should be able to demonstrate:

- A connected Android device is detected through ADB.
- Device identity and software information are extracted.
- Security patch level is recorded.
- Package list is acquired.
- Media files are acquired from shared storage.
- Every acquired file is hashed with SHA-256.
- A case folder is created automatically.
- A manifest is written.
- An audit log is written.
- Call logs and SMS are acquired through the authorized collector APK, if permissions are granted.
- WhatsApp, Telegram, and Signal are detected by package name.
- Accessible shared app media/cache is acquired.
- Private app data is clearly marked as requiring root/import mode.
- The acquisition tool can run from a portable folder without installing Python manually.

---

## Final Recommendation

Use this stack for Phase 1:

```text
Python 3.12 acquisition CLI
ADB Platform Tools
Kotlin Android collector APK
JSONL audit logs
SHA-256 file manifest
SQLite inventory database
PyInstaller one-folder packaging
Linux live USB deployment path
React/FastAPI dashboard later
```

This stack gives the team the best balance of speed, forensic defensibility, and future portability.
