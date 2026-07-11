# Phase 1 - Android Evidence Acquisition Plan

## Objective

During Week 1, build and validate the acquisition layer that pulls selected evidence from an Android device into a structured case folder. Phase 1 deliberately stops at **collection, hashing, inventory, and basic extraction verification**. Rich parsing and dashboard analysis come later.

Phase 1 has two parts:

- **Part A - Android-level information and standard artifacts**
- **Part B - Emerging-app data: WhatsApp, Telegram, and Signal**

The acquisition engine must support three access lanes from the beginning:

1. **ADB Basic:** unlocked phone, USB debugging already enabled, host authorized.
2. **Authorized Collector:** a visible companion APK installed with the device owner's/legal authority and explicit permissions.
3. **Root/Import:** an already-rooted test device or a previously acquired filesystem folder/archive. The project will not root, exploit, unlock a bootloader, or bypass a passcode.

## Important feasibility rule

Do not design one extraction method and assume it works everywhere. Every requested artifact has a different access boundary.

| Artifact | ADB Basic | Authorized Collector | Root/Import |
|---|---:|---:|---:|
| Model, manufacturer, serial, Android/build/security patch | Yes | Yes | Yes |
| Installed packages and versions | Mostly | Yes | Yes |
| Calls | Not reliable across OEM/Android versions | Yes, with `READ_CALL_LOG` | Yes |
| SMS/MMS | Not reliable across OEM/Android versions | Yes, with `READ_SMS` | Yes |
| Shared photos/videos/audio/downloads | Yes where ADB/shared-storage access permits | Yes, subject to modern media permissions/user selection | Yes |
| Precise historical device location | No universal Android source | Only data exposed to the collector; not another app's private history | App/system artifacts when accessible; highly version-specific |
| Browser history | No | Collector cannot read Chrome/other browsers' private history | Browser databases when accessible |
| WhatsApp/Telegram/Signal private data | No | No; Android sandbox blocks cross-app private data | Accessible database/media files only |

The UI and manifest must record `acquired`, `permission_denied`, `not_accessible`, `not_supported`, or `not_present` for every target. “No records found” is valid only after a source was actually acquired and queried.

---

# Part A - Android-level information and standard artifacts

## A1. Connection and preflight

### Inputs

- Case ID, exhibit ID, operator ID, authority/consent reference.
- Selected device serial if more than one ADB device is present.

### Checks

1. Locate the pinned `adb` binary and record its version and SHA-256.
2. Run `adb devices -l` and classify the state: `device`, `unauthorized`, `offline`, or absent.
3. Never automatically accept authorization or change USB mode.
4. Capture host UTC time, timezone, device time, and calculated clock difference.
5. Check device battery and available host storage.
6. Detect root without changing state: test whether `su -c id` is already available. Do not attempt `adb root` on a production device.
7. Create the acquisition manifest before collecting artifacts.

### Output

`preflight.json` containing device state, timestamps, tool version, selected lane, warnings, and all failed checks.

## A2. Device identity: model name and model number

Collect the raw property snapshot first, then normalize key fields.

### Primary read-only commands

```text
adb -s <serial> shell getprop
adb -s <serial> shell settings get global device_name
adb -s <serial> shell cat /proc/cpuinfo
```

### Normalize

- Manufacturer: `ro.product.manufacturer`
- Marketing/model name: `ro.product.model`
- Product/device/codename: `ro.product.name`, `ro.product.device`
- Hardware/board: `ro.hardware`, `ro.product.board`
- ADB serial: host-side ADB serial plus `ro.serialno` when exposed
- Build fingerprint: `ro.build.fingerprint`

“Mobile number” must not be confused with “model number.” If the requirement later includes the SIM phone number, treat it as a separate optional field: it is frequently unavailable or blank and should not be used as device identity.

### Output

- `raw/system/getprop.txt`
- `derived/device_identity.json`

## A3. Software and security information

### Collect

