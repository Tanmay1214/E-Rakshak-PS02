# E-RAKSHAK Forensic Triage — Frontend Handover & Dashboard Integration Guide

> **Document Purpose**: This guide provides complete architectural context, data schemas, directory layouts, and integration instructions for the Frontend Developer (and their LLM coding agent) to build the **E-RAKSHAK Evidence Triage Dashboard**.

---

## 1. Executive Summary & System Context

**E-RAKSHAK** is an Android Rapid Evidence Triage & Forensic Preview tool. The backend CLI / Python engine executes ADB-based forensic acquisition from Android devices/emulators, parses raw SQLite databases (`cache4.db`, WAL sidecars), and outputs structured evidence files into standardized case folders.

As the Frontend Developer, your goal is to consume the structured **JSON / JSONL data files** produced by the backend and render an interactive, analyst-friendly forensic investigation dashboard.

---

## 2. Backend Case Directory Layout

When the backend runs an acquisition (e.g. `python -m erakshak telegram-acquire --case CASE001 --exhibit EX001`), it generates a case folder with the following directory structure:

```text
cases/
└── <CASE_ID>/                        # e.g., PIXEL6_TG_CASE
    └── <EXHIBIT_ID>/                 # e.g., EX001
        ├── acquisition/
        │   ├── acquisition_manifest.jsonl   # Manifest of all acquired files
        │   └── audit.jsonl                  # Forensic audit trail (commands, timestamps, execution ms)
        │
        ├── raw/                             # RAW UNTOUCHED FORENSIC EVIDENCE
        │   └── apps/telegram/
        │       └── <PACKAGE_NAME>/          # e.g., org.telegram.messenger.web
        │           ├── files_cache4.db      # Acquired Telegram SQLite database
        │           ├── files_cache4.db-shm  # Shared memory sidecar
        │           └── files_cache4.db-wal  # Write-Ahead Log (contains deleted text residue)
        │
        ├── derived/                         # PARSED & NORMALIZED OUTPUTS FOR FRONTEND
        │   └── apps/telegram/
        │       ├── telegram_summary.json    # Full acquisition & parsing summary stats
        │       └── <PACKAGE_NAME>/
        │           ├── files_cache4_messages.jsonl   # Extracted Telegram messages
        │           ├── files_cache4_users.jsonl      # Extracted user contacts & profiles
        │           └── files_cache4_dialogs.jsonl    # Extracted chat threads / dialogs
        │
        └── hashes/
            └── sha256sums.txt               # Cryptographic SHA-256 hashes of all acquired files
```

---

## 3. Data Schemas & Field Definitions

All derived outputs are stored in **JSON** or **JSONL** (JSON Lines - where each line is a valid JSON object).

### 3.1. `files_cache4_messages.jsonl` (Extracted Messages)
Located at: `derived/apps/telegram/<PACKAGE_NAME>/files_cache4_messages.jsonl`

Each line represents a message object:

```json
{
  "mid": 138,
  "uid": 7722262739,
  "read_state": 2,
  "send_state": 0,
  "date": 1784798992,
  "out": 1,
  "ttl": 0,
  "reply_to_message_id": 0,
  "text": "Message 5"
}
```

#### Field Reference:
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `mid` | `number` | Unique Message ID inside Telegram's database. |
| `uid` | `number` | User / Chat Partner ID associated with this message. |
| `read_state` | `number` | Read indicator (e.g. `2` = unread/delivered, `3` = read). |
| `send_state` | `number` | Send status (`0` = sent successfully, `1` = pending/sending). |
| `date` | `number` | **Unix Epoch Timestamp in seconds**. Multiply by `1000` for JavaScript `Date`. |
| `out` | `number` | Direction: `1` = **Outgoing message** (sent by suspect), `0` = **Incoming message**. |
| `ttl` | `number` | Time-to-live / self-destruct timer in seconds (`0` if disabled). |
| `reply_to_message_id` | `number` | ID of the target message if this message is a reply (`0` if none). |
| `text` | `string` | **Decoded Message Text Content** extracted from Telegram binary payloads. |

---

### 3.2. `files_cache4_users.jsonl` (User Profiles & Contacts)
Located at: `derived/apps/telegram/<PACKAGE_NAME>/files_cache4_users.jsonl`

```json
{
  "uid": 7722262739,
  "name": "John Doe",
  "status": "online"
}
```

#### Field Reference:
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `uid` | `number` | User Unique Identifier. |
| `name` | `string` | Display Name or Contact Name. |
| `status` | `string \| null` | Presence or custom status string. |

---

### 3.3. `files_cache4_dialogs.jsonl` (Chat Conversations / Threads)
Located at: `derived/apps/telegram/<PACKAGE_NAME>/files_cache4_dialogs.jsonl`

```json
{
  "did": -2126547056,
  "date": 1706876879,
  "unread_count": 0,
  "last_mid": 290
}
```

