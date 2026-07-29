from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class CaseInfo:
    case_id: Optional[str] = None
    exhibit_id: Optional[str] = None
    case_folder: Optional[str] = None
    acquisition_status: Optional[str] = None
    acquisition_started_at: Optional[str] = None
    acquisition_completed_at: Optional[str] = None
    dashboard_indexed_at: Optional[str] = None
    total_events: Optional[int] = None
    total_messages: Optional[int] = None
    total_calls: Optional[int] = None
    total_contacts: Optional[int] = None
    total_media: Optional[int] = None
    total_apps: Optional[int] = None
    total_locations: Optional[int] = None
    total_accounts: Optional[int] = None
    total_files: Optional[int] = None
    notes: Optional[str] = None

@dataclass
class DeviceInfo:
    case_id: Optional[str] = None
    exhibit_id: Optional[str] = None
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    android_version: Optional[str] = None
    sdk_level: Optional[str] = None
    security_patch: Optional[str] = None
    build_fingerprint: Optional[str] = None
    serial: Optional[str] = None
    imei: Optional[str] = None
    root_access: Optional[str] = None
    acquisition_method: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class TimelineEvent:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    source_app: Optional[str] = None
    source_type: Optional[str] = None
    event_type: Optional[str] = None
    category: Optional[str] = None
    direction: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    sender: Optional[str] = None
    receiver: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    location_accuracy: Optional[float] = None
    media_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_path: Optional[str] = None
    deleted_status: Optional[str] = None
    recovered_status: Optional[str] = None
    confidence: Optional[str] = None
    source_file: Optional[str] = None
    source_hash: Optional[str] = None
    parser: Optional[str] = None
    raw_ref: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class Message:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    app: Optional[str] = None
    platform: Optional[str] = None
    chat_id: Optional[str] = None
    chat_name: Optional[str] = None
    direction: Optional[str] = None
    sender: Optional[str] = None
    receiver: Optional[str] = None
    body: Optional[str] = None
    message_type: Optional[str] = None
    deleted_status: Optional[str] = None
    recovered_status: Optional[str] = None
    media_path: Optional[str] = None
    source_file: Optional[str] = None
    source_hash: Optional[str] = None
    parser: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class Call:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    source: Optional[str] = None
    call_type: Optional[str] = None
    direction: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    contact_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    app: Optional[str] = None
    source_file: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class Contact:
    id: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source_app: Optional[str] = None
    apps_seen_in: Optional[str] = None
    message_count: Optional[int] = None
    call_count: Optional[int] = None
    last_seen: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class Media:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    source_app: Optional[str] = None
    path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    linked_event_id: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class Location:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    source: Optional[str] = None
    linked_event_id: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class App:
    package_name: Optional[str] = None
    app_name: Optional[str] = None
    version_name: Optional[str] = None
    version_code: Optional[str] = None
    apk_path: Optional[str] = None
    install_time: Optional[str] = None
    last_update_time: Optional[str] = None
    uid: Optional[str] = None
    is_system_app: Optional[int] = None
    permissions: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class Account:
    id: Optional[str] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    email: Optional[str] = None
    provider_app: Optional[str] = None
    sync_provider: Optional[str] = None
    source_file: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class NetworkEvent:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    ip: Optional[str] = None
    ssid: Optional[str] = None
    carrier: Optional[str] = None
    vpn_state: Optional[str] = None
    dns: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class SystemEvent:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    event_type: Optional[str] = None
    source: Optional[str] = None
    severity: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class ParserOutput:
    id: Optional[str] = None
    parser: Optional[str] = None
    app: Optional[str] = None
    status: Optional[str] = None
    input_path: Optional[str] = None
    output_path: Optional[str] = None
    generated_file_count: Optional[int] = None
    summary_json: Optional[str] = None

@dataclass
class Hash:
    id: Optional[str] = None
    file_path: Optional[str] = None
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    status: Optional[str] = None
    source: Optional[str] = None

@dataclass
class AuditEvent:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    details_json: Optional[str] = None

@dataclass
class BrowserHistory:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    browser: Optional[str] = None
    package_name: Optional[str] = None
    profile: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    visit_count: Optional[int] = None
    typed_count: Optional[int] = None
    confidence: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class BrowserSearch:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    browser: Optional[str] = None
    package_name: Optional[str] = None
    profile: Optional[str] = None
    search_term: Optional[str] = None
    url: Optional[str] = None
    confidence: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class BrowserDownload:
    id: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_sort: Optional[int] = None
    browser: Optional[str] = None
    package_name: Optional[str] = None
    profile: Optional[str] = None
    download_url: Optional[str] = None
    target_path: Optional[str] = None
    mime_type: Optional[str] = None
    received_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    confidence: Optional[str] = None
    raw_json: Optional[str] = None

@dataclass
class ExaminerInfo:
    id: Optional[str] = None
    name: Optional[str] = None
    badge_id: Optional[str] = None
    rank_title: Optional[str] = None
    agency: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class ChainOfCustodyEntry:
    id: Optional[str] = None
    entry_index: Optional[int] = None
    timestamp: Optional[str] = None
    action: Optional[str] = None
    performed_by: Optional[str] = None
    received_by: Optional[str] = None
    location: Optional[str] = None
    evidence_condition: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class EvidenceMetadata:
    id: Optional[str] = None
    storage_location: Optional[str] = None
    evidence_bag_tag: Optional[str] = None
    seizure_date: Optional[str] = None
    seizure_location: Optional[str] = None
    seizure_authority: Optional[str] = None
    warrant_number: Optional[str] = None
    acquisition_tool: Optional[str] = None
    acquisition_tool_version: Optional[str] = None
    notes: Optional[str] = None
    updated_at: Optional[str] = None
