# E-RAKSHAK Forensic Dashboard Plan

## 1. Dashboard Objective

The forensic dashboard is the preview layer for E-RAKSHAK. It should merge Android-level acquisition data, WhatsApp data, Telegram data, Signal data, media, calls, locations, apps, accounts, logs, and integrity information into one readable interface for field officers.

The dashboard should help answer these questions quickly:

- What device was examined?
- What acquisition method was used?
- What evidence sources were available?
- What are the most recent and important events?
- Are there messages from WhatsApp, Telegram, Signal, SMS, or other sources?
- Are there deleted or recovered messages?
- Which contacts, numbers, accounts, media, and locations are relevant?
- Can an officer search by keyword or date range?
- Can a preview report be exported?
- Can the integrity of acquired evidence be verified?

The dashboard must clearly state:

```text
Forensic Preview Only — Not a Full Examination
```

---

## 2. High-Level Flow

```text
Part A acquisition outputs
        +
WhatsApp / Telegram / Signal parser outputs
        +
Media / location / app / network / account artifacts
        ↓
Normalize evidence into SQLite
        ↓
Expose dashboard API
        ↓
Render timeline-first dashboard
        ↓
Export forensic preview report
```

---

## 3. Recommended Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite + TypeScript | Fast, lightweight dashboard UI |
| Styling | Tailwind CSS | Rapid dark forensic UI styling |
| Backend API | FastAPI | Serve local dashboard APIs |
| Evidence Index | SQLite | Portable, local, inspectable evidence index |
| Existing Backend | Python | Reuse current acquisition/parser modules |
| Report Export | HTML first, PDF later | Portable field report generation |
| Packaging Later | PyInstaller + static frontend bundle | Lightweight USB/portable deployment |

Recommended dashboard launch command:

```bash
erakshak dashboard --case CASE001 --exhibit EXHIBIT001
```

This should start a local server:

```text
http://127.0.0.1:8765
```

---

## 4. Core Architecture

Suggested backend structure:

```text
backend/
  erakshak/
    dashboard/
      __init__.py
      api.py
      case_loader.py
      normalizer.py
      timeline_builder.py
      search.py
      report_export.py
      integrity.py
```

Suggested frontend structure:

```text
dashboard/
  src/
    pages/
      CaseDashboard.tsx
    components/
      TopBar.tsx
      Sidebar.tsx
      Timeline.tsx
      EventCard.tsx
      EventDetailsPanel.tsx
      StatCards.tsx
      FiltersBar.tsx
      KeywordSearch.tsx
      MediaPreview.tsx
      LocationPreview.tsx
      ExportButton.tsx
      IntegrityBadge.tsx
    services/
      api.ts
    types/
      evidence.ts
```

---

## 5. Evidence Normalization

The dashboard should not directly read many raw JSON/JSONL files on every page load. First, all case outputs should be normalized into a SQLite database:

```text
cases/<case_id>/<exhibit_id>/derived/evidence_index.db
```

### 5.1 Evidence Index Tables

Recommended SQLite tables:

```text
case_info
device_info
timeline_events
messages
calls
contacts
media
locations
apps
files
accounts
network_events
system_events
parser_outputs
hashes
audit_events
```

### 5.2 Most Important Table: `timeline_events`

All important artifacts should become timeline events.

Suggested schema:

```sql
CREATE TABLE timeline_events (
  id TEXT PRIMARY KEY,
  timestamp TEXT,
  source_app TEXT,
  source_type TEXT,
  event_type TEXT,
  direction TEXT,
  title TEXT,
  summary TEXT,
  sender TEXT,
  receiver TEXT,
  phone_number TEXT,
  location_lat REAL,
  location_lon REAL,
  media_path TEXT,
  file_path TEXT,
  deleted_status TEXT,
  recovered_status TEXT,
  confidence TEXT,
  source_file TEXT,
  source_hash TEXT,
  raw_ref TEXT
);
```

Example event types:

```text
whatsapp_message
telegram_message
signal_message
sms_message
phone_call
whatsapp_call
telegram_call
signal_call
location_update
media_captured
file_accessed
browser_history
app_opened
notification
network_event
system_event
```

---

## 6. Input Source Mapping

| Existing Output | Dashboard Use |
|---|---|
| `device_identity.json` | Case header and device view |
| `software_summary.json` | Case header and device view |
| `installed_apps.jsonl` | Apps view and timeline app events |
| `accounts.jsonl` | Accounts view and identity leads |
| `account_email_leads.jsonl` | Searchable email leads |
| `call_logs.jsonl` | Calls view and timeline |
| `sms.jsonl` | Messages view and timeline |
| `media_index.jsonl` | Media view and timeline |
| `network_summary.json` | Network view |
| `network_connections.jsonl` | Network timeline |
| `logcat_events.jsonl` | System events timeline |
| WhatsApp exporter JSON/HTML | WhatsApp messages, contacts, media, timeline |
| Telegram parser output | Telegram messages, media, timeline |
| Signal parser output | Signal messages, media, timeline |
| `acquisition_manifest.jsonl` | Integrity view |
| `audit.jsonl` | Audit trail view |
| `sha256sums.txt` | Hash verification view |

