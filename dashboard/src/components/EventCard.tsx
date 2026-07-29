import type {  TimelineEvent  } from '../types/evidence';
import { getIconForSource } from '../utils/icons';
import { formatTimestamp } from '../utils/formatters';

interface EventCardProps {
  event: TimelineEvent;
  onSelect: (event: TimelineEvent) => void;
  isSelected?: boolean;
}

export default function EventCard({ event, onSelect, isSelected }: EventCardProps) {
  const { icon: Icon, color } = getIconForSource(event.source_app, event.event_type);

  return (
    <div className="relative pl-8 pb-4 group cursor-pointer" onClick={() => onSelect(event)}>
      {/* Timeline line */}
      <div className="absolute left-[15px] top-8 bottom-0 w-px bg-border group-last:hidden" />
      
      {/* Timeline icon */}
      <div className={`absolute left-0 top-1 w-8 h-8 rounded-full bg-panel border-2 border-panel flex items-center justify-center z-10 ${isSelected ? 'ring-2 ring-accent' : ''}`}>
        <div className={`w-6 h-6 rounded-full flex items-center justify-center bg-panel-alt shadow-sm ${color}`}>
          <Icon className="w-3.5 h-3.5" />
        </div>
      </div>

      <div className={`bg-panel border rounded-lg p-4 transition-all hover:-translate-y-0.5 hover:shadow-lg ${
        isSelected ? 'border-accent shadow-md' : 'border-border hover:border-text-secondary/50'
      }`}>
        <div className="flex justify-between items-start mb-2">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded uppercase ${color} bg-panel-alt`}>
              {event.source_app || event.event_type}
            </span>
            <span className="text-xs text-text-secondary">{formatTimestamp(event.timestamp)}</span>
          </div>
          <div className="flex gap-2">
            {event.deleted && <span className="px-1.5 py-0.5 rounded bg-danger/20 text-danger text-[10px] font-bold">DELETED</span>}
            {event.recovered && <span className="px-1.5 py-0.5 rounded bg-success/20 text-success text-[10px] font-bold">RECOVERED</span>}
          </div>
        </div>
        <h3 className="text-sm font-semibold text-text-primary mb-1">{event.title}</h3>
        <p className="text-xs text-text-secondary line-clamp-2">{event.summary}</p>
      </div>
    </div>
  );
}
