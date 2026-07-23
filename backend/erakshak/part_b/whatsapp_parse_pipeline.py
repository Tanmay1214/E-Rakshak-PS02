"""WhatsApp Exporter Parsing Pipeline Orchestration.

Invokes wtsexporter to parse plaintext database and stages outputs into manifest,
hashes, and preview summaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Any

from erakshak.case.hashing import hash_file
from erakshak.part_b.whatsapp_exporter_runner import run_whatsapp_chat_exporter
from erakshak.part_b.whatsapp_pipeline import (
    append_audit_event,
    append_manifest_record,
    append_sha256sum
)


def parse_decrypted_whatsapp(
    case_id: str,
    exhibit_id: str,
    output_root: Path,
    input_dir: Optional[Path] = None,
    wa_db: Optional[Path] = None,
    media_dir: Optional[Path] = None,
    vcard_path: Optional[Path] = None,
    time_offset: Optional[int] = None,
    filter_date: Optional[str] = None,
    filter_date_format: Optional[str] = None,
    source: Optional[str] = None,
    package: Optional[str] = "com.whatsapp"
) -> dict[str, Any]:
    """Executes the complete WhatsApp parsing and export pipeline."""
    exhibit_path = Path(output_root) / case_id / exhibit_id
    acquisition_dir = exhibit_path / "acquisition"
    audit_path = acquisition_dir / "audit.jsonl"
    manifest_path = acquisition_dir / "acquisition_manifest.jsonl"
    sha256sums_path = exhibit_path / "hashes" / "sha256sums.txt"

    warnings = []

    if source == "rooted":
        if not package:
            package = "com.whatsapp"
        if input_dir is None:
            input_dir = exhibit_path / "processed" / "apps" / "whatsapp" / "rooted" / package
        
        input_dir = Path(input_dir)
        msgstore_db = input_dir / "msgstore.db"
        
        if not msgstore_db.is_file():
            fail_action = "whatsapp_root_parse_failed"
            append_audit_event(
                audit_path=audit_path,
                case_id=case_id,
                exhibit_id=exhibit_id,
                action=fail_action,
                result="failed",
                details={
                    "parser": "Whatsapp-Chat-Exporter",
                    "source_folder": str(input_dir),
                    "output_folder": str(exhibit_path / "derived" / "whatsapp_exporter" / "rooted" / package),
                    "msgstore_present": "no",
                    "wa_db_present": "no",
                    "media_folder_present": "no",
                    "generated_file_count": 0,
                    "warnings": ["msgstore.db not found"],
                    "error": "Rooted WhatsApp msgstore.db not found. Run acquire-whatsapp-root or import-whatsapp-root first."
                }
            )
            raise FileNotFoundError(
                "Rooted WhatsApp msgstore.db not found. Run acquire-whatsapp-root or import-whatsapp-root first."
            )
            
        try:
            with open(msgstore_db, "rb") as f:
                header = f.read(15)
            is_sqlite = (header == b"SQLite format 3")
        except Exception:
            is_sqlite = False
            
        if not is_sqlite:
            fail_action = "whatsapp_root_parse_failed"
            append_audit_event(
                audit_path=audit_path,
                case_id=case_id,
                exhibit_id=exhibit_id,
                action=fail_action,
                result="failed",
                details={
                    "parser": "Whatsapp-Chat-Exporter",
                    "source_folder": str(input_dir),
                    "output_folder": str(exhibit_path / "derived" / "whatsapp_exporter" / "rooted" / package),
                    "msgstore_present": "yes",
                    "wa_db_present": "no",
                    "media_folder_present": "no",
                    "generated_file_count": 0,
                    "warnings": ["msgstore.db is not SQLite"],
                    "error": "Rooted WhatsApp msgstore.db is not a valid plaintext SQLite database."
                }
            )
            raise ValueError(
                "Rooted WhatsApp msgstore.db is not a valid plaintext SQLite database."
            )
            
        wa_db_path = input_dir / "wa.db"
        if wa_db_path.is_file():
            wa_db = wa_db_path
        else:
            wa_db = None
            warn_msg = "wa.db not found; contact/name enrichment may be limited."
            print(f"\n[WARNING] {warn_msg}\n")
            warnings.append(warn_msg)
            
        media_path = input_dir / "media"
        if media_path.is_dir():
            media_dir = media_path
        else:
            media_dir = None
            warn_msg = "media folder not found; media previews may be limited."
            print(f"\n[WARNING] {warn_msg}\n")
            warnings.append(warn_msg)


    # 1. Start Audit
    start_action = "whatsapp_root_parse_started" if source == "rooted" else "whatsapp_exporter_parse_started"
    append_audit_event(
        audit_path=audit_path,
        case_id=case_id,
        exhibit_id=exhibit_id,
        action=start_action,
        result="started",
        details={
            "parser": "Whatsapp-Chat-Exporter",
            "source_folder": str(input_dir) if input_dir else "",
            "output_folder": str(exhibit_path / "derived" / "whatsapp_exporter" / "rooted" / package) if source == "rooted" else str(exhibit_path / "derived" / "whatsapp_exporter" / "html"),
            "msgstore_present": "yes" if input_dir and (input_dir / "msgstore.db").is_file() else "no",
            "wa_db_present": "yes" if wa_db else "no",
            "media_folder_present": "yes" if media_dir else "no"
        }
    )

    # 1.5 Generate vCard from Part A contacts.jsonl if not explicitly provided
    generated_vcard_path = None
    if vcard_path is None:
        contacts_jsonl = exhibit_path / "derived" / "contacts.jsonl"
        if contacts_jsonl.is_file():
            try:
                import re
                contacts_list = []
                phone_keys = ["phone", "number", "data1", "phone_number", "formatted_number", "raw_number"]
                name_keys = ["display_name", "name", "display_name_alt", "sort_key"]
                
                with open(contacts_jsonl, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            if not isinstance(record, dict):
                                continue
                            
                            # Extract name
                            name = None
                            for nk in name_keys:
                                if nk in record and record[nk] and str(record[nk]).strip() and str(record[nk]) != "NULL":
                                    name = str(record[nk]).strip()
                                    break
                                    
                            # Extract phone
                            phone = None
                            for pk in phone_keys:
                                if pk in record and record[pk] and str(record[pk]).strip() and str(record[pk]) != "NULL":
                                    phone = str(record[pk]).strip()
                                    break
                                    
                            # Scan all string values for phone-like patterns
                            if not phone:
                                for k, v in record.items():
                                    if isinstance(v, str) and v.strip() and v != "NULL":
                                        cleaned = v.strip()
                                        if re.match(r"^\+?[0-9\-\s\(\)]{7,20}$", cleaned):
                                            digits = re.sub(r"\D", "", cleaned)
                                            if len(digits) >= 7:
                                                phone = cleaned
                                                break
                                                
                            if name and phone:
                                contacts_list.append((name, phone))
                        except Exception:
                            continue
                
                if contacts_list:
                    vcard_out_dir = exhibit_path / "derived" / "whatsapp_exporter"
                    vcard_out_dir.mkdir(parents=True, exist_ok=True)
                    generated_vcard_path = vcard_out_dir / "contacts.vcf"
                    with open(generated_vcard_path, "w", encoding="utf-8") as vf:
                        for name, phone in contacts_list:
                            vf.write("BEGIN:VCARD\n")
                            vf.write("VERSION:3.0\n")
                            vf.write(f"FN:{name}\n")
                            vf.write(f"TEL;TYPE=CELL:{phone}\n")
                            vf.write("END:VCARD\n")
                            
                    vcard_path = generated_vcard_path
            except Exception:
                pass

    # 2. Run Exporter
    res = run_whatsapp_chat_exporter(
        case_id=case_id,
        exhibit_id=exhibit_id,
        output_root=output_root,
        input_dir=input_dir,
        wa_db=wa_db,
        media_dir=media_dir,
        vcard_path=vcard_path,
        time_offset=time_offset,
        filter_date=filter_date,
        filter_date_format=filter_date_format,
        source=source,
        package=package
    )

    if res["status"] == "success":
        # Rename HTML files from <phone>-<name>.html to <name>.html to improve readability
        html_dir = Path(res["html_output_dir"])
        if html_dir.is_dir():
            for f in list(html_dir.glob("*.html")):
                name_parts = f.name.split("-", 1)
                if len(name_parts) == 2 and name_parts[0].isdigit():
                    new_name = name_parts[1]
                    new_path = f.with_name(new_name)
                    # Resolve collisions safely
                    count = 1
                    while new_path.exists():
                        base = Path(new_name).stem
                        new_path = f.with_name(f"{base}_{count}.html")
                        count += 1
                    try:
                        f.rename(new_path)
                    except Exception:
                        pass

        # Clean up any duplicate nested directories copied by wtsexporter (such as 'cases')
        clutter_dir = html_dir / Path(output_root).name
        if clutter_dir.is_dir():
            import shutil
            try:
                shutil.rmtree(clutter_dir)
            except Exception:
                pass

        # Hash files & append manifest records
        html_dir = Path(res["html_output_dir"])
        json_path = Path(res["json_output_path"])
        
        # Traverse html output directory to collect and hash files
        files_to_hash = []
        if html_dir.is_dir():
            for f in html_dir.rglob("*"):
                if f.is_file():
                    files_to_hash.append(f)
        if json_path.is_file():
            files_to_hash.append(json_path)

        # Staging manifest artifact details:
        artifact_class = "whatsapp_parsed_output" if source == "rooted" else "whatsapp_exporter_output"
        source_type = "rooted_parser_output" if source == "rooted" else "derived_parser_output"

        for f in files_to_hash:
            try:
                sha = hash_file(f)
                size = f.stat().st_size
                append_sha256sum(sha256sums_path, sha, f)
                
                # Manifest log
                manifest_record = {
                    "case_id": case_id,
                    "exhibit_id": exhibit_id,
                    "artifact_class": artifact_class,
                    "source_type": source_type,
                    "parser": "Whatsapp-Chat-Exporter",
                    "destination_path": str(f.relative_to(exhibit_path)),
                    "sha256": sha,
                    "size_bytes": size,
                    "status": "generated"
                }
                if source == "rooted":
                    manifest_record["package_name"] = package
                    
                append_manifest_record(manifest_path, manifest_record)
            except Exception:
                pass

        # Try to parse result.json to get stats
        chat_count = None
        message_count = None
        date_range = None
        
        if json_path.is_file():
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    if isinstance(data, dict):
                        chat_count = len(data)
                        total_msg = 0
                        for chat in data.values():
                            if isinstance(chat, dict) and "messages" in chat:
                                total_msg += len(chat["messages"])
                            elif isinstance(chat, list):
                                total_msg += len(chat)
                        if total_msg > 0:
                            message_count = total_msg
            except Exception:
                pass

        # Write whatsapp_preview_summary.json
        summary_path = exhibit_path / "derived" / "whatsapp_preview_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        
        status_summary = "parsed"
        if warnings:
            status_summary = "partial"
            
        summary = {
            "app": "WhatsApp",
            "package_name": package if source == "rooted" else "com.whatsapp",
            "source": source or "decrypted",
            "parser": "Whatsapp-Chat-Exporter",
            "status": status_summary,
            "msgstore_db_used": True,
            "wa_db_used": bool(wa_db),
            "media_dir_used": bool(media_dir),
            "report_dir": str(html_dir.relative_to(exhibit_path)) if html_dir.exists() else f"derived/whatsapp_exporter/html",
            "json_output": str(json_path.relative_to(exhibit_path)) if json_path.exists() else f"derived/whatsapp_exporter/result.json",
            "generated_file_count": res["generated_file_count"],
            "chat_count": chat_count,
            "message_count": message_count,
            "date_range": date_range,
            "warnings": warnings
        }
        
        with open(summary_path, "w", encoding="utf-8") as sf:
            json.dump(summary, sf, indent=2)

        # Hash and manifest summary file
        try:
            summary_sha = hash_file(summary_path)
            summary_size = summary_path.stat().st_size
            append_sha256sum(sha256sums_path, summary_sha, summary_path)
            append_manifest_record(manifest_path, {
                "case_id": case_id,
                "exhibit_id": exhibit_id,
                "artifact_class": "whatsapp_preview_summary",
                "source_type": "derived_parser_output",
                "parser": "Whatsapp-Chat-Exporter",
                "destination_path": str(summary_path.relative_to(exhibit_path)),
                "sha256": summary_sha,
                "size_bytes": summary_size,
                "status": "generated"
            })
        except Exception:
            pass

        # Completed Audit
        complete_action = "whatsapp_root_parse_completed" if source == "rooted" else "whatsapp_exporter_parse_completed"
        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action=complete_action,
            result="success",
            details={
                "parser": "Whatsapp-Chat-Exporter",
                "source_folder": str(input_dir) if input_dir else "",
                "output_folder": str(html_dir),
                "msgstore_present": "yes" if input_dir and (input_dir / "msgstore.db").is_file() else "no",
                "wa_db_present": "yes" if wa_db else "no",
                "media_folder_present": "yes" if media_dir else "no",
                "generated_file_count": res["generated_file_count"],
                "warnings": warnings
            }
        )
    else:
        # Failed Audit
        fail_action = "whatsapp_root_parse_failed" if source == "rooted" else "whatsapp_exporter_parse_failed"
        append_audit_event(
            audit_path=audit_path,
            case_id=case_id,
            exhibit_id=exhibit_id,
            action=fail_action,
            result="failed",
            details={
                "parser": "Whatsapp-Chat-Exporter",
                "source_folder": str(input_dir) if input_dir else "",
                "output_folder": str(exhibit_path / "derived" / "whatsapp_exporter" / "rooted" / package) if source == "rooted" else str(exhibit_path / "derived" / "whatsapp_exporter" / "html"),
                "msgstore_present": "yes" if input_dir and (input_dir / "msgstore.db").is_file() else "no",
                "wa_db_present": "yes" if wa_db else "no",
                "media_folder_present": "yes" if media_dir else "no",
                "generated_file_count": 0,
                "warnings": warnings,
                "error": res.get("stderr", "Unknown error")
            }
        )
        
    return res
