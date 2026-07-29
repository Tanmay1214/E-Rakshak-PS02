import { useState, useEffect } from 'react';
import { useCaseSummary } from '../hooks/useCaseSummary';
import { useTimeline } from '../hooks/useTimeline';
import Sidebar from '../components/Sidebar';
import TopBar from '../components/TopBar';
import FiltersBar from '../components/FiltersBar';
import StatCards from '../components/StatCards';
import Timeline from '../components/Timeline';
import EventDetailsPanel from '../components/EventDetailsPanel';
import KeywordSearch from '../components/KeywordSearch';
import CategoryView from '../components/CategoryView';
import LoadingSpinner from '../components/LoadingSpinner';
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
import type {  TimelineEvent  } from '../types/evidence';
import { formatTimestamp, formatDuration, formatBytes, truncateText } from '../utils/formatters';

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

  useEffect(() => {
    fetchIntakeStatus()
      .then(res => setIntakeComplete(res.complete))
      .catch(err => {
        console.error("Error fetching intake status", err);
        setIntakeComplete(false);
      });
  }, []);
  
  const getTimelineFilters = () => {
    if (activeFilter === 'all') return {};
    if (['whatsapp', 'telegram', 'signal'].includes(activeFilter)) {
      // API expects exact case for source_app (e.g., 'WhatsApp', 'Telegram', 'Signal')
      const sourceMap: Record<string, string> = {
        'whatsapp': 'WhatsApp',
        'telegram': 'Telegram',
        'signal': 'Signal'
      };
      return { source: sourceMap[activeFilter] };
    }
    if (activeFilter === 'location') return { category: 'locations' };
    return { category: activeFilter };
  };
  
  const { events, loading: eventsLoading, total: totalEvents, loadMore } = useTimeline(getTimelineFilters());

  const { messages, loading: messagesLoading, total: totalMessages } = useMessages();
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

  const renderContent = () => {
    if (activeView === 'case-info') {
      return <CaseInfoPage />;
    }
    
    if (activeView === 'timeline') {
      return (
        <div className="flex flex-col h-full relative">
          <div className="flex items-center justify-between mb-6">
            <FiltersBar activeFilter={activeFilter} onFilterChange={setActiveFilter} />
            <KeywordSearch onSearch={() => {}} />
          </div>
          
          <StatCards summary={summary} />
          
          <div className="flex-1 overflow-auto bg-panel-alt rounded-lg border border-border p-4">
            <Timeline 
              events={events} 
              loading={eventsLoading} 
              onSelectEvent={handleSelectEvent}
              selectedEventId={selectedEventId}
              onLoadMore={loadMore}
              hasMore={events.length < totalEvents}
            />
          </div>
        </div>
      );
    }
    
    if (activeView === 'messages') {
      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'app', label: 'App', render: (val: string) => <span className="capitalize text-accent">{val}</span> },
        { key: 'sender', label: 'Sender' },
        { key: 'receiver', label: 'Receiver' },
        { key: 'body', label: 'Message', render: (val: string) => <ExpandableText text={val} /> }
      ];
      return <CategoryView title="Messages" columns={columns} data={messages} loading={messagesLoading} total={totalMessages} />;
    }
    
    if (activeView === 'calls') {
      const columns = [
        { key: 'timestamp', label: 'Time', render: (val: any) => formatTimestamp(val) },
        { key: 'app', label: 'App', render: (val: string) => <span className="capitalize">{val}</span> },
        { key: 'from_number', label: 'Caller' },
        { key: 'to_number', label: 'Callee' },
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
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${val ? 'bg-accent/20 text-accent' : 'bg-success/20 text-success'}`}>
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
          return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{val}</span>;
        }},
        { key: 'title', label: 'Title' },
        { key: 'summary', label: 'Summary', render: (val: string) => <span className="truncate max-w-xs block" title={val}>{truncateText(val, 60)}</span> },
      ];
      return <CategoryView title="System Logs" columns={columns} data={systemEvents} loading={systemLoading} total={totalSystem} />;
    }
    
    if (activeView === 'locations') {
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
        <div className="space-y-6">
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
        <div className="text-center text-danger">
          <p className="text-xl font-medium mb-2">Failed to load dashboard</p>
          <p>{summaryError || "No case summary found. Did you build the index?"}</p>
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
    <div className="flex h-screen bg-bg text-text-primary overflow-hidden font-sans">
      <Sidebar summary={summary} activeView={activeView} onViewChange={setActiveView} />
      
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar summary={summary} />
        
        <main className="flex-1 overflow-hidden relative flex">
          <div className="flex-1 p-6 overflow-y-auto">
            {renderContent()}
          </div>
          
          {selectedEventId && (
            <div className="absolute inset-y-0 right-0 z-20">
              <EventDetailsPanel eventId={selectedEventId} onClose={() => setSelectedEventId(undefined)} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
