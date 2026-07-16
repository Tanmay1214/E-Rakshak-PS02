"""WhatsApp UI Key Capture Module for E-RAKSHAK.

Automates WhatsApp UI navigation over ADB to retrieve the 64-character
End-to-End Encrypted Backup encryption key.
"""

from __future__ import annotations

import os
import sys
import subprocess
import re
import time
import xml.etree.ElementTree as ET

ADB_PATH = "adb"
DEVICE_SERIAL = None


def run_adb(command: str) -> str | None:
    """Execute an ADB command and return stdout."""
    adb_cmd = f"{ADB_PATH}"
    if DEVICE_SERIAL:
        adb_cmd += f" -s {DEVICE_SERIAL}"
    try:
        result = subprocess.run(
            f"{adb_cmd} {command}",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode != 0 and "error" in result.stderr.lower():
            return None
        return result.stdout.strip()
    except Exception as e:
        raise RuntimeError(f"ADB command failed: {str(e)}")


def check_device() -> None:
    """Verify that the target Android device is connected and authorized."""
    print("[*] Checking for connected device...")
    devices = run_adb("devices")
    if not devices:
        raise RuntimeError("No device found or ADB command failed.")
    
    lines = [line for line in devices.split("\n") if line.strip()]
    if len(lines) < 2 or "device" not in lines[1]:
        if len(lines) >= 2 and "unauthorized" in lines[1]:
            raise RuntimeError("Device is connected but UNAUTHORIZED. Please tap 'Allow' on the phone screen.")
        raise RuntimeError("No device found. Plug in the phone and authorize USB debugging.")
    print("[+] Android device connected!")


def get_screen_size() -> tuple[int, int]:
    """Retrieves screen size width and height from the device."""
    size = run_adb("shell wm size")
    w, h = 1080, 1920
    if size:
        match = re.search(r'(\d+)x(\d+)', size)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
    return w, h


def dump_ui() -> str | None:
    """BULLETPROOF UI DUMP: Uses --compressed and checks for success string."""
    for attempt in range(3):
        run_adb("shell rm /sdcard/ui_dump.xml")
        res = run_adb("shell uiautomator dump --compressed /sdcard/ui_dump.xml")
        if res and "dumped to" in res:
            run_adb("pull /sdcard/ui_dump.xml ui_dump.xml")
            try:
                if os.path.exists("ui_dump.xml"):
                    with open("ui_dump.xml", "r", encoding="utf-8") as f:
                        xml_content = f.read()
                    os.remove("ui_dump.xml")
                    if len(xml_content) > 100: 
                        return xml_content
            except Exception:
                pass
        time.sleep(1.5)
    return None


def tap_node(node) -> bool:
    """Extracts bounds from an XML node and taps it."""
    bounds = node.get('bounds', '')
    match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if match:
        x1, y1, x2, y2 = map(int, match.groups())
        # Ignore invisible/zero-size elements
        if x2 - x1 < 10 or y2 - y1 < 10:
            return False
        
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        print(f"  -> Found target. Tapping at ({center_x}, {center_y})")
        run_adb(f"shell input tap {center_x} {center_y}")
        time.sleep(2.5)
        return True
    return False


def find_and_tap(xml_content: str | None, target_text: str) -> bool:
    """Precision XML matcher. Prioritizes exact text matches over messy content-desc."""
    if not xml_content:
        return False
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return False

    nodes = list(root.iter('node'))
    target_lower = target_text.lower()

    # Pass 1: Exact match on 'text' attribute (e.g., text="Chats")
    for node in nodes:
        if node.get('text', '').strip().lower() == target_lower:
            if tap_node(node): return True

    # Pass 2: Partial match on 'text' attribute
    for node in nodes:
        t = node.get('text', '').strip().lower()
        if target_lower in t:
            if tap_node(node): return True

    # Pass 3: Exact match on 'content-desc' attribute
    for node in nodes:
        if node.get('content-desc', '').strip().lower() == target_lower:
            if tap_node(node): return True

    # Pass 4: Partial match on 'content-desc' attribute (e.g., desc="Chats,Theme...")
    for node in nodes:
        d = node.get('content-desc', '').strip().lower()
        if target_lower in d:
            if tap_node(node): return True

    return False


def smart_tap(target_text: str, fallback_x_pct: float, fallback_y_pct: float, w: int, h: int, timeout: int = 8) -> bool:
    """Waits for text to appear. If XML fails, falls back to coordinates."""
    print(f"[*] Looking for '{target_text}'...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        xml = dump_ui()
        if find_and_tap(xml, target_text):
            return True
        time.sleep(1.5)
        
    print(f"  -> XML failed. Falling back to coordinates for '{target_text}'...")
    tap_x = int(w * fallback_x_pct)
    tap_y = int(h * fallback_y_pct)
    run_adb(f"shell input tap {tap_x} {tap_y}")
    time.sleep(3)
    return True


def scrape_64_digit_key(xml_content: str | None) -> str | None:
    """Extracts ONLY from text nodes that are purely hex characters."""
    if not xml_content:
        return None
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None
        
    hex_string = ""
    for node in root.iter('node'):
        t = node.get('text', '').strip()
        if not t:
            continue
        
        if re.match(r'^[0-9a-fA-F ]+$', t):
            hex_string += t.replace(" ", "")
            
    if len(hex_string) >= 64:
        return hex_string[:64]
    return None


def scrape_via_clipboard() -> str | None:
    """Clipboard method: Long press -> Copy -> Read Clipboard."""
    print("\n[*] XML Parse failed. Falling back to Clipboard Method...")
    
    w, h = get_screen_size()
    
    print("  -> Long pressing key area...")
    x, y = int(w * 0.5), int(h * 0.45)
    run_adb(f"shell input swipe {x} {y} {x} {y} 1000")
    time.sleep(2)
    
    print("  -> Looking for Copy button...")
    xml = dump_ui()
    smart_tap("Copy", 0.5, 0.5, w, h)
    time.sleep(2)
    
    print("  -> Reading Android clipboard...")
    result = run_adb("shell service call clipboard 1 i32 1 i32 0 i32 0")
    if result:
        matches = re.findall(r"'([^']*)'", result)
        combined = "".join(matches)
        hex_only = re.sub(r'[^0-9a-fA-F]', '', combined)
        if len(hex_only) >= 64:
            return hex_only[:64]
            
    return None


def automate_whatsapp_ui() -> str | None:
    """Core WhatsApp UI automation flow."""
    print("\n" + "="*50)
    print("[!] INITIATING ROBUST UI AUTOMATION [!]")
    print("DO NOT TOUCH THE PHONE. The script is controlling it.")
    print("="*50 + "\n")
    
    w, h = get_screen_size()
    
    print("[*] Opening WhatsApp...")
    run_adb("shell am start -n com.whatsapp/.HomeActivity")
    time.sleep(4)
    
    print("[*] Opening Main Menu...")
    smart_tap("More options", 0.93, 0.07, w, h)
    
    print("[*] Tapping Settings...")
    smart_tap("Settings", 0.75, 0.85, w, h)
    
    print("[*] Tapping Chats...")
    smart_tap("Chats", 0.5, 0.45, w, h)
    
    print("[*] Tapping Chat Backup...")
    smart_tap("Chat backup", 0.5, 0.65, w, h)
    
    print("[*] Tapping End-to-End Encrypted Backup...")
    smart_tap("End-to-end encrypted backup", 0.5, 0.45, w, h)
    
    print("[*] Looking for 'More options' button on E2EE screen...")
    if not smart_tap("More options", 0.93, 0.07, w, h):
        smart_tap("Change password", 0.93, 0.07, w, h)
    
    print("[*] Selecting '64-digit encryption key' option...")
    smart_tap("64-digit encryption key", 0.5, 0.60, w, h)
    
    print("[*] Looking for Generate/Create button...")
    if not smart_tap("Generate", 0.85, 0.90, w, h):
        smart_tap("Create", 0.85, 0.90, w, h)
    
    print("[*] Scraping screen for 64-digit key...")
    hex_key = None
    for attempt in range(5):
        xml = dump_ui()
        hex_key = scrape_64_digit_key(xml)
        if hex_key:
            break
        print("  -> Key not found yet, waiting 2 seconds...")
        time.sleep(2)
    
    if not hex_key:
        hex_key = scrape_via_clipboard()
    
    if hex_key:
        print("\n[SUCCESS] 64-digit key scraped automatically!")
        print("    Key: <REDACTED_KEY>")
        
        print("[*] Closing WhatsApp...")
        run_adb("shell am force-stop com.whatsapp")
        print("[*] WhatsApp closed successfully.")
    else:
        print("[-] Failed to scrape key. You may need to navigate manually.")
        
    return hex_key


def capture_whatsapp_backup_key(adb_path: str = "adb", serial: str | None = None) -> str:
    """Core public API to retrieve and validate WhatsApp encryption key."""
    global ADB_PATH, DEVICE_SERIAL
    ADB_PATH = adb_path
    DEVICE_SERIAL = serial
    
    check_device()
    key = automate_whatsapp_ui()
    if not key:
        raise RuntimeError("Failed to capture WhatsApp backup encryption key via UI automation.")
    
    key = key.strip().lower()
    if not re.match(r"^[0-9a-f]{64}$", key):
        raise ValueError("Captured key format is invalid. Must be a 64-character hexadecimal string.")
    
    return key


if __name__ == "__main__":
    try:
        captured_key = capture_whatsapp_backup_key()
        print("\n" + "="*50)
        print("Key successfully captured for E-RAKSHAK pipeline.")
        print(f"Key Hash: {captured_key[:8]}...{captured_key[-8:]}")
        print("="*50)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        sys.exit(1)