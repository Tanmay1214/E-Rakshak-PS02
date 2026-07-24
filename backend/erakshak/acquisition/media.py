"""Inventory and optionally pull media files from the device.

Scans a configurable list of media-bearing directories on the device,
builds an index of every file found, and — when explicitly requested —
pulls files into the case folder within a caller-specified byte budget.

Target folders (default)
------------------------
- ``/sdcard/DCIM``
- ``/sdcard/Pictures``
- ``/sdcard/Movies``
- ``/sdcard/Download``
- ``/sdcard/WhatsApp/Media``
- ``/sdcard/Android/media``

Output artefacts
----------------
- ``derived/media_index.jsonl`` – one JSON object per file
- Pulled files (if enabled) go into ``raw/media/``
"""

from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erakshak.adb.client import ADBClient
    from erakshak.case.audit import AuditLogger
    from erakshak.case.case_folder import CaseFolder
    from erakshak.case.manifest import ManifestWriter


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_local_dest(base_dir: Path, filename: str, ext: str) -> Path:
    """Return a local path that does not collide with existing files.

    Appends ``_1``, ``_2``, … to the stem until a free name is found.
    """
    dest = base_dir / filename
    counter = 1
    stem = Path(filename).stem
    while dest.exists():
        dest = base_dir / f"{stem}_{counter}{ext}"
        counter += 1
    return dest


