import type { CaseSummary } from '../types/evidence';
import { 
  Database, MessageSquare, Phone, Users, Image as ImageIcon, 
  MapPin, Globe, Package 
} from 'lucide-react';

interface StatCardsProps {
  summary: CaseSummary | null;
}

export default function StatCards({ summary }: StatCardsProps) {
  if (!summary) return null;

  const browserCount = (summary.counts.browser_history || 0) + 
                       (summary.counts.browser_searches || 0) + 
                       (summary.counts.browser_downloads || 0);

  const stats = [
    { label: 'Total Events', value: summary.counts.timeline_events, icon: Database, color: 'text-accent', bg: 'bg-accent/5' },
    { label: 'Messages', value: summary.counts.messages, icon: MessageSquare, color: 'text-whatsapp', bg: 'bg-whatsapp/5' },
    { label: 'Calls', value: summary.counts.calls, icon: Phone, color: 'text-blue-500', bg: 'bg-blue-500/5' },
    { label: 'Contacts', value: summary.counts.contacts, icon: Users, color: 'text-slate-300', bg: 'bg-slate-300/5' },
    { label: 'Media', value: summary.counts.media, icon: ImageIcon, color: 'text-orange-500', bg: 'bg-orange-500/5' },
    { label: 'Locations', value: summary.counts.locations, icon: MapPin, color: 'text-amber-400', bg: 'bg-amber-400/5' },
    { label: 'Browser', value: browserCount, icon: Globe, color: 'text-yellow-500', bg: 'bg-yellow-500/5' },
    { label: 'Apps', value: summary.counts.apps, icon: Package, color: 'text-emerald-500', bg: 'bg-emerald-500/5' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3.5 mb-6">
      {stats.map((s, i) => {
        const val = s.value || 0;
        const isZero = val === 0;
        return (
          <div 
            key={i} 
            className={`bg-panel border rounded-xl p-3 flex flex-col justify-between hover:border-accent/40 transition-all duration-150 shadow-sm ${
              isZero ? 'opacity-60 border-border' : 'border-border'
            }`}
          >
            <div className="flex items-center justify-between gap-1 mb-2.5">
              <span className="text-text-secondary/70 text-[9px] font-bold uppercase tracking-wider truncate">
                {s.label}
              </span>
              <div className={`p-1 rounded-md ${s.bg}`}>
                <s.icon className={`w-3.5 h-3.5 ${s.color}`} />
              </div>
            </div>
            
            <div className="flex items-baseline gap-1">
              <div className={`text-xl font-bold font-mono tracking-tight ${
                isZero ? 'text-text-secondary/30' : 'text-text-primary'
              }`}>
                {val.toLocaleString()}
              </div>
              {isZero && (
                <span className="text-[8px] font-bold text-text-secondary/40 uppercase font-mono">
                  Empty
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