- Android release: `ro.build.version.release`
- SDK/API level: `ro.build.version.sdk`
- Security patch level: `ro.build.version.security_patch`
- Build ID/display/fingerprint and build date.
- Kernel: `uname -a` and `/proc/version`
- Verified Boot state: exposed `ro.boot.*` properties such as verified-boot and flash lock state where available.
- Encryption state/type properties where exposed.
- SELinux status: `getenforce`.
- Device policy summary: `dumpsys device_policy` only if approved for the selected profile.
- Installed packages, versions, installer/source and paths using `pm list packages`/`dumpsys package` with a strict time budget.

### Output

- `raw/system/software_properties.txt`
- `raw/system/packages.txt`
- `derived/software_summary.json`

Record property absence as `not_exposed`; OEMs do not expose an identical set of properties.

## A4. Call logs

### Preferred non-root method: authorized collector

The collector requests `READ_CALL_LOG` visibly and queries `CallLog.Calls.CONTENT_URI`. Export records without updating or marking them read.

Minimum fields:

- Row ID, number, cached name, type/direction.
- Start timestamp, duration, presentation, country ISO.
- Features such as video/Wi-Fi where present.
- Last-modified value where provided.
- Subscription/account identifier where exposed.

### Root/import method

Acquire the relevant contacts/call-log database **and its `-wal`, `-shm`, and journal sidecars as a group**. Exact paths differ by OEM, user/profile, and Android version; discover candidates from an allowlist rather than hard-coding one path as universal.

### Output

- Collector lane: `raw/collector/calls.jsonl`
- Root/import lane: source database group under `raw/android/call_logs/`
- `source_metadata.json` with access method, URI/path, permission result, record count, bytes, and hashes.

## A5. SMS and MMS

### Preferred non-root method: authorized collector

Request `READ_SMS` visibly and query the Telephony providers. Export only; do not request default-SMS-app status and do not modify message state.

Minimum SMS fields:

- Row/thread ID, address, body, message type.
- Sent/received timestamps, read/status flags, subscription ID.

Minimum MMS fields:

- PDU/conversation metadata.
- Addresses/participants.
- Text and media parts with MIME type and source relationship.

### Root/import method

Acquire the telephony database and sidecars as one group, plus referenced MMS parts when available.

### Output

- `raw/collector/sms.jsonl`
- `raw/collector/mms.jsonl` and `raw/collector/mms_parts/`
- Or raw DB group under `raw/android/telephony/`

## A6. Location evidence

There is no single universal “Android location history” database available through normal ADB. Split this target into explicit sources:

1. **Media geolocation:** EXIF GPS in accessible photos/videos.
2. **Shared/downloaded location files:** GPX, KML, GeoJSON and similar accessible files.
3. **Call-composer location:** only when exposed by the call-log provider and permission permits it.
4. **App/system location artifacts:** root/import only, version- and app-specific.
5. **Google account Timeline/cloud history:** out of Phase 1; it is cloud/account acquisition, not device logical acquisition.

For each coordinate retain source, original timestamp, timestamp type, precision, and confidence. Never label IP geolocation or phone-number geocoding as device GPS history.

## A7. Browser history

### Non-root

Ordinary ADB and a companion collector cannot read another browser's private sandbox. Collect only accessible downloads/bookmarks explicitly exported by the user; do not promise browser history.

### Root/import

Discover installed browser packages, then acquire known browser profile databases and all journal sidecars. Start Week 1 with Chrome/Chromium-compatible `History`/`Favicons` sources; add other browsers only after fixtures exist.

Acquisition output must retain the original profile path and package/version because browser schemas evolve.

## A8. Media files

### Collection strategy

- Query inventory first: URI/path, display name, relative path, MIME type, size, modified/taken time, dimensions/duration, owner package if available.
- Apply the selected time window and size budget.
- Pull priority thumbnails and recent media before full-size files.
- Hash every pulled file during/after transfer.
- Preserve original extension and relative path under a safe encoded destination path.
- Do not open media automatically; generate derived thumbnails later from working copies.

### Sources

- ADB-accessible shared storage for the ADB Basic lane.
- Android `MediaStore` for the authorized collector, respecting `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`, and user-selected-photo behavior on applicable versions.
- Direct filesystem sources for root/import.

### Budgets for the rapid profile