def extract_gps_from_exif(filepath: Path) -> dict | None:
    """Extract GPS coordinates and metadata from a JPEG file using pure Python."""
    try:
        with open(filepath, 'rb') as f:
            # Check SOI (Start of Image) marker
            soi = f.read(2)
            if soi != b'\xff\xd8':
                return None
                
            # Search for APP1 segment (EXIF marker FFE1)
            marker = b''
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    break
                if marker[0] != 0xFF:
                    # Sync issue, look for next FF
                    continue
                if marker[1] == 0xE1:
                    # Found APP1 segment!
                    break
                elif marker[1] in (0xD9, 0xDA):
                    # SOS (Start of Scan) or EOI reached without APP1
                    return None
                else:
                    # Skip this segment
                    len_bytes = f.read(2)
                    if len(len_bytes) < 2:
                        return None
                    seg_len = int.from_bytes(len_bytes, byteorder='big') - 2
                    f.seek(seg_len, 1)
                    
            if len(marker) < 2 or marker[1] != 0xE1:
                return None
                
            # Read segment length
            len_bytes = f.read(2)
            if len(len_bytes) < 2:
                return None
            seg_len = int.from_bytes(len_bytes, byteorder='big')
            
            # Read EXIF header
            exif_header = f.read(6)
            if exif_header != b'Exif\x00\x00':
                return None
                
            # Read TIFF header
            tiff_start = f.tell()
            byte_order_bytes = f.read(2)
            if byte_order_bytes == b'II':
                byte_order = 'little'
            elif byte_order_bytes == b'MM':
                byte_order = 'big'
            else:
                return None
                
            # Read TIFF magic number (42)
            magic = f.read(2)
            magic_val = int.from_bytes(magic, byteorder=byte_order)
            if magic_val != 42:
                return None
                
            # Read offset to first IFD
            ifd_offset_bytes = f.read(4)
            ifd_offset = int.from_bytes(ifd_offset_bytes, byteorder=byte_order)
            
            # Read IFD helper
            def read_ifd(offset):
                f.seek(tiff_start + offset)
                num_entries_bytes = f.read(2)
                if len(num_entries_bytes) < 2:
                    return {}
                num_entries = int.from_bytes(num_entries_bytes, byteorder=byte_order)
                
                tags = {}
                for _ in range(num_entries):
                    entry = f.read(12)
                    if len(entry) < 12:
                        break
                    tag = int.from_bytes(entry[0:2], byteorder=byte_order)
                    val_type = int.from_bytes(entry[2:4], byteorder=byte_order)
                    count = int.from_bytes(entry[4:8], byteorder=byte_order)
                    val_offset = int.from_bytes(entry[8:12], byteorder=byte_order)
                    tags[tag] = (val_type, count, val_offset, entry[8:12])
                return tags

            ifd0_tags = read_ifd(ifd_offset)
            
            # GPS Info IFD tag is 0x8825 (34853)
            if 0x8825 in ifd0_tags:
                gps_offset = ifd0_tags[0x8825][2]
                gps_tags = read_ifd(gps_offset)
                
                def get_value(tag_info):
                    v_type, count, v_offset, raw_offset_bytes = tag_info
                    curr_pos = f.tell()
                    
                    types_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
                    size = types_sizes.get(v_type, 1) * count
                    
                    if size <= 4:
                        data_bytes = raw_offset_bytes[:size]
                    else:
                        f.seek(tiff_start + v_offset)
                        data_bytes = f.read(size)
                        
                    f.seek(curr_pos)
                    
                    if v_type == 2:  # ASCII
                        return data_bytes.decode('ascii', errors='ignore').strip('\x00')
                    elif v_type == 5 or v_type == 10:  # Rational
                        rationals = []
                        for i in range(count):
                            num = int.from_bytes(data_bytes[i*8 : i*8+4], byteorder=byte_order)
                            den = int.from_bytes(data_bytes[i*8+4 : i*8+8], byteorder=byte_order)
                            rationals.append(num / den if den != 0 else 0)
                        return rationals[0] if count == 1 else rationals
                    elif v_type in (3, 4, 9):  # short, long, slong
                        ints = []
                        elem_size = 2 if v_type == 3 else 4
                        for i in range(count):
                            ints.append(int.from_bytes(data_bytes[i*elem_size : (i+1)*elem_size], byteorder=byte_order))
                        return ints[0] if count == 1 else ints
                    return data_bytes

                # Latitude
                lat_val = None
                if 2 in gps_tags:
                    lat_deg_min_sec = get_value(gps_tags[2])
                    if isinstance(lat_deg_min_sec, list) and len(lat_deg_min_sec) >= 3:
                        lat_val = lat_deg_min_sec[0] + lat_deg_min_sec[1]/60.0 + lat_deg_min_sec[2]/3600.0
                    elif isinstance(lat_deg_min_sec, (int, float)):
                        lat_val = lat_deg_min_sec
                lat_ref = 'N'
                if 1 in gps_tags:
                    lat_ref = get_value(gps_tags[1])
                if lat_val and lat_ref == 'S':
                    lat_val = -lat_val
                    
                # Longitude
                lon_val = None
                if 4 in gps_tags:
                    lon_deg_min_sec = get_value(gps_tags[4])
                    if isinstance(lon_deg_min_sec, list) and len(lon_deg_min_sec) >= 3:
                        lon_val = lon_deg_min_sec[0] + lon_deg_min_sec[1]/60.0 + lon_deg_min_sec[2]/3600.0
                    elif isinstance(lon_deg_min_sec, (int, float)):
                        lon_val = lon_deg_min_sec
                lon_ref = 'E'
                if 3 in gps_tags:
                    lon_ref = get_value(gps_tags[3])
                if lon_val and lon_ref == 'W':
                    lon_val = -lon_val
                    
                # Altitude
                alt_val = None
                if 6 in gps_tags:
                    alt_val = get_value(gps_tags[6])
                alt_ref = 0
                if 5 in gps_tags:
                    alt_ref_bytes = get_value(gps_tags[5])
                    if isinstance(alt_ref_bytes, bytes) and len(alt_ref_bytes) > 0:
                        alt_ref = alt_ref_bytes[0]
                if alt_val and alt_ref == 1:
                    alt_val = -alt_val
                    
                # Date/Time
                date_stamp = ""
                if 29 in gps_tags:
                    date_stamp = get_value(gps_tags[29])
                time_stamp = ""
                if 7 in gps_tags:
                    ts_vals = get_value(gps_tags[7])
                    if isinstance(ts_vals, list) and len(ts_vals) >= 3:
                        time_stamp = f"{int(ts_vals[0]):02d}:{int(ts_vals[1]):02d}:{int(ts_vals[2]):02d}"
                        
                if lat_val is not None and lon_val is not None:
                    return {
                        "latitude": lat_val,
                        "longitude": lon_val,
                        "altitude": alt_val,
                        "date_stamp": date_stamp,
                        "time_stamp": time_stamp
                    }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def acquire_media(
    adb: "ADBClient",
    case_folder: "CaseFolder",
    manifest: "ManifestWriter",
    audit: "AuditLogger",
    *,
    media_days: int = 7,
    media_max_bytes: int = 2_147_483_648,
    pull_media: bool = False,
) -> dict:
    """Inventory and optionally pull media files.

    Parameters
    ----------
    adb : ADBClient
        Connected ADB wrapper.
    case_folder : CaseFolder
        Open case folder.
    manifest : ManifestWriter
        Manifest writer.
    audit : AuditLogger
        Audit trail logger.
    media_days : int, optional
        Only consider files modified within the last *media_days* days
        (advisory — used for filtering if timestamps are parseable).
        Defaults to ``7``.
    media_max_bytes : int, optional
        Maximum total bytes to pull.  Defaults to 2 GiB.
    pull_media : bool, optional
        If ``True``, actually pull files from the device into
        ``raw/media/``.  If ``False`` (the default), only build the
        inventory — no files are transferred.

    Returns
    -------
    dict
        Summary with ``status``, ``files_inventoried``,
        ``files_pulled``, ``total_bytes_pulled``, ``warnings``.
    """
    from erakshak.adb.parsers import parse_ls_output
    from erakshak.case.hashing import hash_file
    from erakshak.config.defaults import (
        MEDIA_TARGET_FOLDERS,
        MEDIA_PULL_TIMEOUT,
        DEFAULT_ADB_TIMEOUT,
        STATUS_ACQUIRED,
    )

    results: dict = {
        "status": STATUS_ACQUIRED,
        "files_inventoried": 0,
        "files_pulled": 0,
        "total_bytes_pulled": 0,
        "warnings": [],
    }

    all_files: list[dict] = []

    # ---- 1. List files in each target folder --------------------------------
    for folder in MEDIA_TARGET_FOLDERS:
        folder_label = folder.rstrip("/").split("/")[-1]
        ls_result = adb.shell(
            ["ls", "-laR", folder],
            timeout=DEFAULT_ADB_TIMEOUT,
            audit_action=f"media_ls_{folder_label}",
        )

        if ls_result.return_code != 0:
            stderr_lower = ls_result.stderr.lower()
            if "no such file" in stderr_lower or "not found" in stderr_lower:
                # Folder simply does not exist on this device — expected.
                continue
            results["warnings"].append(
                f"ls failed for {folder}: {ls_result.stderr[:200]}"
            )
            continue

        files = parse_ls_output(ls_result.stdout)
        for entry in files:
            entry["source_folder"] = folder
        all_files.extend(files)

    # ---- 2. Build media index (skip directory entries) ----------------------
    media_index: list[dict] = []
    bytes_pulled = 0

    for f_entry in all_files:
        if f_entry.get("type") == "directory":
            continue

        source_path: str = f_entry.get("path", "")
        filename: str = f_entry.get("filename", "")
        ext: str = Path(filename).suffix.lower() if filename else ""
        mime_type: str | None = (
            mimetypes.guess_type(filename)[0] if filename else None
        )
        size: int | None = f_entry.get("size")
        modified: str | None = f_entry.get("datetime")

        entry: dict = {
            "source_path": source_path,
            "filename": filename,
            "extension": ext,
            "mime_type": mime_type,
            "size": size,
            "modified_time": modified,
            "source_folder": f_entry.get("source_folder", ""),
            "pulled": False,
            "local_path": None,
            "sha256": None,
        }

        # ---- optional pull --------------------------------------------------
        if pull_media and size is not None and source_path:
            if bytes_pulled + (size or 0) <= media_max_bytes:
                local_dest = _safe_local_dest(
                    case_folder.raw_media_dir, filename, ext,
                )
                pull_result = adb.pull(
                    source_path,
                    str(local_dest),
                    timeout=MEDIA_PULL_TIMEOUT,
                    audit_action=f"media_pull_{filename}",
                )
                if pull_result.return_code == 0 and local_dest.exists():
                    entry["pulled"] = True
                    entry["local_path"] = str(local_dest)
                    entry["sha256"] = hash_file(local_dest)
                    bytes_pulled += local_dest.stat().st_size
                    results["files_pulled"] += 1
                    manifest.add_file(
                        "media_file", "adb_pull", source_path, local_dest,
                    )
                else:
                    results["warnings"].append(
                        f"pull failed: {source_path}"
                    )

        entry["gps_info"] = None
        media_index.append(entry)

    # ---- 3. Extract GPS coordinates from pulled media files -----------------
    gps_locations: list[dict] = []
    for entry in media_index:
        if entry.get("pulled") and entry.get("local_path"):
            local_dest = Path(entry["local_path"])
            if entry["extension"] in (".jpg", ".jpeg"):
                gps_info = extract_gps_from_exif(local_dest)
                if gps_info:
                    entry["gps_info"] = gps_info
                    gps_locations.append({
                        "filename": entry["filename"],
                        "source_path": entry["source_path"],
                        "local_path": entry["local_path"],
                        "latitude": gps_info["latitude"],
                        "longitude": gps_info["longitude"],
                        "altitude": gps_info["altitude"],
                        "timestamp": f"{gps_info['date_stamp']} {gps_info['time_stamp']}".strip()
                    })

    # ---- 4. Write derived/media_index.jsonl ---------------------------------
    results["files_inventoried"] = len(media_index)
    results["total_bytes_pulled"] = bytes_pulled

    index_path: Path = case_folder.derived_dir / "media_index.jsonl"
    with open(index_path, "w", encoding="utf-8") as fh:
        for entry in media_index:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    manifest.add_file(
        "media_index", "parsed", "ls -laR + inventory", index_path,
    )

    # ---- 5. Write derived/media_gps_locations.json --------------------------
    gps_locations_path: Path = case_folder.derived_dir / "media_gps_locations.json"
    with open(gps_locations_path, "w", encoding="utf-8") as fh:
        json.dump({"media_gps_locations": gps_locations}, fh, indent=2, ensure_ascii=False)
    manifest.add_file(
        "media_gps_locations", "parsed", "EXIF parser", gps_locations_path,
        status=STATUS_ACQUIRED if gps_locations else "No GPS coordinates found",
    )

    # ---- 6. Finalise --------------------------------------------------------
    if results["warnings"]:
        results["status"] = "partial"

    audit.log(
        action="media_acquired",
        command_category="media",
        result=results["status"],
        output_path=str(index_path),
    )

    return results
