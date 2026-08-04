import { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  HelpCircle, 
  Search, 
  Layers, 
  Cpu, 
  ShieldAlert, 
  ArrowRight,
  Filter
} from 'lucide-react';
import { 
  fetchQuestioningLeads, 
  fetchQuestioningLeadsSummary, 
  fetchQuestioningLeadEvents, 
  QuestioningLead, 
  LeadsSummary 
} from '../services/api';
import type { TimelineEvent } from '../types/evidence';

interface LeadsPanelProps {
  caseId: string;
  exhibitId: string;
  onJumpToEvent: (eventId: string) => void;
}

export const LeadsPanel = ({ caseId, exhibitId, onJumpToEvent }: LeadsPanelProps) => {
  const [leads, setLeads] = useState<QuestioningLead[]>([]);
  const [summary, setSummary] = useState<LeadsSummary | null>(null);
  const [selectedLead, setSelectedLead] = useState<QuestioningLead | null>(null);
  const [linkedEvents, setLinkedEvents] = useState<TimelineEvent[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load leads list & summary
  const loadLeadsData = async () => {
    setLoading(true);
    try {
      const filters: any = {};
      if (severityFilter !== 'all') {
        filters.severity = severityFilter;
      }
      if (searchQuery.trim()) {
        filters.q = searchQuery.trim();
      }
      
      const leadsRes = await fetchQuestioningLeads(caseId, exhibitId, filters);
      const summaryRes = await fetchQuestioningLeadsSummary(caseId, exhibitId);
      
      setLeads(leadsRes.leads);
      setSummary(summaryRes);
      
      // Auto-select first lead if none selected
      if (leadsRes.leads.length > 0 && (!selectedLead || !leadsRes.leads.some(l => l.lead_id === selectedLead.lead_id))) {
        setSelectedLead(leadsRes.leads[0]);
      } else if (leadsRes.leads.length === 0) {
        setSelectedLead(null);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load questioning leads');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLeadsData();
  }, [caseId, exhibitId, severityFilter, searchQuery]);

  // Load linked timeline events for selected lead
  useEffect(() => {
    if (!selectedLead) {
      setLinkedEvents([]);
      return;
    }
    const loadEvents = async () => {
      try {
        const events = await fetchQuestioningLeadEvents(caseId, exhibitId, selectedLead.lead_id);
        setLinkedEvents(events);
      } catch (err) {
        console.error('Failed to load linked timeline events', err);
      }
    };
    loadEvents();
  }, [selectedLead, caseId, exhibitId]);

  const getSeverityColor = (sev: string) => {
    switch (sev.toLowerCase()) {
      case 'critical': return 'bg-red-500/15 border-red-500/30 text-red-400';
      case 'high': return 'bg-orange-500/15 border-orange-500/30 text-orange-400';
      case 'medium': return 'bg-yellow-500/15 border-yellow-500/30 text-yellow-400';
      default: return 'bg-blue-500/15 border-blue-500/30 text-blue-400';
    }
  };

  const getConfidenceColor = (conf: string) => {
    switch (conf.toLowerCase()) {
      case 'high': return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400';
      case 'medium': return 'bg-indigo-500/15 border-indigo-500/30 text-indigo-400';
      default: return 'bg-slate-500/15 border-slate-500/30 text-slate-400';
    }
  };

  const formatEpochToReadable = (ms?: number) => {
    if (!ms) return 'Not available';
    return new Date(ms).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  };

  return (
    <div className="flex flex-col h-full bg-[#0b0f19] text-[#cbd5e1] overflow-hidden">
      
      {/* Top Warning Disclaimer (Visible Compliance) */}
      <div className="bg-amber-950/20 border-b border-amber-500/20 p-3 flex items-start gap-2.5 text-xs text-amber-300">
        <AlertTriangle className="h-4.5 w-4.5 text-amber-500 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-amber-400">Forensic Intelligence Disclaimer:</span>{' '}
          Questioning leads are automatically generated investigative prompts based on extracted artifacts. They are not forensic conclusions. Do not label anyone guilty or assume criminal intent.
        </div>
      </div>

      {/* Summary Analytics Card Block */}
      <div className="p-4 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3 border-b border-slate-800 bg-[#0f172a]/40">
        <div className="bg-[#1e293b]/30 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Total Leads</span>
          <span className="text-2xl font-bold text-slate-100">{summary?.total || 0}</span>
        </div>
        <div className="bg-red-950/10 border border-red-500/20 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-red-500 tracking-wider">Critical Severity</span>
          <span className="text-2xl font-bold text-red-400">{summary?.by_severity?.critical || 0}</span>
        </div>
        <div className="bg-orange-950/10 border border-orange-500/20 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-orange-500 tracking-wider">High Severity</span>
          <span className="text-2xl font-bold text-orange-400">{summary?.by_severity?.high || 0}</span>
        </div>
        <div className="bg-yellow-950/10 border border-yellow-500/20 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-yellow-500 tracking-wider">Medium Severity</span>
          <span className="text-2xl font-bold text-yellow-400">{summary?.by_severity?.medium || 0}</span>
        </div>
        <div className="col-span-2 sm:col-span-1 bg-[#1e293b]/30 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Last Computed</span>
          <span className="text-[10px] text-slate-400 break-all truncate" title={summary?.generated_at}>
            {summary?.generated_at ? new Date(summary.generated_at).toLocaleTimeString() : 'N/A'}
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3 border-b border-slate-800 flex flex-wrap items-center gap-3 bg-[#0d1323]">
        <div className="relative flex-1 min-w-[200px]">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-slate-500" />
          </span>
          <input
            type="text"
            className="w-full bg-[#1e293b]/50 border border-slate-700 rounded-md py-1.5 pl-9 pr-4 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500"
            placeholder="Search leads (e.g. OTP, WhatsApp, Surat)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-500" />
          <select
            className="bg-[#1e293b]/50 border border-slate-700 rounded-md py-1.5 px-3 text-xs text-slate-200 focus:outline-none focus:border-slate-500"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical Only</option>
            <option value="high">High & Critical</option>
            <option value="medium">Medium & Above</option>
            <option value="low">Low & Above</option>
          </select>
        </div>
      </div>

      {/* Split Body Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Column: Leads List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 border-r border-slate-800">
          {loading && (
            <div className="text-center py-8 text-slate-500 text-xs">
              <Cpu className="h-6 w-6 animate-spin mx-auto mb-2 text-slate-600" />
              Running leads heuristics...
            </div>
          )}
          {!loading && error && (
            <div className="text-center py-8 text-red-400 text-xs">
              Error: {error}
            </div>
          )}
          {!loading && leads.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-xs">
              No questioning leads matched current filters.
            </div>
          )}

          {leads.map((lead) => (
            <div
              key={lead.lead_id}
              onClick={() => setSelectedLead(lead)}
              className={`p-4 border rounded-lg cursor-pointer transition-all duration-150 ${
                selectedLead?.lead_id === lead.lead_id
                  ? 'bg-[#1e293b]/40 border-slate-600 shadow-md ring-1 ring-slate-700'
                  : 'bg-[#0f172a]/20 border-slate-800 hover:bg-[#1e293b]/20 hover:border-slate-700'
              }`}
            >
              {/* Header Badges */}
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                <span className="text-xs font-bold text-slate-200">
                  {lead.title}
                </span>
                <div className="flex gap-1.5">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getSeverityColor(lead.severity)}`}>
                    {lead.severity}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getConfidenceColor(lead.confidence)}`}>
                    {lead.confidence}
                  </span>
                </div>
              </div>

              {/* Summary Description */}
              <p className="text-xs text-slate-400 mb-3 leading-relaxed">
                {lead.summary}
              </p>

              {/* Suggested Question Quote Box */}
              <div className="bg-[#1e293b]/25 border-l-2 border-slate-600 p-2.5 rounded-r mb-3 text-xs italic text-slate-300">
                "{lead.suggested_question}"
              </div>

              {/* Footer details */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500">
                <div className="flex flex-wrap gap-1">
                  {lead.source_apps.map((app) => (
                    <span key={app} className="bg-slate-800 border border-slate-700 text-slate-400 px-1.5 py-0.5 rounded">
                      {app}
                    </span>
                  ))}
                </div>
                <span>
                  {lead.evidence_count || lead.event_ids.length} linked event(s)
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Right Column: Selected Lead Details Panel */}
        <div className="w-[380px] md:w-[420px] bg-[#0c1221] p-4 overflow-y-auto flex flex-col gap-4 border-l border-slate-800">
          {selectedLead ? (
            <>
              {/* Lead ID & Rule Information */}
              <div>
                <div className="flex items-center gap-2 text-slate-500 text-[10px] uppercase font-semibold mb-1">
                  <Cpu className="h-3.5 w-3.5" />
                  <span>Rule: {selectedLead.rule_id}</span>
                </div>
                <h3 className="text-sm font-bold text-slate-200 mb-2">
                  {selectedLead.title}
                </h3>
                <div className="flex gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getSeverityColor(selectedLead.severity)}`}>
                    Severity: {selectedLead.severity}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getConfidenceColor(selectedLead.confidence)}`}>
                    Confidence: {selectedLead.confidence}
                  </span>
                </div>
              </div>

              {/* Divider */}
              <hr className="border-slate-800" />

              {/* Investigator Prompt */}
              <div>
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <HelpCircle className="h-4 w-4 text-indigo-400" />
                  Suggested Investigative Prompt
                </h4>
                <div className="bg-[#1e293b]/30 border border-slate-700 p-3.5 rounded-lg text-xs italic text-indigo-300 leading-relaxed">
                  "{selectedLead.suggested_question}"
                </div>
              </div>

              {/* Flaggings / Details */}
              <div>
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">
                  Heuristic Analysis Detail
                </h4>
                <div className="text-xs text-slate-400 space-y-2 leading-relaxed">
                  <p>{selectedLead.summary}</p>
                  {selectedLead.time_window_start && (
                    <div className="bg-[#131b2e] p-2.5 rounded border border-slate-800 text-[11px] space-y-1 mt-2">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Activity Start:</span>
                        <span className="text-slate-300 font-mono">{formatEpochToReadable(selectedLead.time_window_start)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Activity End:</span>
                        <span className="text-slate-300 font-mono">{formatEpochToReadable(selectedLead.time_window_end)}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Linked Timeline Evidence Events List */}
              <div className="flex-1 flex flex-col min-h-[200px]">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <Layers className="h-4 w-4 text-emerald-400" />
                  Linked Forensic Evidence ({linkedEvents.length})
                </h4>
                <div className="flex-1 border border-slate-800 bg-[#070b13] rounded-lg overflow-y-auto p-2 space-y-2">
                  {linkedEvents.map((evt) => (
                    <div key={evt.id} className="p-2.5 bg-[#141b2b]/55 border border-slate-800 rounded flex flex-col justify-between gap-2.5">
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="bg-slate-800 border border-slate-700 text-slate-400 px-1.5 py-0.5 rounded text-[9px] font-mono uppercase">
                            {evt.source_app} / {evt.event_type}
                          </span>
                          <span className="text-[9px] text-slate-500 font-mono">{evt.display_date} {evt.display_time}</span>
                        </div>
                        <p className="text-xs text-slate-300 font-semibold mb-0.5">{evt.title}</p>
                        <p className="text-[11px] text-slate-400 truncate max-w-[340px]" title={evt.summary || ''}>
                          {evt.summary || 'No description available.'}
                        </p>
                      </div>
                      
                      {/* Jump button */}
                      <button
                        onClick={() => onJumpToEvent(evt.id)}
                        className="self-end flex items-center gap-1 text-[10px] text-emerald-400 hover:text-emerald-300 bg-emerald-950/25 border border-emerald-500/20 hover:border-emerald-500/40 px-2 py-1 rounded transition-all duration-100"
                      >
                        <span>Open in Timeline</span>
                        <ArrowRight className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                  {linkedEvents.length === 0 && (
                    <div className="text-center py-6 text-[10px] text-slate-600">
                      Loading cited events...
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 text-xs">
              <ShieldAlert className="h-8 w-8 mb-2 text-slate-700" />
              Select a questioning lead to inspect details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
