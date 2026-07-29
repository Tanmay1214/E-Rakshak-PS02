from __future__ import annotations
import logging
from pathlib import Path
from datetime import datetime
from .db import DashboardDB

logger = logging.getLogger(__name__)

def export_html_report(db: DashboardDB, exhibit_root: Path, case_id: str, exhibit_id: str) -> Path:
    reports_dir = exhibit_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "forensic_preview_report.html"
    
    case_info = db.query("case_info", limit=1)
    case_data = case_info[0] if case_info else {}
    
    device_info = db.query("device_info", limit=1)
    dev_data = device_info[0] if device_info else {}
    
    examiner_rows = db.query("examiner_info", limit=1)
    examiner = examiner_rows[0] if examiner_rows else {}
    
    evidence_rows = db.query("evidence_metadata", limit=1)
    evidence = evidence_rows[0] if evidence_rows else {}
    
    coc_entries = db.query("chain_of_custody", limit=1000, order_by="entry_index ASC")
    
    counts = db.get_counts()
    
    # Build chain of custody table rows
    coc_rows = ""
    for entry in coc_entries:
        coc_rows += f"""
            <tr>
                <td>{entry.get('entry_index', '')}</td>
                <td>{entry.get('timestamp', '')}</td>
                <td>{entry.get('action', '')}</td>
                <td>{entry.get('performed_by', '')}</td>
                <td>{entry.get('received_by', '')}</td>
                <td>{entry.get('location', '')}</td>
                <td>{entry.get('evidence_condition', '')}</td>
                <td>{entry.get('notes', '')}</td>
            </tr>"""
    if not coc_rows:
        coc_rows = '<tr><td colspan="8" style="text-align:center; color:#888;">No chain of custody entries recorded.</td></tr>'
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Forensic Preview Report - {case_id}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #121212; color: #e0e0e0; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #ffffff; font-size: 28px; border-bottom: 2px solid #4fc3f7; padding-bottom: 10px; }}
        h2 {{ color: #4fc3f7; font-size: 20px; border-bottom: 1px solid #333; padding-bottom: 5px; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #444; padding: 10px 14px; text-align: left; font-size: 14px; }}
        th {{ background: #1a1a2e; color: #4fc3f7; font-weight: 600; }}
        tr:nth-child(even) {{ background: #1a1a1a; }}
        .warning {{ background: #3a1a0a; padding: 14px 18px; border-left: 5px solid #ff5252; margin-bottom: 24px; border-radius: 4px; }}
        .meta-label {{ color: #888; font-weight: 600; min-width: 200px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #333; font-size: 12px; color: #666; }}
        .count-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 20px; }}
        .count-card {{ background: #1a1a2e; padding: 12px; border-radius: 6px; text-align: center; }}
        .count-card .num {{ font-size: 24px; font-weight: 700; color: #4fc3f7; }}
        .count-card .lbl {{ font-size: 11px; color: #888; text-transform: uppercase; }}
    </style>
</head>
<body>
    <h1>E-RAKSHAK Forensic Preview Report</h1>
    <div class="warning">
        <strong>IMPORTANT:</strong> This report is a rapid forensic preview only. It is not a substitute for full laboratory examination.
        All findings are preliminary and must be verified through proper forensic procedures.
    </div>
    
    <h2>1. Case &amp; Evidence Summary</h2>
    <table>
        <tr><td class="meta-label">Case ID</td><td>{case_id}</td></tr>
        <tr><td class="meta-label">Evidence / Exhibit ID</td><td>{exhibit_id}</td></tr>
        <tr><td class="meta-label">Evidence Bag / Tag Number</td><td>{evidence.get('evidence_bag_tag', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Seizure Date</td><td>{evidence.get('seizure_date', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Seizure Location</td><td>{evidence.get('seizure_location', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Seizure Authority</td><td>{evidence.get('seizure_authority', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Warrant Number</td><td>{evidence.get('warrant_number', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Storage Location</td><td>{evidence.get('storage_location', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Acquisition Tool</td><td>{evidence.get('acquisition_tool', 'E-RAKSHAK')} {evidence.get('acquisition_tool_version', '')}</td></tr>
        <tr><td class="meta-label">Report Generated At</td><td>{datetime.utcnow().isoformat()}Z</td></tr>
    </table>
    
    <h2>2. Examiner Information</h2>
    <table>
        <tr><td class="meta-label">Name</td><td>{examiner.get('name', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Badge / ID Number</td><td>{examiner.get('badge_id', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Rank / Title</td><td>{examiner.get('rank_title', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Agency / Organization</td><td>{examiner.get('agency', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Email</td><td>{examiner.get('email', 'Not specified')}</td></tr>
        <tr><td class="meta-label">Phone</td><td>{examiner.get('phone', 'Not specified')}</td></tr>
    </table>
    
    <h2>3. Chain of Custody</h2>
    <table>
        <tr>
            <th>#</th><th>Date / Time</th><th>Action</th><th>Performed By</th>
            <th>Received By</th><th>Location</th><th>Condition</th><th>Notes</th>
        </tr>
        {coc_rows}
    </table>
    
    <h2>4. Device Information</h2>
    <table>
        <tr><td class="meta-label">Manufacturer</td><td>{dev_data.get('manufacturer', '')}</td></tr>
        <tr><td class="meta-label">Brand</td><td>{dev_data.get('brand', '')}</td></tr>
        <tr><td class="meta-label">Model</td><td>{dev_data.get('model', '')}</td></tr>
        <tr><td class="meta-label">Android Version</td><td>{dev_data.get('android_version', '')}</td></tr>
        <tr><td class="meta-label">SDK Level</td><td>{dev_data.get('sdk_level', '')}</td></tr>
        <tr><td class="meta-label">Security Patch</td><td>{dev_data.get('security_patch', '')}</td></tr>
        <tr><td class="meta-label">Serial</td><td>{dev_data.get('serial', '')}</td></tr>
        <tr><td class="meta-label">IMEI</td><td>{dev_data.get('imei', '')}</td></tr>
        <tr><td class="meta-label">Root Access</td><td>{dev_data.get('root_access', '')}</td></tr>
        <tr><td class="meta-label">Acquisition Method</td><td>{dev_data.get('acquisition_method', '')}</td></tr>
    </table>

    <h2>5. Evidence Summary Counts</h2>
    <div class="count-grid">
        <div class="count-card"><div class="num">{counts.get('timeline_events', 0)}</div><div class="lbl">Timeline Events</div></div>
        <div class="count-card"><div class="num">{counts.get('messages', 0)}</div><div class="lbl">Messages</div></div>
        <div class="count-card"><div class="num">{counts.get('calls', 0)}</div><div class="lbl">Calls</div></div>
        <div class="count-card"><div class="num">{counts.get('contacts', 0)}</div><div class="lbl">Contacts</div></div>
        <div class="count-card"><div class="num">{counts.get('media', 0)}</div><div class="lbl">Media Files</div></div>
        <div class="count-card"><div class="num">{counts.get('apps', 0)}</div><div class="lbl">Apps</div></div>
        <div class="count-card"><div class="num">{counts.get('locations', 0)}</div><div class="lbl">Locations</div></div>
        <div class="count-card"><div class="num">{counts.get('browser_history', 0)}</div><div class="lbl">Browser History</div></div>
    </div>

    <h2>6. Limitations &amp; Notes</h2>
    <ul>
        <li>This report is a <strong>rapid forensic preview</strong> generated by E-RAKSHAK automated triage.</li>
        <li>Evidence integrity should be independently verified using the SHA-256 hash manifest.</li>
        <li>Telegram message content may contain binary artifacts due to TDS serialization limitations.</li>
        <li>Timestamps are presented in the device's local timezone unless otherwise noted.</li>
    </ul>
    <p><strong>Evidence Notes:</strong> {evidence.get('notes', 'None')}</p>
    <p><strong>Examiner Notes:</strong> {examiner.get('notes', 'None')}</p>

    <div class="footer">
        Generated by E-RAKSHAK v0.1.0 &mdash; Android Rapid Evidence Triage &amp; Forensic Preview Tool
    </div>
</body>
</html>
    """
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    return report_path
