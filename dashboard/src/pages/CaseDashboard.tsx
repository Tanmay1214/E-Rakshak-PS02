import { useState, useEffect } from 'react';
import { useCaseSummary } from '../hooks/useCaseSummary';
import { useTimeline } from '../hooks/useTimeline';
import Sidebar from '../components/Sidebar';
import TopBar from '../components/TopBar';
import FiltersBar from '../components/FiltersBar';
import Timeline from '../components/Timeline';
import EventDetailsPanel from '../components/EventDetailsPanel';
import CategoryView from '../components/CategoryView';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import BottomSummaryStrip from '../components/BottomSummaryStrip';
import { useMessages } from '../hooks/useMessages';
import { useCalls } from '../hooks/useCalls';
import { useContacts } from '../hooks/useContacts';
import { useMedia } from '../hooks/useMedia';
import { useApps } from '../hooks/useApps';
import { useAccounts } from '../hooks/useAccounts';
import { useSystemEvents } from '../hooks/useSystemEvents';
import { useLocations } from '../hooks/useLocations';
import { useNetwork } from '../hooks/useNetwork';
import { useBrowserHistory } from '../hooks/useBrowserHistory';
import { fetchIntakeStatus } from '../services/api';
import CaseIntakeWizard from './CaseIntakeWizard';
import CaseInfoPage from './CaseInfoPage';
import type { TimelineEvent } from '../types/evidence';
import { formatTimestamp, formatDuration, formatBytes, truncateText } from '../utils/formatters';
import { AlertTriangle, AlertCircle, ShieldAlert, X } from 'lucide-react';

const ExpandableText = ({ text, maxLength = 100 }: { text: string; maxLength?: number }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!text) return <span></span>;
  if (text.length <= maxLength) return <span className="whitespace-normal break-words max-w-md block">{text}</span>;
  
  return (
    <div className="cursor-pointer group whitespace-normal break-words max-w-md block" onClick={() => setExpanded(!expanded)}>
      <span className={expanded ? "whitespace-pre-wrap" : "line-clamp-2"}>
        {text}
      </span>
      <span className="text-xs text-accent font-medium mt-1 inline-block opacity-80 hover:opacity-100 transition-opacity">
        {expanded ? 'Show less' : 'Show more'}
      </span>
    </div>
  );
};

