"""Pure parsing functions for ADB command output.

Every function in this module is a **pure function**: it takes a string
(the raw stdout of an ADB command) and returns structured data.  No I/O,
no side-effects, no exceptions on malformed input — if something cannot be
parsed the function returns an empty container (``[]`` or ``{}``).
"""

from __future__ import annotations

import re
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# Device listing
# ═══════════════════════════════════════════════════════════════════════════

def parse_adb_devices(text: str) -> list[dict[str, str]]:
    """Parse ``adb devices -l`` output.

    Expected format::

        List of devices attached
        R5CR7039TBJ            device usb:1-1 product:a52qnsxx model:SM_A525F device:a52q transport_id:1

    Returns
    -------
    list[dict]
        Each dict may contain: *serial*, *state*, *usb*, *product*,
        *model*, *device*, *transport_id*.
    """
    results: list[dict[str, str]] = []
    if not text:
        return results

    for line in text.splitlines():
        line = line.strip()
        # Skip header and blank lines
        if not line or line.startswith("List of devices"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        entry: dict[str, str] = {
            "serial": parts[0],
            "state": parts[1],
        }

        # Parse optional key:value pairs after the state token
        for token in parts[2:]:
            if ":" in token:
                key, _, value = token.partition(":")
                entry[key] = value

        results.append(entry)

    return results


# ═══════════════════════════════════════════════════════════════════════════
# System properties
# ═══════════════════════════════════════════════════════════════════════════

_GETPROP_RE = re.compile(r"\[(.+?)\]\s*:\s*\[(.*)\]")


def parse_getprop(text: str) -> dict[str, str]:
    """Parse ``adb shell getprop`` output.

    Lines look like::

        [ro.build.version.release]: [13]

    Returns a dict mapping property names to values.
    """
    props: dict[str, str] = {}
    if not text:
        return props

    for line in text.splitlines():
        m = _GETPROP_RE.match(line.strip())
        if m:
            props[m.group(1)] = m.group(2)

    return props


# ═══════════════════════════════════════════════════════════════════════════
# Battery info
# ═══════════════════════════════════════════════════════════════════════════

def parse_battery_info(text: str) -> dict[str, Any]:
    """Parse ``adb shell dumpsys battery`` output.

    Expected format::

        Current Battery Service state:
          AC powered: false
          USB powered: true
          Wireless powered: false
          Max charging current: 500000
          Max charging voltage: 5000000
          Charge type: 1
          status: 2
          health: 2
          present: true
          level: 85
          scale: 100
          voltage: 4200
          temperature: 280
          technology: Li-ion

    Returns a dict with parsed key/value pairs.  Numeric values are
    converted to ``int`` where possible, boolean strings to ``bool``.
    """
    result: dict[str, Any] = {}
    if not text:
        return result

    for line in text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        # Skip section headers (they don't have a value after the colon)
        key, _, value = line.partition(":")
        value = value.strip()
        if not value:
            continue

        key = key.strip().lower().replace(" ", "_")

        # Type coercion
        if value.lower() in ("true", "false"):
            result[key] = value.lower() == "true"
        else:
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = value

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Installed packages
# ═══════════════════════════════════════════════════════════════════════════

# package:/data/app/~~abc==/com.example-xyz==/base.apk=com.example versionCode:123 uid:10042
_PACKAGE_RE = re.compile(
    r"package:(.+?)=([\w.]+)\s*(?:versionCode:(\d+))?\s*(?:uid:(\d+))?"
)


def parse_packages(text: str) -> list[dict[str, Any]]:
    """Parse ``pm list packages -f -U --show-versioncode`` output.

    Returns a list of dicts with keys: *package_name*, *apk_path*,
    *version_code*, *uid*.
    """
    results: list[dict[str, Any]] = []
    if not text:
        return results

    for line in text.splitlines():
        line = line.strip()
        m = _PACKAGE_RE.match(line)
        if m:
            results.append({
                "package_name": m.group(2),
                "apk_path": m.group(1),
                "version_code": int(m.group(3)) if m.group(3) else None,
                "uid": int(m.group(4)) if m.group(4) else None,
            })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Package detail (dumpsys package <pkg>)
# ═══════════════════════════════════════════════════════════════════════════

def parse_dumpsys_package_detail(text: str, package_name: str) -> dict[str, Any]:
    """Extract detailed info for *package_name* from ``dumpsys package`` output.

    Looks for the ``Package [<package>]`` section and extracts:

    * versionName, versionCode
    * firstInstallTime, lastUpdateTime
    * requested permissions (list)
    * install permissions with granted status (list of dicts)

    Returns an empty dict on any parsing failure.
    """
    info: dict[str, Any] = {
        "package_name": package_name,
        "version_name": None,
        "version_code": None,
        "first_install_time": None,
        "last_update_time": None,
        "requested_permissions": [],
        "install_permissions": [],
    }

    if not text:
        return info

    lines = text.splitlines()

    # ── locate the Package [...] block ───────────────────────────────────
    in_package_block = False
    in_requested_permissions = False
    in_install_permissions = False

    for line in lines:
        stripped = line.strip()

        # Detect start of the target package block
        if stripped.startswith(f"Package [{package_name}]") or stripped.startswith(f"pkg={package_name}"):
            in_package_block = True
            continue

        # Detect end of block (next Package [...] header or Packages: header)
        if in_package_block and (
            stripped.startswith("Package [") or stripped.startswith("pkg=")
        ):
            break

        if not in_package_block:
            continue

        # ── scalar fields ────────────────────────────────────────────────
        if stripped.startswith("versionName="):
            info["version_name"] = stripped.split("=", 1)[1]
        elif stripped.startswith("versionCode="):
            raw = stripped.split("=", 1)[1].split()[0]  # may have trailing info
            try:
                info["version_code"] = int(raw)
            except ValueError:
                info["version_code"] = raw
        elif stripped.startswith("firstInstallTime="):
            info["first_install_time"] = stripped.split("=", 1)[1]
        elif stripped.startswith("lastUpdateTime="):
            info["last_update_time"] = stripped.split("=", 1)[1]

        # ── requested permissions section ────────────────────────────────
        if stripped.startswith("requested permissions:") or stripped.startswith("grantedPermissions:"):
            in_requested_permissions = True
            in_install_permissions = False
            continue
        if stripped.startswith("install permissions:"):
            in_install_permissions = True
            in_requested_permissions = False
            continue

        # End of a sub-section: line without leading whitespace
        if not line.startswith(" ") and not line.startswith("\t"):
            in_requested_permissions = False
            in_install_permissions = False

        if in_requested_permissions:
            perm = stripped.rstrip(",")
            if perm and not perm.endswith(":"):
                # Strip trailing ": granted=true" if present on requested list
                perm_clean = perm.split(":")[0].strip()
                if perm_clean:
                    info["requested_permissions"].append(perm_clean)

        if in_install_permissions:
            # Format: android.permission.INTERNET: granted=true
            if "granted=" in stripped:
                perm_part, _, granted_part = stripped.partition(": granted=")
                perm_part = perm_part.strip().rstrip(",")
                granted = granted_part.strip().lower() == "true"
                info["install_permissions"].append({
                    "permission": perm_part,
                    "granted": granted,
                })

    return info


# ═══════════════════════════════════════════════════════════════════════════
# Account / email extraction
# ═══════════════════════════════════════════════════════════════════════════

_ACCOUNT_RE = re.compile(r"Account\s*\{name=(.+?),\s*type=(.+?)\}", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def parse_dumpsys_account(text: str) -> dict[str, Any]:
    """Parse ``dumpsys account`` output.

    Returns
    -------
    dict
        ``accounts`` – list of ``{name, type}`` dicts.
        ``emails`` – deduplicated sorted list of email addresses found
        anywhere in the text.
    """
    result: dict[str, Any] = {"accounts": [], "emails": []}
    if not text:
        return result

    seen_accounts: set[tuple[str, str]] = set()
    for m in _ACCOUNT_RE.finditer(text):
        name = m.group(1).strip()
        acct_type = m.group(2).strip()
        key = (name, acct_type)
        if key not in seen_accounts:
            seen_accounts.add(key)
            result["accounts"].append({"name": name, "type": acct_type})

    result["emails"] = extract_emails(text)
    return result


def extract_emails(text: str) -> list[str]:
    """Extract unique email addresses from *text*.

    Returns a sorted, deduplicated list.
    """
    if not text:
        return []
    return sorted(set(_EMAIL_RE.findall(text)))


# ═══════════════════════════════════════════════════════════════════════════
# Logcat
# ═══════════════════════════════════════════════════════════════════════════

# Standard logcat "threadtime" format:
#   MM-DD HH:MM:SS.mmm  PID  TID PRIORITY TAG : MESSAGE
# The PID/TID fields may have variable spacing.
_LOGCAT_RE = re.compile(
    r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+"  # timestamp
    r"(\d+)\s+"                                          # PID
    r"(\d+)\s+"                                          # TID
    r"([VDIWEF])\s+"                                     # priority
    r"(\S+)\s*:\s+"                                      # tag
    r"(.*)",                                             # message
)

# Keywords ➜ event type mapping
_EVENT_KEYWORDS: list[tuple[str, str, str | None]] = [
    # (substring in tag, substring in message or None, event_type)
    ("ActivityManager", "START", "app_launch"),
    ("ActivityManager", "Displayed", "app_displayed"),
    ("ActivityManager", None, "activity_manager"),
    ("AndroidRuntime", None, "crash"),
    ("FATAL", None, "fatal"),
    ("USB", None, "usb_event"),
    ("ConnectivityService", None, "connectivity"),
    ("NetworkAgent", None, "network"),
    ("boot", None, "boot_event"),
]


def _classify_logcat_event(priority: str, tag: str, message: str) -> str | None:
    """Return an event_type string if the line is forensically interesting."""
    tag_upper = tag.upper()
    msg_upper = message.upper()

    for tag_kw, msg_kw, event_type in _EVENT_KEYWORDS:
        tag_match = tag_kw.upper() in tag_upper
        if tag_match:
            if msg_kw is None or msg_kw.upper() in msg_upper:
                return event_type

    # Warnings and errors are always interesting
    if priority in ("W", "E", "F"):
        return f"priority_{priority}"

    return None


def parse_logcat(text: str) -> list[dict[str, Any]]:
    """Parse ``logcat -d`` output and extract forensically interesting events.

    Each returned dict contains: *timestamp*, *pid*, *tid*, *priority*,
    *tag*, *message*, *event_type*.
    """
    events: list[dict[str, Any]] = []
    if not text:
        return events

    for line in text.splitlines():
        m = _LOGCAT_RE.match(line.strip())
        if not m:
            continue

        timestamp = m.group(1)
        pid = m.group(2)
        tid = m.group(3)
        priority = m.group(4)
        tag = m.group(5)
        message = m.group(6)

        event_type = _classify_logcat_event(priority, tag, message)
        if event_type is None:
            continue

        events.append({
            "timestamp": timestamp,
            "pid": pid,
            "tid": tid,
            "priority": priority,
            "tag": tag,
            "message": message,
            "event_type": event_type,
        })

    return events


# ═══════════════════════════════════════════════════════════════════════════
# Recent tasks
# ═══════════════════════════════════════════════════════════════════════════

# Example:  Recent #0: Task{abc123 #42 type=standard A=10042:com.foo/.BarActivity U=0 …}
_RECENT_RE = re.compile(
    r"Recent\s+#(\d+):\s+Task\{.*?#(\d+)\s+.*?"
    r"A=\d+:([\w./]+)"
)
# Alternate simpler pattern for some Android versions:
#   * Recent #0: TaskRecord{hash #42 A com.example/.Main ...}
_RECENT_ALT_RE = re.compile(
    r"Recent\s+#(\d+):\s+TaskRecord\{.*?#(\d+)\s+[AI]\s+([\w./]+)"
)

_LAST_ACTIVE_RE = re.compile(r"lastActiveTime=(\d+)")


def parse_dumpsys_activity_recents(text: str) -> list[dict[str, Any]]:
    """Parse ``dumpsys activity recents`` for recently used apps.

    Returns list of dicts with *task_id*, *component*, *last_active_time_raw*.
    """
    results: list[dict[str, Any]] = []
    if not text:
        return results

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        m = _RECENT_RE.search(stripped) or _RECENT_ALT_RE.search(stripped)
        if not m:
            continue

        task_id = m.group(2)
        component = m.group(3)

        # Try to find lastActiveTime in nearby lines (within 10 lines ahead)
        last_active: str | None = None
        for look_line in lines[idx: idx + 10]:
            lm = _LAST_ACTIVE_RE.search(look_line)
            if lm:
                last_active = lm.group(1)
                break

        results.append({
            "task_id": task_id,
            "component": component,
            "last_active_time_raw": last_active,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Usage stats
# ═══════════════════════════════════════════════════════════════════════════

_USAGE_PKG_RE = re.compile(r"package=([\w.]+)")
_USAGE_TOTAL_RE = re.compile(r"totalTime(?:Visible|InForeground|Used)?=\"?(\d+)\"?", re.IGNORECASE)
_USAGE_LAST_RE = re.compile(r"lastTime(?:Visible|Used|Stamp)?=\"?(\d+)\"?", re.IGNORECASE)


def parse_dumpsys_usagestats(text: str) -> list[dict[str, Any]]:
    """Parse ``dumpsys usagestats`` for app usage data.

    Returns list of dicts with *package_name*, *total_time_ms*,
    *last_time_used_raw*.
    """
    results: list[dict[str, Any]] = []
    if not text:
        return results

    current_pkg: str | None = None
    current_total: int | None = None
    current_last: str | None = None

    for line in text.splitlines():
        stripped = line.strip()

        pkg_m = _USAGE_PKG_RE.search(stripped)
        if pkg_m:
            # Flush previous
            if current_pkg is not None:
                results.append({
                    "package_name": current_pkg,
                    "total_time_ms": current_total,
                    "last_time_used_raw": current_last,
                })
            current_pkg = pkg_m.group(1)
            current_total = None
            current_last = None

            # Check if totalTime and lastTime are on the same line
            tot_m = _USAGE_TOTAL_RE.search(stripped)
            if tot_m:
                try:
                    current_total = int(tot_m.group(1))
                except ValueError:
                    pass
            last_m = _USAGE_LAST_RE.search(stripped)
            if last_m:
                current_last = last_m.group(1)
            continue

        if current_pkg is not None:
            tot_m = _USAGE_TOTAL_RE.search(stripped)
            if tot_m and current_total is None:
                try:
                    current_total = int(tot_m.group(1))
                except ValueError:
                    pass
            last_m = _USAGE_LAST_RE.search(stripped)
            if last_m and current_last is None:
                current_last = last_m.group(1)

    # Flush last entry
    if current_pkg is not None:
        results.append({
            "package_name": current_pkg,
            "total_time_ms": current_total,
            "last_time_used_raw": current_last,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Network – ip addr
# ═══════════════════════════════════════════════════════════════════════════

_IFACE_RE = re.compile(r"^\d+:\s+(\S+?)[@:].*<(.+?)>")
_MAC_RE = re.compile(r"link/\w+\s+([\da-fA-F:]{17})")
_IPV4_RE = re.compile(r"inet\s+([\d.]+/\d+)")
_IPV6_RE = re.compile(r"inet6\s+([\da-fA-F:]+/\d+)")


def parse_ip_addr(text: str) -> list[dict[str, Any]]:
    """Parse ``ip addr`` output.

    Returns list of interface dicts with *name*, *state*, *mac*, *ipv4*
    (list), *ipv6* (list).
    """
    interfaces: list[dict[str, Any]] = []
    if not text:
        return interfaces

    current: dict[str, Any] | None = None

    for line in text.splitlines():
        # New interface line (starts with a number)
        m = _IFACE_RE.match(line)
        if m:
            if current is not None:
                interfaces.append(current)
            flags = m.group(2)
            state = "UP" if "UP" in flags else "DOWN"
            current = {
                "name": m.group(1),
                "state": state,
                "mac": None,
                "ipv4": [],
                "ipv6": [],
            }
            continue

        if current is None:
            continue

        mac_m = _MAC_RE.search(line)
        if mac_m:
            current["mac"] = mac_m.group(1)

        ipv4_m = _IPV4_RE.search(line)
        if ipv4_m:
            current["ipv4"].append(ipv4_m.group(1))

        ipv6_m = _IPV6_RE.search(line)
        if ipv6_m:
            current["ipv6"].append(ipv6_m.group(1))

    if current is not None:
        interfaces.append(current)

    return interfaces


# ═══════════════════════════════════════════════════════════════════════════
# Network – ip route
# ═══════════════════════════════════════════════════════════════════════════

def parse_ip_route(text: str) -> list[dict[str, str]]:
    """Parse ``ip route`` output.

    Example lines::

        default via 192.168.1.1 dev wlan0
        192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.42

    Returns list of dicts with *destination*, *gateway*, *device*, *src*.
    """
    routes: list[dict[str, str]] = []
    if not text:
        return routes

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        if not tokens:
            continue

        entry: dict[str, str] = {
            "destination": tokens[0],
            "gateway": "",
            "device": "",
            "src": "",
        }

        for i, tok in enumerate(tokens):
            if tok == "via" and i + 1 < len(tokens):
                entry["gateway"] = tokens[i + 1]
            elif tok == "dev" and i + 1 < len(tokens):
                entry["device"] = tokens[i + 1]
            elif tok == "src" and i + 1 < len(tokens):
                entry["src"] = tokens[i + 1]

        routes.append(entry)

    return routes


# ═══════════════════════════════════════════════════════════════════════════
# Network – netstat
# ═══════════════════════════════════════════════════════════════════════════

def parse_netstat(text: str) -> list[dict[str, str]]:
    """Parse ``netstat`` or ``netstat -tulnp`` output.

    Example lines::

        Proto Recv-Q Send-Q Local Address           Foreign Address         State
        tcp        0      0 0.0.0.0:5555            0.0.0.0:*               LISTEN
        tcp6       0      0 :::5555                 :::*                    LISTEN
        udp        0      0 0.0.0.0:68              0.0.0.0:*

    Returns list of dicts with *protocol*, *local_address*,
    *foreign_address*, *state*.
    """
    connections: list[dict[str, str]] = []
    if not text:
        return connections

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip headers
        if line.lower().startswith(("proto", "active")):
            continue

        parts = line.split()
        if len(parts) < 4:
            continue

        proto = parts[0]
        if proto not in ("tcp", "tcp6", "udp", "udp6", "raw", "raw6"):
            continue

        # Netstat columns: Proto Recv-Q Send-Q Local Foreign [State]
        # With -tulnp there may be extra columns at the end
        local_addr = parts[3]
        foreign_addr = parts[4] if len(parts) > 4 else ""
        state = parts[5] if len(parts) > 5 else ""

        connections.append({
            "protocol": proto,
            "local_address": local_addr,
            "foreign_address": foreign_addr,
            "state": state,
        })

    return connections


# ═══════════════════════════════════════════════════════════════════════════
# File listing (ls -laR)
# ═══════════════════════════════════════════════════════════════════════════

# ls -la lines look like:
# -rwxr-x---  1 root   shell     123456 2024-06-01 10:30 filename
# drwxr-xr-x  2 root   root        4096 2024-06-01 10:30 dirname
# lrwxrwxrwx  1 root   root          12 2024-06-01 10:30 link -> target
_LS_LINE_RE = re.compile(
    r"^([dlcbps\-][rwxsStT\-]{9})\s+"  # permissions
    r"\d+\s+"                            # link count
    r"\S+\s+"                            # owner
    r"\S+\s+"                            # group
    r"(\d+)\s+"                          # size
    r"(\d{4}-\d{2}-\d{2})\s+"           # date
    r"(\d{2}:\d{2})\s+"                 # time
    r"(.+)"                              # name (may include " -> target")
)


def parse_ls_output(text: str) -> list[dict[str, Any]]:
    """Parse ``ls -laR`` output from an ADB shell.

    Directory headers end with ``:``, file entries follow the standard
    ``ls -l`` format.

    Returns list of dicts with *path*, *filename*, *size*, *date*, *time*,
    *permissions*, *type* (``file``, ``dir``, ``link``).
    """
    results: list[dict[str, Any]] = []
    if not text:
        return results

    current_dir = ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Directory header:  /sdcard/DCIM:
        if stripped.endswith(":") and not stripped.startswith("-"):
            # Could be a directory path or "total N"
            candidate = stripped[:-1]
            if candidate.startswith("/") or candidate.startswith("."):
                current_dir = candidate
            continue

        # Skip "total N" lines
        if stripped.startswith("total "):
            continue

        m = _LS_LINE_RE.match(stripped)
        if not m:
            continue

        permissions = m.group(1)
        size = int(m.group(2))
        date = m.group(3)
        time_str = m.group(4)
        name_raw = m.group(5)

        # Determine type from first character of permissions
        perm_char = permissions[0]
        if perm_char == "d":
            ftype = "dir"
        elif perm_char == "l":
            ftype = "link"
        else:
            ftype = "file"

        # Handle symlinks: "name -> target"
        filename = name_raw.split(" -> ")[0].strip()

        # Build full path
        if current_dir:
            full_path = f"{current_dir}/{filename}"
        else:
            full_path = filename

        results.append({
            "path": full_path,
            "filename": filename,
            "size": size,
            "date": date,
            "time": time_str,
            "permissions": permissions,
            "type": ftype,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# WiFi info
# ═══════════════════════════════════════════════════════════════════════════

_SSID_RE = re.compile(r'mWifiInfo\s+.*?SSID:\s*"?(.+?)"?\s*[,\n]', re.IGNORECASE)
_SSID_ALT_RE = re.compile(r'SSID:\s*"?(.+?)"?\s*[,\s]', re.IGNORECASE)
_WIFI_MAC_RE = re.compile(r"(?:MAC|macAddress):\s*([\da-fA-F:]{17})", re.IGNORECASE)
_SAVED_NET_RE = re.compile(r'SSID\s*[:=]\s*"?(.+?)"?\s*$', re.IGNORECASE | re.MULTILINE)


def parse_dumpsys_wifi(text: str) -> dict[str, Any]:
    """Parse ``dumpsys wifi`` for current SSID, MAC, and saved networks.

    Returns dict with *current_ssid*, *mac_address*, *saved_networks*
    (list of SSID strings).
    """
    result: dict[str, Any] = {
        "current_ssid": None,
        "mac_address": None,
        "saved_networks": [],
    }
    if not text:
        return result

    # Current SSID
    m = _SSID_RE.search(text)
    if m:
        result["current_ssid"] = m.group(1).strip('"').strip()
    else:
        m = _SSID_ALT_RE.search(text)
        if m:
            result["current_ssid"] = m.group(1).strip('"').strip()

    # MAC address
    mac_m = _WIFI_MAC_RE.search(text)
    if mac_m:
        result["mac_address"] = mac_m.group(1)

    # Saved networks
    seen: set[str] = set()
    # Look in the "WifiConfigStore" or "Configured networks" section
    for m_net in _SAVED_NET_RE.finditer(text):
        ssid = m_net.group(1).strip('"').strip()
        if ssid and ssid not in seen and ssid != "<unknown ssid>":
            seen.add(ssid)
            result["saved_networks"].append(ssid)

    result["saved_networks"].sort()
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Battery stats (screen/charge/boot events)
# ═══════════════════════════════════════════════════════════════════════════

# +12h34m56s789ms — standard batterystats timestamp
_BATT_TS_RE = re.compile(r"[+\-]?\d+[hms\d]+")

_SCREEN_RE = re.compile(r"(\+[\dhms]+)\s.*\b(screen_on|screen_off)\b", re.IGNORECASE)
_CHARGE_RE = re.compile(r"(\+[\dhms]+)\s.*\b(plugged|unplugged|charging|not.?charging)\b", re.IGNORECASE)
_BOOT_RE = re.compile(r"(\+[\dhms]+)\s.*\b(boot|reboot|shutdown)\b", re.IGNORECASE)


def parse_dumpsys_battery_stats(text: str) -> list[dict[str, Any]]:
    """Parse ``dumpsys batterystats`` for screen-on/off, charging, and boot events.

    Returns list of dicts with *timestamp_raw*, *event_type*, *detail*.
    """
    events: list[dict[str, Any]] = []
    if not text:
        return events

    for line in text.splitlines():
        stripped = line.strip()

        for pattern, evt_type_prefix in [
            (_SCREEN_RE, "screen"),
            (_CHARGE_RE, "charge"),
            (_BOOT_RE, "boot"),
        ]:
            m = pattern.search(stripped)
            if m:
                events.append({
                    "timestamp_raw": m.group(1),
                    "event_type": f"{evt_type_prefix}_{m.group(2).lower().replace(' ', '_')}",
                    "detail": stripped,
                })
                break  # one event per line

    return events
