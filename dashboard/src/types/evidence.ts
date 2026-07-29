export interface CaseSummary {
  case_id: string;
  exhibit_id: string;
  device_info: {
    model: string;
    manufacturer: string;
    android_version: string;
    security_patch: string;
    serial: string;
    imei: string;
  };
  acquisition_status: 'Complete' | 'Partial' | 'Unavailable';
  acquisition_method: string;
  root_access: boolean;
  counts: {
    timeline_events: number;
    messages: number;
    calls: number;
    contacts: number;
    media: number;
    apps: number;
    locations: number;
    accounts: number;
    files: number;
    network: number;
    system: number;
    integrity: number;
    browser_history?: number;
    browser_searches?: number;
    browser_downloads?: number;
  };
  acquisition_started_at: string;
  acquisition_completed_at: string;
  warnings?: string[];
  missing_sources?: string[];
}

export interface DeviceInfo {
  id: string;
  model: string;
  manufacturer: string;
  android_version: string;
  security_patch: string;
  serial: string;
  imei: string;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  timestamp_sort?: string | number;
  bucket_15m?: string;
  bucket_1h?: string;
  source_app: string;
  source_type?: string;
  category?: string;
  event_type: string;
  direction?: string;
  title: string;
  summary: string;
  sender?: string;
  receiver?: string;
  phone_number?: string;
  email?: string;
  location_lat?: number;
  location_lon?: number;
  location_accuracy?: number;
  media_path?: string;
  thumbnail_path?: string;
  file_path?: string;
  deleted_status?: string;
  recovered_status?: string;
  deleted?: boolean;
  recovered?: boolean;
  confidence?: 'high' | 'medium' | 'low';
  source_file?: string;
  source_hash?: string;
  parser?: string;
  raw_ref?: string;
  raw_json?: string;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
}

export interface Message {
  id: string;
  timestamp: string;
  source_app: string;
  sender: string;
  receiver: string;
  body: string;
  deleted: boolean;
}

export interface Call {
  id: string;
  timestamp: string;
  source_app: string;
  caller: string;
  callee: string;
  duration: number;
  type: string;
  deleted: boolean;
}

export interface Contact {
  id: string;
  name: string;
  phone_number: string;
  source_app: string;
  deleted: boolean;
}

export interface MediaItem {
  id: string;
  timestamp: string;
  source_app: string;
  file_path: string;
  mime_type: string;
  size_bytes: number;
  deleted: boolean;
}

export interface Location {
  id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  accuracy: number;
  source_app: string;
}

export interface App {
  id: string;
  package_name: string;
  app_name: string;
  version: string;
  installed_at: string;
}

export interface Account {
  id: string;
  account_type: string;
  account_name: string;
  source_app: string;
}

export interface NetworkEvent {
  id: string;
  timestamp: string;
  event_type: string;
  details: string;
}

export interface SystemEvent {
  id: string;
  timestamp: string;
  event_type: string;
  details: string;
}

export interface SearchResult {
  result_type: string;
  id: string;
  timestamp: string;
  source: string;
  snippet: string;
  confidence: string;
  event_id: string;
}

export interface HashRecord {
  file_path: string;
  sha256: string;
  size_bytes: number;
  status: 'Verified' | 'Mismatch' | 'Unknown';
  source: string;
}

export interface AuditEvent {
  timestamp: string;
  action: string;
  result: string;
  details_json: string;
}

export interface IntegrityData {
  hashes: HashRecord[];
  audit_events: AuditEvent[];
  summary: {
    total_files: number;
    verified: number;
    mismatches: number;
    unknown: number;
  };
}

export interface BrowserHistoryRecord {
  id: string;
  timestamp: string;
  browser: string;
  url: string;
  title: string;
  visit_count: number;
  confidence: string;
}

export interface BrowserSearchRecord {
  id: string;
  timestamp: string;
  browser: string;
  search_term: string;
  url: string;
  confidence: string;
}

export interface BrowserDownloadRecord {
  id: string;
  timestamp: string;
  browser: string;
  download_url: string;
  target_path: string;
  mime_type: string;
  total_bytes: number;
  confidence: string;
}

export interface TimelineFilters {
  page?: number;
  limit?: number;
  source?: string;
  category?: string;
  event_type?: string;
  from_date?: string;
  to_date?: string;
  q?: string;
  deleted?: boolean;
  recovered?: boolean;
}

export interface ExaminerInfo {
  id?: string;
  name: string;
  badge_id?: string;
  rank_title?: string;
  agency?: string;
  email?: string;
  phone?: string;
  notes?: string;
  updated_at?: string;
}

export interface ChainOfCustodyEntry {
  id?: string;
  entry_index?: number;
  timestamp: string;
  action: string;
  performed_by?: string;
  received_by?: string;
  location?: string;
  evidence_condition?: string;
  notes?: string;
  created_at?: string;
}

export interface EvidenceMetadata {
  id?: string;
  storage_location?: string;
  evidence_bag_tag?: string;
  seizure_date?: string;
  seizure_location?: string;
  seizure_authority?: string;
  warrant_number?: string;
  acquisition_tool?: string;
  acquisition_tool_version?: string;
  notes?: string;
  updated_at?: string;
}