#### Field Reference:
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `did` | `number` | Dialog / Chat ID (negative numbers usually represent channels/groups). |
| `date` | `number` | Unix timestamp of the last activity in this chat thread. |
| `unread_count` | `number` | Number of unread messages in this thread. |
| `last_mid` | `number` | Message ID of the latest message in this thread. |

---

### 3.4. `telegram_summary.json` (Overall Acquisition Stats)
Located at: `derived/apps/telegram/telegram_summary.json`

```json
{
  "acquisition": {
    "status": "acquired",
    "packages_found": ["org.telegram.messenger.web"],
    "packages_not_found": ["org.telegram.messenger", "org.telegram.plus"],
    "volatile_count": 0,
    "warnings": []
  },
  "parsing": {
    "parsed_dbs": [".../files_cache4.db"],
    "total_users": 31,
    "total_messages": 12,
    "total_dialogs": 11
  },
  "output_dir": ".../derived/apps/telegram"
}
```

---

## 4. Feature Implementation Recommendation: Active vs. Deleted Messages Timeline

> 💡 **Suggested Feature for Frontend Implementation**:
> In Telegram, when a user deletes a message, it is removed from the active database table (`messages_v2`), but its raw string content remains stored inside the Write-Ahead Log sidecar (`files_cache4.db-wal`).

### Proposed Unified Dashboard Model
To build a timeline view where users can select a **Time Interval Filter** (e.g., date range picker) and view both **Active** and **Deleted** messages side by side:

#### Recommended Unified JSON Interface:
```typescript
interface DashboardMessage {
  id: string | number;
  uid: number;
  senderName: string;
  timestamp: number;          // Unix epoch seconds
  isoDate: string;            // ISO 8601 string for UI display
  text: string;               // Decoded message body
  isOutgoing: boolean;        // out === 1
  isDeleted: boolean;         // true if recovered from WAL / freelist
  recoverySource: 'active_db' | 'wal_sidecar_carver';
}
```

#### Recommended UI UX Design:
1. **Time Range Filter Bar**: Allow analysts to pick a Start Date & End Date (filter by `timestamp`).
2. **Status Badges**:
   - 🟢 **Active Messages** (`isDeleted: false`): Render with standard chat bubble styling.
   - 🔴 **Deleted Messages** (`isDeleted: true`): Render with a red/amber highlight border and a prominent `[DELETED]` badge.
3. **Filter Toggles**: Add quick toggle buttons: `[ All Messages ]`, `[ Active Only ]`, `[ Deleted Only ]`.

---

## 5. How to Consume JSONL Files in JavaScript / Node.js API

Since JSONL files contain one JSON object per line, parse them as follows:

### Node.js / Express API Endpoint Example:
```javascript
const fs = require('fs');
const readline = require('readline');

async function loadMessagesJsonl(filePath) {
  const messages = [];
  if (!fs.existsSync(filePath)) return messages;

  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  for await (const line of rl) {
    if (line.trim()) {
      try {
        messages.push(JSON.parse(line));
      } catch (err) {
        console.error('Failed to parse line:', line, err);
      }
    }
  }
  return messages;
}
```

---

## 6. Comprehensive Developer FAQ

#### Q1: What if `files_cache4_messages.jsonl` is missing from the directory?
**Answer**: If `files_cache4_messages.jsonl` is missing or empty, it means 0 messages were present in the extracted database during acquisition. Handle this gracefully in the UI by displaying an empty state: *"No extracted messages found for this exhibit."*

#### Q2: How do I convert the `date` field to a human-readable date in Javascript?
**Answer**: The `date` field is in **Unix Epoch seconds**. Convert it to a JavaScript `Date` object by multiplying by 1000:
```javascript
const formattedDate = new Date(message.date * 1000).toLocaleString();
```

#### Q3: How do I link a message to its user contact name?
**Answer**: Match `message.uid` with `user.uid` from `files_cache4_users.jsonl`.
```javascript
const userMap = new Map(users.map(u => [u.uid, u.name]));
const senderName = userMap.get(message.uid) || `User (${message.uid})`;
```

#### Q4: What is the difference between `out: 1` and `out: 0`?
**Answer**:
- `out === 1`: Outgoing message sent by the device owner/suspect.
- `out === 0`: Incoming message received from another contact or channel.

#### Q5: Can package names vary between Android devices?
**Answer**: Yes. Telegram has multiple package variants registered in E-RAKSHAK:
- `org.telegram.messenger` (Official Play Store variant)
- `org.telegram.messenger.web` (Official Direct APK variant)
- `org.telegram.plus` (Plus Messenger client)

Dynamically read the subfolder names under `derived/apps/telegram/` to support any variant automatically.

#### Q6: How do I check hash integrity of the evidence files?
**Answer**: Read `hashes/sha256sums.txt` or execute the CLI verifier command:
```cmd
python -m erakshak verify --case-folder cases/<CASE_ID>/<EXHIBIT_ID>
```

---

*Handover document generated for E-RAKSHAK Dashboard Frontend Development.*
