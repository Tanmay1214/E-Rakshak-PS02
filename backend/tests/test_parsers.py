"""Tests for erakshak.adb.parsers — parse ADB output without a real device."""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════
# getprop fixtures
# ══════════════════════════════════════════════════════════════════════

GETPROP_SAMPLE = """\
[ro.product.model]: [Pixel 6]
[ro.product.manufacturer]: [Google]
[ro.product.brand]: [google]
[ro.build.version.release]: [13]
[ro.build.version.sdk]: [33]
[ro.build.version.security_patch]: [2023-06-05]
[ro.build.fingerprint]: [google/oriole/oriole:13/TQ3A.230605.012/10204302:user/release-keys]
[ro.product.device]: [oriole]
[ro.product.board]: [oriole]
[ro.hardware]: [oriole]
[ro.build.id]: [TQ3A.230605.012]
[ro.build.display.id]: [TQ3A.230605.012]
[ro.serialno]: [1A2B3C4D5E]
[ro.boot.verifiedbootstate]: [green]
[ro.crypto.state]: [encrypted]
"""


def test_parse_getprop() -> None:
    from erakshak.adb.parsers import parse_getprop

    result = parse_getprop(GETPROP_SAMPLE)
    assert result["ro.product.model"] == "Pixel 6"
    assert result["ro.product.manufacturer"] == "Google"
    assert result["ro.build.version.release"] == "13"
    assert result["ro.build.version.sdk"] == "33"
    assert result["ro.build.version.security_patch"] == "2023-06-05"


def test_parse_getprop_empty() -> None:
    from erakshak.adb.parsers import parse_getprop

    result = parse_getprop("")
    assert result == {}


# ══════════════════════════════════════════════════════════════════════
# devices fixtures
# ══════════════════════════════════════════════════════════════════════

DEVICES_SAMPLE = """\
List of devices attached
R5CRA1GHTXE          device usb:1-1 product:x1q model:SM_G981B device:x1q transport_id:3
"""

DEVICES_MULTIPLE = """\
List of devices attached
R5CRA1GHTXE          device usb:1-1 product:x1q model:SM_G981B device:x1q
emulator-5554        device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64
"""


def test_parse_devices_single() -> None:
    from erakshak.adb.parsers import parse_adb_devices

    result = parse_adb_devices(DEVICES_SAMPLE)
    assert len(result) == 1
    assert result[0]["serial"] == "R5CRA1GHTXE"
    assert result[0]["state"] == "device"


def test_parse_devices_multiple() -> None:
    from erakshak.adb.parsers import parse_adb_devices

    result = parse_adb_devices(DEVICES_MULTIPLE)
    assert len(result) == 2


# ══════════════════════════════════════════════════════════════════════
# packages fixtures
# ══════════════════════════════════════════════════════════════════════

PACKAGES_SAMPLE = """\
package:/system/app/BasicDreams/BasicDreams.apk=com.android.dreams.basic versionCode:33 uid:10001
package:/data/app/~~abc123==/com.whatsapp-def456==/base.apk=com.whatsapp versionCode:223108214 uid:10234
package:/data/app/~~xyz==/org.telegram.messenger-abc==/base.apk=org.telegram.messenger versionCode:34567 uid:10235
"""


def test_parse_packages() -> None:
    from erakshak.adb.parsers import parse_packages

    result = parse_packages(PACKAGES_SAMPLE)
    assert len(result) == 3
    wa = [p for p in result if p["package_name"] == "com.whatsapp"]
    assert len(wa) == 1
    assert wa[0]["version_code"] == 223108214
    assert "base.apk" in wa[0]["apk_path"]


def test_parse_packages_empty() -> None:
    from erakshak.adb.parsers import parse_packages

    result = parse_packages("")
    assert result == []


# ══════════════════════════════════════════════════════════════════════
# account / email extraction
# ══════════════════════════════════════════════════════════════════════

ACCOUNT_DUMP_SAMPLE = """\
Accounts: 3
  Account {name=john.doe@gmail.com, type=com.google}
  Account {name=user@samsung.com, type=com.samsung.account}
  Account {name=test.user@outlook.com, type=com.microsoft.workaccount}

Registered authenticators:
  com.google (1 accounts)
  com.samsung.account (1 accounts)
  com.microsoft.workaccount (1 accounts)
"""


def test_parse_dumpsys_account() -> None:
    from erakshak.adb.parsers import parse_dumpsys_account

    result = parse_dumpsys_account(ACCOUNT_DUMP_SAMPLE)
    assert len(result["accounts"]) == 3
    assert any(a["name"] == "john.doe@gmail.com" for a in result["accounts"])


def test_extract_emails() -> None:
    from erakshak.adb.parsers import extract_emails

    result = extract_emails(ACCOUNT_DUMP_SAMPLE)
    assert "john.doe@gmail.com" in result
    assert "user@samsung.com" in result
    assert "test.user@outlook.com" in result
    assert len(result) == 3


def test_extract_emails_empty() -> None:
    from erakshak.adb.parsers import extract_emails

    result = extract_emails("no emails here")
    assert result == []


# ══════════════════════════════════════════════════════════════════════
# battery parsing
# ══════════════════════════════════════════════════════════════════════

BATTERY_SAMPLE = """\
Current Battery Service state:
  AC powered: false
  USB powered: true
  Wireless powered: false
  Max charging current: 500000
  status: 2
  health: 2
  present: true
  level: 85
  scale: 100
  voltage: 4200
  temperature: 280
  technology: Li-ion
"""


def test_parse_battery() -> None:
    from erakshak.adb.parsers import parse_battery_info

    result = parse_battery_info(BATTERY_SAMPLE)
    assert result["level"] == 85
    assert result["status"] == 2
    assert result["temperature"] == 280