export default function CaseDashboard() {
  const { summary, loading: summaryLoading, error: summaryError } = useCaseSummary();
  const [activeView, setActiveView] = useState('case-info');
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedEventId, setSelectedEventId] = useState<string | undefined>();
  const [intakeComplete, setIntakeComplete] = useState<boolean | null>(null);

  // Filter States
  const [timeRange, setTimeRange] = useState('7d');
  const [customFromDate, setCustomFromDate] = useState('2026-07-17T00:00');
  const [customToDate, setCustomToDate] = useState('2026-07-24T23:59');
  const [searchTerm, setSearchTerm] = useState('');
  const [showWarningsModal, setShowWarningsModal] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>([
    'whatsapp', 'telegram', 'signal', 'sms', 'phone', 'chrome', 'system'
  ]);
  const [bucketMode, setBucketMode] = useState<'15m' | '1h' | 'exact'>('exact');
  const [selectedMessageApp, setSelectedMessageApp] = useState<string>('all');

  useEffect(() => {
    fetchIntakeStatus()
      .then(res => setIntakeComplete(res.complete))
      .catch(err => {
        console.error("Error fetching intake status", err);
        setIntakeComplete(false);
      });
  }, []);

  const getTimelineFilters = () => {
    const filters: any = { limit: 100 };
    
    // Category mapping
    if (activeFilter !== 'all') {
      if (['whatsapp', 'telegram', 'signal'].includes(activeFilter)) {
        const sourceMap: Record<string, string> = {
          'whatsapp': 'WhatsApp',
          'telegram': 'Telegram',
          'signal': 'Signal'
        };
        filters.source = sourceMap[activeFilter];
      } else if (activeFilter === 'sms' || activeFilter === 'messages') {
        filters.source = 'sms';
      } else if (activeFilter === 'browser') {
        filters.category = 'browser';
      } else if (activeFilter === 'location') {
        filters.category = 'locations';
      } else {
        filters.category = activeFilter;
      }
    }
    
    // Time Range / Date Picker filters
    if (timeRange === '24h') {
      const yesterday = new Date(Date.now() - 24 * 3600000);
      filters.from_date = yesterday.toISOString().split('T')[0];
    } else if (timeRange === '7d') {
      const weekAgo = new Date(Date.now() - 7 * 24 * 3600000);
      filters.from_date = weekAgo.toISOString().split('T')[0];
    } else if (timeRange === 'custom') {
      if (customFromDate) filters.from_date = customFromDate;
      if (customToDate) filters.to_date = customToDate;
    }

    if (searchTerm) {
      filters.q = searchTerm;
    }
    
    return filters;
  };
  
  const { events, loading: eventsLoading, total: totalEvents, loadMore } = useTimeline(getTimelineFilters());

  const { messages, loading: messagesLoading, total: totalMessages } = useMessages(selectedMessageApp);
  const { calls, loading: callsLoading, total: totalCalls } = useCalls();
  const { contacts, loading: contactsLoading, total: totalContacts } = useContacts();
  const { media, loading: mediaLoading, total: totalMedia } = useMedia();
  const { apps, loading: appsLoading, total: totalApps } = useApps();
  const { accounts, loading: accountsLoading, total: totalAccounts } = useAccounts();
  const { events: systemEvents, loading: systemLoading, total: totalSystem } = useSystemEvents();
  const { locations, loading: locationsLoading, total: totalLocations } = useLocations();
  const { events: networkEvents, loading: networkLoading, total: totalNetwork } = useNetwork();
  const { history, searches, downloads, totalHistory, totalSearches, totalDownloads, loading: browserLoading } = useBrowserHistory();

  const handleSelectEvent = (event: TimelineEvent) => {
    setSelectedEventId(event.id);
  };

  // const handleClearFilters = () => {
  //   setActiveFilter('all');
  //   setTimeRange('7d');
  //   setCustomFromDate('2026-07-17T00:00');
  //   setCustomToDate('2026-07-24T23:59');
  //   setSearchTerm('');
  //   setSelectedSources(['whatsapp', 'telegram', 'signal', 'sms', 'phone', 'chrome', 'system']);
  //   setBucketMode('exact');
  // };

  // Client-side local filters to check checkboxes state and search query
  const filteredEvents = events.filter(evt => {
    // 1. Source checkbox filters
    const app = (evt.source_app || '').toLowerCase();
    const type = (evt.event_type || '').toLowerCase();
    
    let matchesCheckbox = false;
    if (selectedSources.includes('whatsapp') && app.includes('whatsapp')) matchesCheckbox = true;
    if (selectedSources.includes('telegram') && app.includes('telegram')) matchesCheckbox = true;
    if (selectedSources.includes('signal') && app.includes('signal')) matchesCheckbox = true;
    if (selectedSources.includes('sms') && (app.includes('sms') || type.includes('sms'))) matchesCheckbox = true;
    if (selectedSources.includes('phone') && (app.includes('phone') || app.includes('call') || type.includes('call') || app === 'phone')) matchesCheckbox = true;
    if (selectedSources.includes('chrome') && (app.includes('chrome') || app.includes('browser') || type.includes('browser'))) matchesCheckbox = true;
    if (selectedSources.includes('system') && (app.includes('system') || app.includes('logcat') || type.includes('system') || type.includes('logcat'))) matchesCheckbox = true;
    
    if (!matchesCheckbox) return false;

    // 2. Keyword search
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const fields = [
        evt.title,
        evt.summary,
        evt.sender,
        evt.receiver,
        evt.phone_number,
        evt.email,
        evt.source_app,
        evt.source_type,
        evt.file_path,
        evt.media_path
      ];
      if (!fields.some(f => String(f || '').toLowerCase().includes(term))) return false;
    }
    return true;
  });

  const warningsList = summary?.warnings || [];
  const missingSources = summary?.missing_sources || [];
  const warningsCount = warningsList.length + missingSources.length;

  const renderContent = () => {
    if (activeView === 'case-info') {
      return <CaseInfoPage />;
    }
    
    if (activeView === 'timeline') {
      return (
        <div className="flex flex-col h-full space-y-3 overflow-hidden">
          
          {/* Header titles */}
          <div className="flex-shrink-0 select-none">
            <h2 className="text-sm font-black tracking-wider uppercase text-text-primary">RAW EVENT TIMELINE</h2>
            <p className="text-text-secondary text-[11px] font-semibold mt-0.5">
              Exact events normalized from Android, apps, browser, media, network, and system sources
            </p>
          </div>

          {/* Header query filters & bucket controls */}
          <FiltersBar 
            activeFilter={activeFilter} 
            onFilterChange={setActiveFilter}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            bucketMode={bucketMode}
            onBucketModeChange={setBucketMode}
          />
          
          {/* 3-Column Layout: Center Timeline List + Right Details Panel */}
          <div className="flex-1 flex gap-6 overflow-hidden min-h-0">
            {/* Center Timeline */}
            <div className="flex-1 overflow-y-auto bg-panel-alt rounded-xl border border-border p-4 shadow-inner">
              {filteredEvents.length === 0 && !eventsLoading ? (
                <EmptyState message="No timeline events match this search." />
              ) : (
                <Timeline 
                  events={filteredEvents} 
                  loading={eventsLoading} 
                  onSelectEvent={handleSelectEvent}
                  selectedEventId={selectedEventId}
                  onLoadMore={loadMore}
                  hasMore={events.length < totalEvents}
                />
              )}
            </div>
            
            {/* Right Details Panel */}
            <div className="w-[360px] md:w-[380px] flex-shrink-0 flex flex-col h-full">
              <EventDetailsPanel 
                eventId={selectedEventId} 
                onClose={() => setSelectedEventId(undefined)} 
                filteredEvents={filteredEvents}
                onSelectEvent={handleSelectEvent}
              />
            </div>
          </div>
        </div>
      );
    }
    
    if (activeView === 'messages') {
      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'app', label: 'App', render: (val: string) => <span className="capitalize text-accent font-bold">{val}</span> },
        { key: 'sender', label: 'Sender' },
        { key: 'receiver', label: 'Receiver' },
        { key: 'body', label: 'Message', render: (val: string) => <ExpandableText text={val} /> }
      ];

      return (
        <div className="flex flex-col h-full space-y-4 overflow-hidden">
          {/* Header titles */}
          <div className="flex-shrink-0 select-none">
            <h2 className="text-sm font-black tracking-wider uppercase text-text-primary">MESSAGES OUTBOX & INBOX</h2>
            <p className="text-text-secondary text-[11px] font-semibold mt-0.5">
              Acquired and normalized message chat threads across standard apps and SMS channels
            </p>
          </div>

          {/* App Filter Switcher Chips */}
          <div className="flex items-center gap-1.5 bg-panel border border-border p-1 rounded-lg w-fit flex-shrink-0 select-none">
            {[
              { id: 'all', label: 'All Messages' },
              { id: 'sms', label: 'SMS History' },
              { id: 'WhatsApp', label: 'WhatsApp' },
              { id: 'Telegram', label: 'Telegram' },
              { id: 'Signal', label: 'Signal' }
            ].map(app => (
              <button
                key={app.id}
                onClick={() => setSelectedMessageApp(app.id)}
                className={`px-3 py-1 text-[10px] font-bold rounded uppercase tracking-wider transition-all duration-150 ${
                  selectedMessageApp === app.id
                    ? 'bg-accent text-white shadow-sm'
                    : 'text-text-secondary hover:text-text-primary hover:bg-panel-alt'
                }`}
              >
                {app.label}
              </button>
            ))}
          </div>

          {/* Message List Grid */}
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            {messages.length === 0 && !messagesLoading ? (
              <div className="flex-1 flex items-center justify-center border border-border rounded-xl bg-panel-alt h-full p-8 text-center">
                <div className="max-w-sm space-y-2 animate-in fade-in duration-200">
                  <AlertCircle className="w-8 h-8 text-warning mx-auto animate-pulse" />
                  <p className="text-sm font-semibold text-text-primary">No messages found for this app filter.</p>
                  <p className="text-xs text-text-secondary">Verify that the acquisition pipeline successfully extracted chats from this source.</p>
                </div>
              </div>
            ) : (
              <CategoryView title="Messages" columns={columns} data={messages} loading={messagesLoading} total={totalMessages} />
            )}
          </div>
        </div>
      );
    }

    
    if (activeView === 'calls') {
      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'app', label: 'App', render: (val: string) => <span className="capitalize">{val}</span> },
        { 
          key: 'from_number', 
          label: 'Caller',
          render: (val: string, row: any) => {
            if (val === 'Me') return 'Me';
            return row.contact_name ? `${row.contact_name} (${val})` : val;
          }
        },
        { 
          key: 'to_number', 
          label: 'Callee',
          render: (val: string, row: any) => {
            if (val === 'Me') return 'Me';
            return row.contact_name ? `${row.contact_name} (${val})` : val;
          }
        },
        { key: 'direction', label: 'Type', render: (val: string) => <span className="capitalize">{val}</span> },
        { key: 'duration_seconds', label: 'Duration', render: (val: number) => formatDuration(val) }
      ];
      return <CategoryView title="Calls" columns={columns} data={calls} loading={callsLoading} total={totalCalls} />;
    }
    
    if (activeView === 'contacts') {
      const columns = [
        { key: 'name', label: 'Name' },
        { key: 'phone', label: 'Phone' },
        { key: 'email', label: 'Email' },
        { key: 'source_app', label: 'Source' },
      ];
      return <CategoryView title="Contacts" columns={columns} data={contacts} loading={contactsLoading} total={totalContacts} />;
    }
    
    if (activeView === 'media') {
      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'source_app', label: 'Source' },
        { key: 'path', label: 'Filename', render: (val: string) => <span className="truncate max-w-xs block" title={val}>{val}</span> },
        { key: 'mime_type', label: 'Type' },
        { key: 'size_bytes', label: 'Size', render: (val: number) => formatBytes(val) }
      ];
      return <CategoryView title="Media" columns={columns} data={media} loading={mediaLoading} total={totalMedia} />;
    }
    
    if (activeView === 'apps') {
      const columns = [
        { key: 'app_name', label: 'App Name' },
        { key: 'package_name', label: 'Package' },
        { key: 'version_name', label: 'Version' },
        { key: 'install_time', label: 'Installed', render: (val: any) => formatTimestamp(val) },
        { key: 'is_system_app', label: 'System App', render: (val: boolean) => (
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${val ? 'bg-accent/20 text-accent' : 'bg-success/20 text-success'}`}>
            {val ? 'Yes' : 'No'}
          </span>
        )},
      ];
      return <CategoryView title="Apps" columns={columns} data={apps} loading={appsLoading} total={totalApps} />;
    }
    
    if (activeView === 'accounts') {
      const columns = [
        { key: 'account_name', label: 'Account Name' },
        { key: 'account_type', label: 'Account Type' },
        { key: 'email', label: 'Email' },
      ];
      return <CategoryView title="Accounts" columns={columns} data={accounts} loading={accountsLoading} total={totalAccounts} />;
    }
    
    if (activeView === 'system') {
      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'event_type', label: 'Event Type' },
        { key: 'severity', label: 'Severity', render: (val: string) => {
          const color = val === 'critical' ? 'bg-danger/20 text-danger' 
            : val === 'warning' ? 'bg-warning/20 text-warning' 
            : val === 'error' ? 'bg-danger/20 text-danger'
            : 'bg-success/20 text-success';
          return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>{val}</span>;
        }},
        { key: 'title', label: 'Title' },
        { key: 'summary', label: 'Summary', render: (val: string) => <span className="truncate max-w-xs block" title={val}>{truncateText(val, 60)}</span> },
      ];
      return <CategoryView title="System Logs" columns={columns} data={systemEvents} loading={systemLoading} total={totalSystem} />;
    }
    
    if (activeView === 'locations') {
      if (locations.length === 0 && !locationsLoading) {
        return (
          <div className="flex-1 flex items-center justify-center border border-border rounded-xl bg-panel-alt h-full p-8 text-center">
            <div className="max-w-sm space-y-2">
              <AlertCircle className="w-8 h-8 text-warning mx-auto animate-pulse" />
              <p className="text-sm font-semibold text-text-primary">Location evidence unavailable for this case.</p>
              <p className="text-xs text-text-secondary">GPS, Wifi, and cell triangulation logs are missing or uncollected.</p>
            </div>
          </div>
        );
      }

      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'latitude', label: 'Latitude' },
        { key: 'longitude', label: 'Longitude' },
        { key: 'accuracy', label: 'Accuracy' },
        { key: 'source', label: 'Source' },
      ];
      return <CategoryView title="Locations" columns={columns} data={locations} loading={locationsLoading} total={totalLocations} />;
    }
    
    if (activeView === 'network') {
      const columns = [
        { key: 'timestamp', label: 'Time' },
        { key: 'type', label: 'Type' },
        { key: 'source', label: 'Source' },
        { key: 'ip', label: 'IP Address' },
        { key: 'ssid', label: 'SSID' },
        { key: 'carrier', label: 'Carrier' },
      ];
      return <CategoryView title="Network" columns={columns} data={networkEvents} loading={networkLoading} total={totalNetwork} />;
    }
    
    if (activeView === 'browser') {
      if (history.length === 0 && searches.length === 0 && downloads.length === 0 && !browserLoading) {
        return (
          <div className="flex-1 flex items-center justify-center border border-border rounded-xl bg-panel-alt h-full p-8 text-center">
            <div className="max-w-sm space-y-2">
              <AlertCircle className="w-8 h-8 text-warning mx-auto" />
              <p className="text-sm font-semibold text-text-primary">Browser history unavailable or not collected.</p>
              <p className="text-xs text-text-secondary">No local searches, downloads or Chrome browsing history files were found.</p>
            </div>
          </div>
        );
      }

      const historyColumns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'browser', label: 'Browser' },
        { key: 'title', label: 'Title' },
        { key: 'url', label: 'URL', render: (val: string) => <span className="truncate max-w-xs block" title={val}>{truncateText(val, 60)}</span> },
        { key: 'visit_count', label: 'Visits' },
      ];
      const searchColumns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'browser', label: 'Browser' },
        { key: 'search_term', label: 'Search Term' },
        { key: 'url', label: 'URL', render: (val: string) => <span className="truncate max-w-xs block" title={val}>{truncateText(val, 60)}</span> },
      ];
      const downloadColumns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'browser', label: 'Browser' },
        { key: 'target_path', label: 'Target Path' },
        { key: 'mime_type', label: 'Type' },
        { key: 'total_bytes', label: 'Size', render: (val: number) => formatBytes(val) },
      ];
      return (
        <div className="space-y-6 h-full overflow-y-auto pr-1">
          <CategoryView title="Browser History" columns={historyColumns} data={history} loading={browserLoading} total={totalHistory} />
          <CategoryView title="Browser Searches" columns={searchColumns} data={searches} loading={browserLoading} total={totalSearches} />
          <CategoryView title="Browser Downloads" columns={downloadColumns} data={downloads} loading={browserLoading} total={totalDownloads} />
        </div>
      );
    }
    
    return (
      <div className="flex-1 flex items-center justify-center text-text-secondary border border-border rounded-lg bg-panel-alt">
        <p>This view ({activeView}) is not fully implemented in the preview.</p>
      </div>
    );
  };

  if (summaryLoading || intakeComplete === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="text-center">
          <LoadingSpinner />
          <p className="mt-4 text-text-secondary">Loading case data...</p>
        </div>
      </div>
    );
  }

  if (summaryError || !summary) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="text-center text-danger p-6 border border-danger/20 rounded-xl bg-panel max-w-md">
          <ShieldAlert className="w-10 h-10 text-danger mx-auto mb-3" />
          <p className="text-lg font-bold mb-2">Failed to load dashboard</p>
          <p className="text-xs text-text-secondary">{summaryError || "No case summary found. Did you build the index?"}</p>
        </div>
      </div>
    );
  }

  if (!intakeComplete) {
    return (
      <CaseIntakeWizard 
        caseId={summary.case_id} 
        exhibitId={summary.exhibit_id} 
        onComplete={() => setIntakeComplete(true)} 
      />
    );
  }

  return (
    <div className="flex h-screen bg-bg text-text-primary overflow-hidden font-sans select-text">
      {/* Sidebar Navigation */}
      <Sidebar 
        summary={summary} 
        activeView={activeView} 
        onViewChange={setActiveView} 
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        customFromDate={customFromDate}
        onCustomFromDateChange={setCustomFromDate}
        customToDate={customToDate}
        onCustomToDateChange={setCustomToDate}
        selectedSources={selectedSources}
        onSelectedSourcesChange={setSelectedSources}
      />
      
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <TopBar 
          summary={summary} 
          timeRange={timeRange} 
          onTimeRangeChange={setTimeRange}
        />
        
        <main className="flex-1 overflow-hidden p-5 flex flex-col">
          <div className="flex-1 min-h-0 overflow-hidden">
            {renderContent()}
          </div>
          
          {/* Sticky Forensic Warning Page Footer */}
          <div className="mt-3 p-2 bg-warning/5 border border-warning/20 rounded flex items-center justify-center gap-2 text-warning text-[9px] font-extrabold tracking-wider uppercase shadow-sm flex-shrink-0">
            <AlertTriangle className="w-3.5 h-3.5 text-warning animate-pulse" />
            <span>Forensic Preview Only — Not a Full Examination</span>
          </div>
        </main>

        {/* Bottom Summary Strip */}
        <BottomSummaryStrip summary={summary} />
      </div>

      {/* Warnings & Missing Sources Modal Overlay */}
      {showWarningsModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-panel border border-border rounded-xl max-w-lg w-full flex flex-col max-h-[80vh] shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-border bg-panel-alt">
              <div className="flex items-center gap-2 text-warning">
                <AlertTriangle className="w-5 h-5" />
                <h3 className="font-bold text-text-primary">Pipeline Warnings & Missing Sources</h3>
              </div>
              <button 
                onClick={() => setShowWarningsModal(false)}
                className="p-1 hover:bg-panel-alt rounded-lg text-text-secondary hover:text-text-primary transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-4 overflow-y-auto space-y-4 text-xs">
              {warningsList.length > 0 && (
                <div className="space-y-1.5">
                  <h4 className="font-bold text-warning uppercase text-[10px] tracking-wide">Warnings ({warningsList.length})</h4>
                  <ul className="space-y-1 list-disc pl-4 text-text-secondary">
                    {warningsList.map((w, idx) => (
                      <li key={idx} className="leading-relaxed">{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              {missingSources.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-border/50">
                  <h4 className="font-bold text-text-primary uppercase text-[10px] tracking-wide">Missing Artifact Sources ({missingSources.length})</h4>
                  <ul className="space-y-1 list-disc pl-4 text-text-secondary font-mono">
                    {missingSources.map((ms, idx) => (
                      <li key={idx} className="text-[10px]">{ms}</li>
                    ))}
                  </ul>
                </div>
              )}
              {warningsCount === 0 && (
                <p className="text-center text-text-secondary py-8 font-medium">No warnings or missing sources detected in this triage pipeline.</p>
              )}
            </div>
            
            <div className="p-3 border-t border-border bg-panel-alt flex justify-end">
              <button 
                onClick={() => setShowWarningsModal(false)}
                className="px-4 py-1.5 bg-accent hover:bg-accent-hover text-white text-xs font-semibold rounded-lg transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
