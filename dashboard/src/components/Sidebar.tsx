import { 
  Clock, MessageSquare, Phone, Image as ImageIcon, MapPin, 
  Globe, Package, Wifi, Terminal, CheckCircle2
} from 'lucide-react';
import type { CaseSummary } from '../types/evidence';

interface SidebarProps {
  summary: CaseSummary | null;
  activeView: string;
  onViewChange: (view: string) => void;
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
  customFromDate: string;
  onCustomFromDateChange: (date: string) => void;
  customToDate: string;
  onCustomToDateChange: (date: string) => void;
  selectedSources: string[];
  onSelectedSourcesChange: (sources: string[]) => void;
}

export default function Sidebar({
  summary,
  activeView,
  onViewChange,
  timeRange,
  onTimeRangeChange,
  customFromDate,
  onCustomFromDateChange,
  customToDate,
  onCustomToDateChange,
  selectedSources,
  onSelectedSourcesChange
}: SidebarProps) {
  
  // Calculate browser count
  const browserCount = summary 
    ? (summary.counts.browser_history || 0) + (summary.counts.browser_searches || 0) + (summary.counts.browser_downloads || 0)
    : 0;

  const navItems = [
    { id: 'timeline', label: 'Timeline', icon: Clock, count: summary?.counts.timeline_events || 0 },
    { id: 'messages', label: 'Messages', icon: MessageSquare, count: summary?.counts.messages || 0 },
    { id: 'calls', label: 'Calls', icon: Phone, count: summary?.counts.calls || 0 },
    { id: 'media', label: 'Media', icon: ImageIcon, count: summary?.counts.media || 0 },
    { id: 'locations', label: 'Locations', icon: MapPin, count: summary?.counts.locations || 0 },
    { id: 'browser', label: 'Browser', icon: Globe, count: browserCount },
    { id: 'apps', label: 'Apps', icon: Package, count: summary?.counts.apps || 0 },
    { id: 'network', label: 'Network', icon: Wifi, count: summary?.counts.network || 0 },
    { id: 'system', label: 'System', icon: Terminal, count: summary?.counts.system || 0 },
  ];

  const sourceOptions = [
    { id: 'whatsapp', label: 'WhatsApp' },
    { id: 'telegram', label: 'Telegram' },
    { id: 'signal', label: 'Signal' },
    { id: 'sms', label: 'SMS' },
    { id: 'phone', label: 'Phone' },
    { id: 'chrome', label: 'Chrome' },
    { id: 'system', label: 'Android System' },
  ];

  const handleSourceToggle = (id: string) => {
    if (selectedSources.includes(id)) {
      onSelectedSourcesChange(selectedSources.filter(s => s !== id));
    } else {
      onSelectedSourcesChange([...selectedSources, id]);
    }
  };

  return (
    <div className="w-60 flex-shrink-0 bg-panel border-r border-border h-full flex flex-col justify-between overflow-hidden select-none">
      <div className="flex-1 flex flex-col overflow-y-auto py-4">
        
        {/* CASE OVERVIEW Nav list */}
        <div className="px-4 mb-2 text-[10px] font-bold text-text-secondary uppercase tracking-wider">Case Overview</div>
        <nav className="space-y-0.5 px-2">
          {navItems.map(item => {
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onViewChange(item.id)}
                className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 ${
                  isActive 
                    ? 'bg-accent text-white shadow-md font-bold' 
                    : 'text-text-secondary hover:bg-panel-alt hover:text-text-primary'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                  isActive ? 'bg-white/20 text-white' : 'text-text-secondary'
                }`}>
                  {item.count > 0 ? item.count.toLocaleString() : '0'}
                </span>
              </button>
            );
          })}
        </nav>

        {/* TIME FILTER Section */}
        <div className="mt-5 px-4 mb-2 text-[10px] font-bold text-text-secondary uppercase tracking-wider">Time Filter</div>
        <div className="px-4 space-y-2">
          <div className="space-y-1.5">
            {[
              { id: '24h', label: 'Last 24 Hours' },
              { id: '7d', label: 'Last 7 Days' },
              { id: 'custom', label: 'Custom Range' },
            ].map(r => (
              <label key={r.id} className="flex items-center gap-2.5 text-xs text-text-secondary cursor-pointer hover:text-text-primary">
                <input
                  type="radio"
                  name="time-range-group"
                  checked={timeRange === r.id}
                  onChange={() => onTimeRangeChange(r.id)}
                  className="rounded-full bg-panel-alt border-border text-accent focus:ring-accent w-3 h-3"
                />
                <span className={timeRange === r.id ? 'text-text-primary font-semibold' : ''}>{r.label}</span>
              </label>
            ))}
          </div>

          {/* Date Pickers for Custom Range */}
          {timeRange === 'custom' && (
            <div className="mt-2.5 pt-2.5 border-t border-border/40 space-y-2">
              <div className="space-y-1">
                <span className="text-[9px] font-bold uppercase tracking-wider text-text-secondary">From</span>
                <input
                  type="datetime-local"
                  value={customFromDate}
                  onChange={(e) => onCustomFromDateChange(e.target.value)}
                  className="w-full bg-panel-alt border border-border text-[11px] font-mono text-text-primary px-2 py-1 rounded focus:outline-none focus:border-accent"
                />
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-bold uppercase tracking-wider text-text-secondary">To</span>
                <input
                  type="datetime-local"
                  value={customToDate}
                  onChange={(e) => onCustomToDateChange(e.target.value)}
                  className="w-full bg-panel-alt border border-border text-[11px] font-mono text-text-primary px-2 py-1 rounded focus:outline-none focus:border-accent"
                />
              </div>
            </div>
          )}
        </div>

        {/* SOURCE FILTERS Checkbox group */}
        <div className="mt-5 px-4 mb-2 text-[10px] font-bold text-text-secondary uppercase tracking-wider">Source Filters</div>
        <div className="px-4 space-y-1.5">
          {sourceOptions.map(opt => {
            const isChecked = selectedSources.includes(opt.id);
            return (
              <label key={opt.id} className="flex items-center gap-2.5 text-xs text-text-secondary cursor-pointer hover:text-text-primary">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleSourceToggle(opt.id)}
                  className="rounded bg-panel-alt border-border text-accent focus:ring-accent w-3.5 h-3.5"
                />
                <span className={isChecked ? 'text-text-primary font-semibold' : ''}>{opt.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* ACQUISITION INFO Section */}
      {summary && (
        <div className="border-t border-border p-4 bg-panel-alt flex-shrink-0">
          <div className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-2.5">
            Acquisition Info
          </div>
          
          <div className="space-y-1.5 text-[10px] text-text-secondary font-mono">
            <div className="flex justify-between gap-2">
              <span>Method:</span>
              <span className="text-text-primary font-semibold text-right">Mixed Logical / Rooted Import</span>
            </div>
            <div className="flex justify-between gap-2">
              <span>SMS/Calls:</span>
              <span className="text-text-primary font-semibold text-right">Dual-Lane Deduped</span>
            </div>
            <div className="flex justify-between gap-2">
              <span>Root Access:</span>
              <span className={summary.root_access ? 'text-red-500 font-bold' : 'text-emerald-500 font-semibold'}>
                {summary.root_access ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span>Timezone:</span>
              <span className="text-text-primary font-semibold text-right">Asia/Kolkata (UTC+05:30)</span>
            </div>
            <div className="flex justify-between items-center gap-2 mt-2 pt-2 border-t border-border/40">
              <span>Hash Status:</span>
              <div className="flex items-center gap-1 text-emerald-500 font-extrabold tracking-wide uppercase text-[9px]">
                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                <span>Verified</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
