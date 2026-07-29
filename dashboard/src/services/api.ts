import type {  
  CaseSummary, DeviceInfo, TimelineFilters, TimelineResponse, TimelineEvent,
  Message, Call, Contact, MediaItem, Location, App, Account, NetworkEvent, SystemEvent,
  IntegrityData, SearchResult, ExaminerInfo, ChainOfCustodyEntry, EvidenceMetadata
 } from '../types/evidence';

const API_BASE = '/api';

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  return res.json();
}

function cleanParams(params: any): Record<string, string> {
  const clean: Record<string, string> = {};
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null) {
      clean[k] = String(v);
    }
  }
  return clean;
}

export async function fetchCaseSummary(): Promise<CaseSummary> {
  return fetchJSON<CaseSummary>(`${API_BASE}/case/summary`);
}

export async function fetchDevice(): Promise<DeviceInfo> {
  return fetchJSON<DeviceInfo>(`${API_BASE}/device`);
}

export async function fetchTimeline(params: TimelineFilters): Promise<TimelineResponse> {
  const query = new URLSearchParams(cleanParams(params as any)).toString();
  return fetchJSON<TimelineResponse>(`${API_BASE}/timeline?${query}`);
}

export async function fetchTimelineEvent(eventId: string): Promise<TimelineEvent> {
  return fetchJSON<TimelineEvent>(`${API_BASE}/timeline/${eventId}`);
}

export async function fetchMessages(params: any): Promise<{ data: Message[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/messages?${query}`);
}

export async function fetchCalls(params: any): Promise<{ data: Call[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/calls?${query}`);
}

export async function fetchContacts(params: any): Promise<{ data: Contact[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/contacts?${query}`);
}

export async function fetchMedia(params: any): Promise<{ data: MediaItem[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/media?${query}`);
}

export async function fetchLocations(params: any): Promise<{ data: Location[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/locations?${query}`);
}

export async function fetchApps(params: any): Promise<{ data: App[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/apps?${query}`);
}

export async function fetchAccounts(params: any): Promise<{ data: Account[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/accounts?${query}`);
}

export async function fetchNetwork(params: any): Promise<{ data: NetworkEvent[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/network?${query}`);
}

export async function fetchSystem(params: any): Promise<{ data: SystemEvent[], total: number }> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/system?${query}`);
}

export async function fetchIntegrity(): Promise<IntegrityData> {
  return fetchJSON<IntegrityData>(`${API_BASE}/integrity`);
}

export async function searchEvidence(query: string, limit?: number): Promise<SearchResult[]> {
  const url = `${API_BASE}/search?q=${encodeURIComponent(query)}${limit ? `&limit=${limit}` : ''}`;
  return fetchJSON<SearchResult[]>(url);
}

export async function exportReport(): Promise<void> {
  const res = await fetch(`${API_BASE}/export-report`, { method: 'POST' });
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
}

export async function verifyHashes(): Promise<void> {
  const res = await fetch(`${API_BASE}/verify-hashes`, { method: 'POST' });
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
}

export async function fetchBrowserHistory(params: Record<string, any> = {}): Promise<any> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/browser-history?${query}`);
}

export async function fetchBrowserSearches(params: Record<string, any> = {}): Promise<any> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/browser-searches?${query}`);
}

export async function fetchBrowserDownloads(params: Record<string, any> = {}): Promise<any> {
  const query = new URLSearchParams(cleanParams(params)).toString();
  return fetchJSON(`${API_BASE}/browser-downloads?${query}`);
}

export async function fetchIntakeStatus(): Promise<{complete: boolean}> {
  return fetchJSON('/api/intake-status');
}

export async function fetchExaminer(): Promise<ExaminerInfo> {
  return fetchJSON('/api/examiner');
}

export async function updateExaminer(data: Partial<ExaminerInfo>): Promise<any> {
  const res = await fetch('/api/examiner', { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  return res.json();
}

export async function fetchChainOfCustody(): Promise<{entries: ChainOfCustodyEntry[], total: number}> {
  return fetchJSON('/api/chain-of-custody');
}

export async function addChainOfCustodyEntry(data: Partial<ChainOfCustodyEntry>): Promise<any> {
  const res = await fetch('/api/chain-of-custody', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  return res.json();
}

export async function deleteChainOfCustodyEntry(id: string): Promise<any> {
  const res = await fetch(`/api/chain-of-custody/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  return res.json();
}

export async function fetchEvidenceMetadata(): Promise<EvidenceMetadata> {
  return fetchJSON('/api/evidence-metadata');
}

export async function updateEvidenceMetadata(data: Partial<EvidenceMetadata>): Promise<any> {
  const res = await fetch('/api/evidence-metadata', { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  return res.json();
}