- Inventory all accessible media metadata.
- Pull thumbnails plus the most recent N files or files inside the selected date range.
- Stop at a configurable byte/time limit and mark remaining files `deferred`, not missing.

---

# Part B - WhatsApp, Telegram, and Signal data

## B1. Shared design for emerging apps

Part B begins by detecting package presence and version. For each app, acquire an **evidence source group** rather than an isolated `.db` file:

- Main databases.
- `-wal`, `-shm`, rollback journals and related index/contact databases.
- Preferences/configuration needed to interpret accounts, when accessible and legally in scope.
- Referenced thumbnails, cache items, and shared media under the time/size budget.
- App version, package name, user/profile ID, source paths, file sizes, and SHA-256 values.

The acquisition engine must use a versioned path/profile registry:

```text
profile_id, app, package, version_range, access_lane,
candidate_paths, grouped_sidecars, media_roots, parser_hint
```

Do not silently choose the first file found. Record all candidates, selected source, and reason.

## B2. WhatsApp

### What to target when accessible

- Primary message/chat databases and their sidecars.
- Contacts/JID-related databases.
- Preferences/account metadata required for interpretation.
- App thumbnails/cache.
- Shared WhatsApp media directories and locally stored encrypted backup files.

### Access reality

- ADB Basic: shared WhatsApp media or backup files may be visible; private live databases and private key material are not.
- Authorized Collector: cannot cross the WhatsApp sandbox.
- Root/import: acquire accessible private database/source groups.
- An encrypted WhatsApp backup is not equivalent to readable chats. Preserve it and label it encrypted unless the required lawful key material is separately available.

### Week 1 definition of done

The engine detects WhatsApp, records its version, acquires a complete database group from the rooted fixture/import, inventories recent shared media, and verifies every hash. Deep message decoding belongs to Phase 2.

## B3. Telegram

### What to target when accessible

- Account-specific Telegram cache/message databases and sidecars.
- User/chat configuration and account metadata needed to map IDs.
- Thumbnails, cached media, documents, and shared Telegram media.
- Multiple accounts/profiles as distinct source groups.

### Access reality

- Standard cloud chats may leave local cached content, but local availability is not guaranteed.
- Secret-chat and self-destruct behavior must never be described as fully recoverable.
- ADB Basic/collector cannot read Telegram's private sandbox.
- Root/import can acquire accessible local databases and caches; it does not perform cloud acquisition.

### Week 1 definition of done

The engine detects Telegram variants, supports multiple discovered account/source groups, acquires database sidecars and selected caches from the rooted fixture/import, and reports which expected source classes were absent.

## B4. Signal

### What to target when accessible

- Signal's private encrypted database and sidecars as preserved evidence.
- Attachment/cache files when accessible.
- A user-created Signal backup file if one already exists and is voluntarily supplied.
- App version and evidence of source encryption state.

### Access reality

- Signal data is designed to be encrypted and sandboxed.
- Copying a database from a rooted device does not guarantee that its content can be decrypted.
- The collector cannot read Signal's private data.
- Never log or persist a supplied backup passphrase. Passphrase-based backup decryption/parsing is a later, isolated feature.
- Deleted Signal recovery is not a Week 1 promise.

### Week 1 definition of done

The engine preserves accessible encrypted sources without corruption, detects a supplied backup, hashes it, records that its content is encrypted/not yet parsed, and never exposes secrets in logs.

---

# Evidence-transfer design

## Case-folder output

```text
cases/<case>/<exhibit>/
  acquisition/
    preflight.json
    acquisition_manifest.json
    audit.jsonl
  raw/
    system/
    collector/
    android/
    apps/whatsapp/
    apps/telegram/
    apps/signal/
    media/
  derived/
    device_identity.json
    software_summary.json
  hashes/
    sha256sums.txt
```

## Manifest record per source

- Evidence ID and source-group ID.
- Artifact class and application/package.
- Device serial/exhibit and Android user/profile.
- Acquisition lane and exact source URI/path.
- Start/end UTC, device time and clock offset.
- Command/API operation identifier and tool version.
- Destination path, byte count and SHA-256.
- Source-side hash if available.
- Result and reason code.
- Volatility/consistency status.