---

## 7. Dashboard Layout

The UI should follow a timeline-first forensic preview layout similar to the provided reference image.

### 7.1 Top Bar

Display:

- Tool name: `E-RAKSHAK Rapid Evidence Triage`
- Case ID
- Exhibit ID
- Device model
- Android version
- Security patch level
- IMEI/serial if available
- Acquisition status
- Time taken
- Export Report button
- Open Case Folder button
- Verify Hashes button

Example:

```text
Case ID: CASE-2026-001
Device: Samsung Galaxy S21 Android 13
Status: Acquisition Complete
Time Taken: 06:42
```

### 7.2 Left Sidebar

Sections:

```text
Case Overview
- Timeline
- Messages
- Calls
- Contacts
- Media
- Locations
- Apps
- Files
- Accounts
- Network
- System Logs

Quick Filters
- All Time
- Last 24 Hours
- Last 7 Days
- Custom Range

Keyword Search
- Global search box

Acquisition Info
- Method
- Root Access
- Extraction status
- Start time
- End time
- Case hash
- Read-only acquisition badge
```

### 7.3 Main Timeline Panel

Default view should be the timeline.

Each timeline card should show:

- timestamp
- icon
- source app
- event title
- short summary
- deleted/recovered badge
- confidence badge
- source/hash badge

Example cards:

```text
WhatsApp Message Received
From: +91 98765 43210
"Bhai, meeting cancel ho gayi..."

Deleted WhatsApp Message
[This message was deleted]

Telegram Message Sent
To: @Tech_Group

Location Update
Lat: 28.6139, Lon: 77.2090

Image Captured
IMG_20260718_095811.jpg
```

### 7.4 Right Event Details Panel

When an event is selected, show:

- event type
- source app
- sender
- receiver
- timestamp
- message body or summary
- deleted/recovered status
- extraction source
- database/table/source file
- SHA-256 hash
- parser used
- confidence level
- media preview
- location preview
- related events

---

## 8. Dashboard Views

Build the views in the following order.

### 8.1 Timeline View

Filters:

```text
All
Messages
Calls
WhatsApp
Telegram
Signal
Location
Media
Files
Browser
System
```

Additional filters:

- date range
- keyword search
- deleted only
- recovered only
- high-confidence only

### 8.2 Messages View

Columns:

```text
Time
App
Direction
From
To
Message
Deleted?
Recovered?
Source
Hash
```

### 8.3 Calls View

Include:

- Android phone calls
- WhatsApp calls
- Telegram calls, if available
- Signal calls, if available

Columns:

```text
Time
Type
Source
From
To
Duration
App/System
```

### 8.4 Contacts View

Merge contacts from:

- Android contacts
- WhatsApp contact mapping, if available
- Telegram users
- Signal contacts
- phone enrichment results, if implemented

Columns:

```text
Name
Phone
Apps Seen In
Message Count
Call Count
Last Seen
```

### 8.5 Media View

Use a grid layout.

Fields:

```text
Thumbnail
Filename
Source App
Path
Timestamp
Hash
Linked Chat/Event
```

### 8.6 Locations View

Fields:

```text
Timestamp
Latitude
Longitude
Source
Accuracy
Linked Event
```

Offline-first option:

- show coordinates first
- use Leaflet later
- avoid depending on Google Maps for field use
- optionally support offline map tiles in the final portable kit

### 8.7 Apps View

Fields:

```text
Package Name
App Name
Version
Install Time
Last Update Time
Permissions
System/User App
```

### 8.8 Accounts View

Fields:

```text
Account Name
Account Type
Provider App
Email Lead
Sync Provider
Source
```

### 8.9 Network View

Fields:

```text
Current IP
Wi-Fi SSID/BSSID
Carrier
SIM Info
VPN State
DNS
Bluetooth Devices
Active Connections
```

### 8.10 Integrity View

Show:

```text
Total files acquired
Total files hashed
Verified hashes
Missing files
Hash mismatches
Manifest status
Audit event count
Parser output hashes
```

This view is important for forensic credibility.

---

## 9. Global Search

Global search should search across:

- messages
- contacts
- phone numbers
- emails
- file names
- package names
- locations
- browser history
- notifications
- system logs
- network events

Search result format:

```text
result_type
timestamp
source
snippet
confidence
open_in_timeline
```

---

## 10. Export Report

The dashboard should export a readable forensic preview report.

Output:

```text
cases/<case_id>/<exhibit_id>/reports/forensic_preview_report.html
cases/<case_id>/<exhibit_id>/reports/forensic_preview_report.pdf
```

Report sections:

