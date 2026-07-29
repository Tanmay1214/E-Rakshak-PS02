import type {  CaseSummary  } from '../types/evidence';
import { Database, MessageSquare, Phone, Users, Image as ImageIcon, Package } from 'lucide-react';

interface StatCardsProps {
  summary: CaseSummary | null;
}

export default function StatCards({ summary }: StatCardsProps) {
  if (!summary) return null;

  const stats = [
    { label: 'Total Events', value: summary.counts.timeline_events, icon: Database, color: 'text-accent' },
    { label: 'Messages', value: summary.counts.messages, icon: MessageSquare, color: 'text-whatsapp' },
    { label: 'Calls', value: summary.counts.calls, icon: Phone, color: 'text-telegram' },
    { label: 'Contacts', value: summary.counts.contacts, icon: Users, color: 'text-text-primary' },
    { label: 'Media', value: summary.counts.media, icon: ImageIcon, color: 'text-danger' },
    { label: 'Apps', value: summary.counts.apps, icon: Package, color: 'text-success' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      {stats.map((s, i) => (
        <div key={i} className="bg-panel border border-border rounded-lg p-4 flex flex-col hover:border-accent transition-colors shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-text-secondary text-xs font-medium uppercase tracking-wider">{s.label}</span>
            <s.icon className={`w-4 h-4 ${s.color}`} />
          </div>
          <div className="text-2xl font-bold text-text-primary font-mono">
            {s.value?.toLocaleString() || 0}
          </div>
        </div>
      ))}
    </div>
  );
}
