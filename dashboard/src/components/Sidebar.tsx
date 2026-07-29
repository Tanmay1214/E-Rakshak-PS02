import { useState } from 'react';
import { 
  Clock, MessageSquare, Phone, Users, Image as ImageIcon, MapPin, 
  Package, User, Wifi, Terminal, ShieldCheck, Globe, ChevronDown, ChevronRight,
  ClipboardList
} from 'lucide-react';
import type {  CaseSummary  } from '../types/evidence';

interface SidebarProps {
  summary: CaseSummary | null;
  activeView: string;
  onViewChange: (view: string) => void;
}

export default function Sidebar({ summary, activeView, onViewChange }: SidebarProps) {
  const [infoOpen, setInfoOpen] = useState(true);

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
    { id: 'browser', label: 'Browser', icon: Globe, count: undefined },
  ];

  return (
    <div className="w-64 flex-shrink-0 bg-panel border-r border-border h-screen flex flex-col overflow-y-auto">
      <div className="flex-1 py-4">
        <div className="px-4 mb-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">Navigation</div>
        <nav className="space-y-1 px-2">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                activeView === item.id 
                  ? 'bg-accent text-white' 
                  : 'text-text-secondary hover:bg-panel-alt hover:text-text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </div>
              {item.count !== undefined && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${activeView === item.id ? 'bg-white/20' : 'bg-panel-alt'}`}>
                  {item.count}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="mt-8 px-4 mb-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">Quick Filters</div>
        <div className="px-4 space-y-2">
          <button className="w-full text-left text-sm text-text-secondary hover:text-text-primary">All Time</button>
          <button className="w-full text-left text-sm text-text-secondary hover:text-text-primary">Last 24 Hours</button>
          <button className="w-full text-left text-sm text-text-secondary hover:text-text-primary">Last 7 Days</button>
        </div>
      </div>

      {summary && (
        <div className="border-t border-border p-4 bg-panel-alt">
          <button 
            onClick={() => setInfoOpen(!infoOpen)}
            className="flex items-center justify-between w-full text-sm font-semibold text-text-secondary mb-2"
          >
            <span>Acquisition Info</span>
            {infoOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
          
          {infoOpen && (
            <div className="space-y-2 text-xs text-text-secondary mt-3">
              <div className="flex justify-between">
                <span>Method:</span>
                <span className="text-text-primary">{summary.acquisition_method}</span>
              </div>
              <div className="flex justify-between">
                <span>Rooted:</span>
                <span className={summary.root_access ? 'text-danger' : 'text-success'}>
                  {summary.root_access ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="flex justify-between mt-2 pt-2 border-t border-border">
                <span>Read-Only:</span>
                <span className="bg-success/20 text-success px-1.5 rounded text-[10px] font-bold">VERIFIED</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