```text
1. Case summary
2. Device information
3. Acquisition summary
4. Key timeline events
5. Messages summary
6. Calls summary
7. Contacts of interest
8. Media preview
9. Locations
10. Installed apps
11. Accounts and identifiers
12. Network information
13. Deleted/recovered artifacts
14. Hash and integrity summary
15. Audit trail summary
16. Limitations
```

Mandatory limitation text:

```text
This report is a rapid forensic preview only. It is not a substitute for full laboratory examination.
```

---

## 11. API Design

FastAPI endpoints:

```text
GET /api/case/summary
GET /api/device
GET /api/timeline
GET /api/timeline/{event_id}
GET /api/messages
GET /api/calls
GET /api/contacts
GET /api/media
GET /api/locations
GET /api/apps
GET /api/accounts
GET /api/network
GET /api/system
GET /api/search?q=<keyword>
GET /api/integrity
POST /api/export-report
POST /api/verify-hashes
```

Example timeline query:

```text
GET /api/timeline?source=whatsapp&from=2026-07-01&to=2026-07-18&deleted=true&q=meeting
```

---

## 12. UI Theme

Use a dark forensic theme.

Suggested colors:

```text
background: #070b14
panel: #0d1320
panel_alt: #111827
border: #1c2537
text_primary: #f8fafc
text_secondary: #94a3b8
accent: #635bff
success: #22c55e
warning: #f59e0b
danger: #ef4444
whatsapp: #25d366
telegram: #229ed9
signal: #3a76f0
```

Use icons for:

- WhatsApp
- Telegram
- Signal
- Phone
- SMS
- Location
- Media
- File
- Browser
- System
- Account
- Network
- Hash/integrity

---

## 13. Implementation Roadmap

### Milestone 1: Evidence Indexer

Command:

```bash
python -m erakshak.cli build-dashboard-index --case CASE001 --exhibit EXHIBIT001
```

Tasks:

- read all existing derived files
- normalize messages, calls, contacts, media, apps, accounts, logs, network events
- build `derived/evidence_index.db`
- populate `timeline_events`
- write indexer audit event

Exit condition:

```text
Evidence index is generated and timeline_events contains merged data from Part A and app parsers.
```

### Milestone 2: Dashboard API

Tasks:

- implement FastAPI app
- load selected case/exhibit
- expose endpoints for summary, timeline, messages, calls, contacts, media, apps, locations, search, and integrity
- add pagination for large tables

Exit condition:

```text
API returns timeline and case summary from evidence_index.db.
```

### Milestone 3: React Dashboard UI

Tasks:

- create Vite React app
- implement top bar
- implement left sidebar
- implement timeline cards
- implement event details panel
- implement filters
- implement search box

Exit condition:

```text
The dashboard visually resembles the reference screenshot and can browse timeline events.
```

### Milestone 4: Category Views

Tasks:

- messages view
- calls view
- contacts view
- media view
- locations view
- apps view
- accounts view
- network view
- integrity view

Exit condition:

```text
Officer can switch between major evidence categories.
```

### Milestone 5: Export Report

Tasks:

- generate HTML preview report
- include case/device/acquisition summary
- include selected key events
- include hash/integrity summary
- include limitations
- add PDF export later

Exit condition:

```text
Dashboard can export a readable forensic preview report.
```

### Milestone 6: Portable Mode

Tasks:

- serve built React files from Python backend
- bundle backend with PyInstaller
- include ADB platform tools
- include WhatsApp parser/decryption tools already used
- ensure all tools are resolved from local bundled paths first

Exit condition:

```text
Dashboard runs from the project folder/USB without external installation.
```

---

## 14. Immediate Next Prompt for Implementation

Use this as the next prompt for Antigravity/Gemini:

```text
Implement the E-RAKSHAK dashboard backend indexer and API.

Read existing case folder outputs from:
cases/<case_id>/<exhibit_id>/

Normalize Part A outputs and WhatsApp/Telegram/Signal parser outputs into:
derived/evidence_index.db

Create tables:
case_info, device_info, timeline_events, messages, calls, contacts, media, locations, apps, accounts, network_events, system_events, parser_outputs, hashes, audit_events.

Create a timeline_events table that merges messages, calls, media, locations, app activity, browser events, system logs, and parser results.

Expose FastAPI endpoints:
GET /api/case/summary
GET /api/device
GET /api/timeline
GET /api/timeline/{event_id}
GET /api/messages
GET /api/calls
GET /api/contacts
GET /api/media
GET /api/locations
GET /api/apps
GET /api/accounts
GET /api/network
GET /api/system
GET /api/search
GET /api/integrity

Do not build the UI yet. First make the normalized evidence database and API stable.
```

---

## 15. Final Priority Order

```text
1. Normalize all evidence into evidence_index.db
2. Build timeline_events table
3. Build FastAPI endpoints
4. Build dashboard UI
5. Add event details panel
6. Add keyword/date filters
7. Add category views
8. Add export report
9. Add portable packaging
```

The normalized evidence index is the most important part. Once it exists, the timeline dashboard becomes much easier to build and maintain.
