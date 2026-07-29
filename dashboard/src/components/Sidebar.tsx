import { useState } from 'react';
import { 
  Clock, MessageSquare, Phone, Users, Image as ImageIcon, MapPin, 
  Package, User, Wifi, Terminal, ShieldCheck, Globe, ChevronDown, ChevronRight,
  ClipboardList
} from 'lucide-react';
import type { CaseSummary } from '../types/evidence';

interface SidebarProps {
  summary: CaseSummary | null;
  activeView: string;
  onViewChange: (view: string) => void;
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
}

export default function Sidebar({
  summary,
  activeView,
  onViewChange,
  timeRange,
  onTimeRangeChange
}: SidebarProps) {
  const [infoOpen, setInfoOpen] = useState(true);

  // Summarize browser counts
  const browserCount = summary 
    ? (summary.counts.browser_history || 0) + (summary.counts.browser_searches || 0) + (summary.counts.browser_downloads || 0)
    : undefined;

  const navItems = [
    { id: 'case-info', label: 'Case Info', icon: ClipboardList, count: undefined },
    { id: 'timeline', label: 'Timeline', icon: Clock, count: summary?.counts.timeline_events },
    { id: 'messages', label: 'Messages', icon: MessageSquare, count: summary?.counts.messages },
    { id: 'calls', label: 'Calls', icon: Phone, count: summary?.counts.calls },
    { id: 'contacts', label: 'Contacts', icon: Users, count: summary?.counts.contacts },
    { id: 'media', label: 'Media', icon: ImageIcon, count: summary?.counts.media },
    { id: 'locations', label: 'Locations', icon: MapPin, count: summary?.counts.locations },
    { id: 'apps', label: 'Apps', icon: Package, count: summary?.counts.apps },
    { id: 'accounts', label: 'Accounts', icon: User, count: summary?.counts.accounts },
    { id: 'network', label: 'Network', icon: Wifi, count: summary?.counts.network },
    { id: 'system', label: 'System Logs', icon: Terminal, count: summary?.counts.system },
    { id: 'integrity', label: 'Integrity', icon: ShieldCheck, count: summary?.counts.integrity },
    { id: 'browser', label: 'Browser', icon: Globe, count: browserCount },
  ];

  return (
    <div className="w-64 flex-shrink-0 bg-panel border-r border-border h-screen flex flex-col justify-between overflow-hidden">
      <div className="flex-1 flex flex-col overflow-y-auto py-4">
        {/* Navigation list */}
        <div className="px-4 mb-2 text-[10px] font-bold text-text-secondary uppercase tracking-wider">Navigation</div>
        <nav className="space-y-1 px-2">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition-all duration-150 ${
                activeView === item.id 
                  ? 'bg-accent text-white shadow-md' 
                  : 'text-text-secondary hover:bg-panel-alt hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </div>
              {item.count !== undefined && (
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  activeView === item.id ? 'bg-white/20 text-white' : 'bg-panel-alt text-text-secondary'
                }`}>
                  {item.count}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Time filters list */}
        <div className="mt-6 px-4 mb-2 text-[10px] font-bold text-text-secondary uppercase tracking-wider">Time Range</div>
        <nav className="space-y-0.5 px-2">
          {[
            { id: 'all', label: 'All Time' },
            { id: '24h', label: 'Last 24 Hours' },
            { id: '7d', label: 'Last 7 Days' },
            { id: 'custom', label: 'Custom Range' },
          ].map(r => (
            <button
              key={r.id}
              onClick={() => onTimeRangeChange(r.id)}
              className={`w-full flex items-center px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 ${
                timeRange === r.id 
                  ? 'bg-panel-alt text-accent font-bold pl-2.5 border-l-2 border-accent' 
                  : 'text-text-secondary hover:bg-panel-alt/40 hover:text-text-primary pl-3'
              }`}
            >
              {r.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Acquisition Info at bottom */}
      {summary && (
        <div className="border-t border-border p-4 bg-panel-alt">
          <button 
            onClick={() => setInfoOpen(!infoOpen)}
            className="flex items-center justify-between w-full text-xs font-bold text-text-secondary uppercase tracking-wider mb-2.5"
          >
            <span>Acquisition Info</span>
            {infoOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
          
          {infoOpen && (
            <div className="space-y-2 text-[11px] text-text-secondary mt-3">
              <div className="flex justify-between">
                <span>Method:</span>
                <span className="text-text-primary font-semibold capitalize">{summary.acquisition_method || 'ADB'}</span>
              </div>
              <div className="flex justify-between">
                <span>Rooted Device:</span>
                <span className={summary.root_access ? 'text-danger font-bold' : 'text-success font-semibold'}>
                  {summary.root_access ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="flex justify-between mt-2.5 pt-2 border-t border-border/50">
                <span>Read-Only:</span>
                <span className="bg-success/20 text-success border border-success/30 px-2 py-0.5 rounded text-[9px] font-extrabold tracking-wide uppercase">
                  VERIFIED
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
