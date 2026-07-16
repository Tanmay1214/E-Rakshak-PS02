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
    """Execute an ADB command and return stdout. Redacts key material in exception/errors."""
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
        raise RuntimeError("No device found or ADB command failed. Plug in the phone and authorize USB debugging.")
    
    lines = [line for line in devices.split("\n") if line.strip()]
    if len(lines) < 2 or "device" not in lines[1]:
        raise RuntimeError("No device found. Plug in the phone and authorize USB debugging.")
    print("[+] Android device connected!")


def dump_ui() -> str | None:
    """BULLETPROOF UI DUMP: Uses --compressed and checks for success string."""
    for attempt in range(5):
        # Delete old file first
        run_adb("shell rm /sdcard/ui_dump.xml")
        
        # --compressed bypasses animation locks
        res = run_adb("shell uiautomator dump --compressed /sdcard/ui_dump.xml")
        
        # Android prints this string ONLY if the dump succeeded
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
        # If it failed, wait 1.5 seconds for animation to finish and try again
        time.sleep(1.5)
    return None


def swipe_up() -> None:
    """Swipes up to scroll the screen down."""
    print("  -> Swiping up to find the button...")
    run_adb("shell input swipe 540 1500 540 400 500")
    time.sleep(1)


def find_and_tap(xml_content: str | None, target_text: str) -> bool:
    """Parses the UI XML to find target text, calculates its center, and taps it."""
    if not xml_content:
        return False
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return False

    for node in root.iter('node'):
        node_text = (node.get('text', '') + " " + node.get('content-desc', '')).lower()
        if target_text.lower() in node_text:
            bounds = node.get('bounds', '')
            match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                
                # Ignore invisible/zero-size elements
                if x2 - x1 < 10 or y2 - y1 < 10:
                    continue
                
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                print(f"  -> Found '{target_text}'. Tapping...")
                run_adb(f"shell input tap {center_x} {center_y}")
                time.sleep(3) # Wait 3 seconds for screen to load
                return True
    return False


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
    
    size = run_adb("shell wm size")
    w, h = 1080, 1920
    if size:
        match = re.search(r'(\d+)x(\d+)', size)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
    
    print("  -> Long pressing key area...")
    x, y = int(w * 0.5), int(h * 0.45)
    run_adb(f"shell input swipe {x} {y} {x} {y} 1000")
    time.sleep(2)
    
    print("  -> Looking for Copy button...")
    xml = dump_ui()
    if not find_and_tap(xml, "Copy"):
        find_and_tap(xml, "Copy all")
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
    """Core WhatsApp UI automation flow. Key printing removed for forensic security."""
    print("\n" + "="*50)
    print("🤖 INITIATING ROBUST UI AUTOMATION 🤖")
    print("DO NOT TOUCH THE PHONE. The script is controlling it.")
    print("="*50 + "\n")
    
    # 1. Open WhatsApp
    print("[*] Opening WhatsApp...")
    run_adb("shell am start -n com.whatsapp/.HomeActivity")
    time.sleep(4)
    
    # 2. Tap the 3-dot menu (More options)
    print("[*] Opening Main Menu...")
    xml = dump_ui()
    if not find_and_tap(xml, "More options"):
        # Fallback coordinate if XML dump has issues
        w, h = 1080, 1920
        size = run_adb("shell wm size")
        if size:
            match = re.search(r'(\d+)x(\d+)', size)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
        tap_x = int(w * 0.9)
        tap_y = int(h * 0.08)
        run_adb(f"shell input tap {tap_x} {tap_y}")
        time.sleep(3)
    
    # 3. Tap "Settings"
    print("[*] Tapping Settings...")
    xml = dump_ui()
    if not find_and_tap(xml, "Settings"):
        swipe_up()
        xml = dump_ui()
        find_and_tap(xml, "Settings")
    
    # 4. Tap "Chats"
    print("[*] Tapping Chats...")
    xml = dump_ui()
    if not find_and_tap(xml, "Chats"):
        swipe_up()
        xml = dump_ui()
        find_and_tap(xml, "Chats")
    
    # 5. Tap "Chat Backup"
    print("[*] Tapping Chat Backup...")
    xml = dump_ui()
    if not find_and_tap(xml, "Chat backup"):
        swipe_up()
        xml = dump_ui()
        find_and_tap(xml, "Chat backup")
    
    # 6. Tap "End-to-End Encrypted Backup"
    print("[*] Tapping End-to-End Encrypted Backup...")
    xml = dump_ui()
    if not find_and_tap(xml, "End-to-end encrypted backup"):
        swipe_up()
        xml = dump_ui()
        find_and_tap(xml, "End-to-end encrypted backup")
    
    # 7. Tap "More options" on the E2EE screen
    print("[*] Looking for 'More options' button on E2EE screen...")
    xml = dump_ui()
    if not find_and_tap(xml, "More options"):
        find_and_tap(xml, "Change password")
    
    # 8. Tap "64 digit encryption key"
    print("[*] Selecting '64-digit encryption key' option...")
    xml = dump_ui()
    if not find_and_tap(xml, "64-digit encryption key"):
        swipe_up()
        xml = dump_ui()
        find_and_tap(xml, "64-digit encryption key")
    
    # 9. Tap "Generate" or "Create"
    print("[*] Looking for Generate/Create button...")
    xml = dump_ui()
    if not find_and_tap(xml, "Generate"):
        xml = dump_ui()
        find_and_tap(xml, "Create")
    
    # 10. Scrape the key
    print("[*] Scraping screen for 64-digit key...")
    hex_key = None
    for attempt in range(3):
        xml = dump_ui()
        hex_key = scrape_64_digit_key(xml)
        if hex_key:
            break
        print("  -> Key not found yet, waiting 2 seconds...")
        time.sleep(2)
    
    # FALLBACK: Clipboard method
    if not hex_key:
        hex_key = scrape_via_clipboard()
    
    if hex_key:
        print("\n[✅ SUCCESS] 64-digit key scraped automatically!")
        print("    Key: <REDACTED_KEY>")  # Redacted output to avoid leak
        
        # Close WhatsApp after scraping the key
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
    
    # Validations
    key = key.strip().lower()
    if not re.match(r"^[0-9a-f]{64}$", key):
        raise ValueError("Captured key format is invalid. Must be a 64-character hexadecimal string.")
    
    return key