## Database consistency rule

Live SQLite files can change while copied. The engine must:

1. Acquire DB plus sidecars together in one streamed archive where possible.
2. Record source sizes/timestamps before and after transfer.
3. Compute source hashes where safe and supported.
4. If the group changes, retain the first attempt, retry once into a new attempt folder, and flag both as volatile.
5. Never `VACUUM`, checkpoint, open writable, force-stop an app, or create an on-device SQLite backup without an explicitly approved and logged acquisition profile.

---

# Week 1 execution schedule

## Day 1 - Framework and feasibility harness

- Build ADB process wrapper with explicit device serial, timeout, stdout/stderr capture, cancellation, and audit events.
- Implement case folder, streaming SHA-256, manifest schema, and result reason codes.
- Create capability detection and the three access lanes.
- Prepare one stock non-root phone/emulator and one pre-rooted test emulator/import fixture.

**Exit:** an authorized device is detected and a test stream is acquired, hashed, manifested, and independently verified.

## Day 2 - Device/software acquisition

- Implement preflight, getprop snapshot, identity normalization, software/security summary, package inventory and clock offset.
- Add tests for missing OEM properties, unauthorized ADB, multiple devices, and disconnects.

**Exit:** model, build, Android version, SDK and security patch are correct on both reference devices.

## Day 3 - Standard communications and media

- Build the minimal authorized collector for calls, SMS/MMS and MediaStore inventory, or use a controlled fixture export if APK work is assigned separately.
- Implement root/import database-group collection for calls/SMS.
- Implement prioritized shared-media inventory/pull and EXIF-preserving copy.

**Exit:** seeded calls, messages and recent media are acquired with expected counts/hashes; denied permissions are reported accurately.

## Day 4 - Location/browser and emerging-app acquisition

- Implement explicit location-source categories and browser root/import acquisition.
- Add package/version detection and versioned acquisition profiles for WhatsApp, Telegram and Signal.
- Acquire DB/sidecar/media source groups from rooted fixtures or imported datasets.

**Exit:** each app is reported as acquired, partially acquired, inaccessible, absent or unsupported with no ambiguous “zero results.”

## Day 5 - Hardening and validation

- Test Android 11/12 and a recent Android version where available, including stock and rooted/import paths.
- Test cable removal, low host disk, changed live DB, huge media folder, missing permission, multiple user/profile paths and corrupted imports.
- Freeze ADB/tool versions and fixtures.
- Measure time to first acquired artifact and total rapid-profile time.
- Produce a Phase 1 capability matrix with evidence files and expected hashes.

**Exit:** one command/API call creates a complete, verifiable Phase 1 case folder in under the agreed time budget on the reference dataset.

---

# Team workstreams

- **Acquisition core:** ADB wrapper, root/import streaming, cancellation and path safety.
- **Android collector:** permission UI and provider exports for calls, SMS/MMS and media.
- **Evidence integrity:** hashing, manifests, audit chain and verification utility.
- **App profiles/testing:** WhatsApp/Telegram/Signal fixtures, path registry, version coverage and ground-truth validation.

These can be developed concurrently after the manifest and plugin interfaces are frozen on Day 1.

# Phase 1 acceptance checklist

- [ ] Device identity, Android version, build and security patch extracted and normalized.
- [ ] Package inventory includes WhatsApp/Telegram/Signal presence and version.
- [ ] Calls, SMS/MMS and media acquired through at least one honest supported lane.
- [ ] Location output identifies its exact source type; no generic unsupported “location history” claim.
- [ ] Browser history limitation is visible on non-root; root/import fixture acquisition works.
- [ ] WhatsApp, Telegram and Signal source groups acquired from rooted/import fixtures without claiming universal decryption.
- [ ] Every target has a result/reason code.
- [ ] Every acquired file has SHA-256, provenance and acquisition timestamps.
- [ ] DB sidecars are preserved and volatile sources are flagged.
- [ ] Audit log contains every command/API action and no secrets.
- [ ] Independent verification reproduces all case hashes.

