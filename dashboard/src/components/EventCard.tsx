import type { TimelineEvent } from '../types/evidence';
import { getIconForSource } from '../utils/icons';
import { formatEventTime } from '../utils/formatters';

interface EventCardProps {
  event: TimelineEvent;
  onSelect: (event: TimelineEvent) => void;
  isSelected?: boolean;
}

export default function EventCard({ event, onSelect, isSelected }: EventCardProps) {
  const { icon: Icon, color, bg, border } = getIconForSource(event.source_app, event.event_type);

  // Shorten hash for displays
  const formatHash = (hash: string | undefined) => {
    if (!hash) return '';
    const clean = hash.trim();
    if (clean.length > 12) {
      return `${clean.substring(0, 6)}...${clean.substring(clean.length - 4)}`;
    }
    return clean;
  };

  // Confidence color map
  const getConfidenceBadge = (conf: string | undefined) => {
    if (!conf) return null;
    const c = conf.toLowerCase();
    let style = 'bg-slate-500/10 text-slate-400 border border-slate-500/20';
    if (c === 'high') style = 'bg-success/15 text-success border border-success/35';
    if (c === 'medium') style = 'bg-warning/15 text-warning border border-warning/35';
    if (c === 'low') style = 'bg-danger/15 text-danger border border-danger/35';
    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wide uppercase ${style}`}>
        Confidence: {c}
      </span>
    );
  };

  return (
    <div 
      onClick={() => onSelect(event)}
      className="relative pl-10 pb-6 group cursor-pointer"
    >
      {/* Glow Timeline vertical connector */}
      <div className={`absolute left-[15px] top-8 bottom-0 w-[2px] transition-colors duration-300 ${
        isSelected ? 'bg-accent/60' : 'bg-border group-hover:bg-border/80'
      } group-last:hidden`} />
      
      {/* Node Bullet point */}
      <div 
        className={`absolute left-0 top-1 w-8 h-8 rounded-full flex items-center justify-center z-10 transition-all duration-300 ${bg} border ${border} ${
          isSelected 
            ? 'scale-110 ring-4 ring-accent/30 border-accent' 
            : 'group-hover:scale-105 group-hover:border-text-secondary/30'
        }`}
      >
        <Icon className={`w-4 h-4 ${color}`} />
      </div>

      {/* Main card box container */}
      <div className={`bg-panel border rounded-xl p-4 transition-all duration-300 shadow-sm ${
        isSelected 
          ? 'border-accent/80 bg-panel-alt shadow-lg ring-1 ring-accent/10 translate-x-1' 
          : 'border-border hover:border-border/80 hover:bg-panel-alt/40 hover:shadow-md'
      }`}>
        {/* Top header parameters */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded uppercase tracking-wider ${color} ${bg} border ${border}`}>
              {event.source_app || event.event_type}
            </span>
            <span className="text-[11px] text-text-secondary font-semibold font-mono">
              {formatEventTime(event.timestamp, event.timestamp_sort)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {getConfidenceBadge(event.confidence)}
            {event.deleted && (
              <span className="px-2 py-0.5 rounded bg-danger/15 text-danger border border-danger/25 text-[10px] font-extrabold uppercase tracking-wide">
                DELETED
              </span>
            )}
            {event.recovered && (
              <span className="px-2 py-0.5 rounded bg-success/15 text-success border border-success/25 text-[10px] font-extrabold uppercase tracking-wide animate-pulse">
                RECOVERED
              </span>
            )}
          </div>
        </div>

        {/* Title */}
        <h3 className="text-sm font-semibold text-text-primary mb-1.5 group-hover:text-accent transition-colors">
          {event.title}
        </h3>

        {/* Summary Description block (2 lines max clamp) */}
        <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed mb-3.5 whitespace-pre-line">
          {event.summary}
        </p>

        {/* Footer forensic parameters */}
        {(event.source_type || event.parser || event.source_file || event.source_hash) && (
          <div className="pt-2.5 border-t border-border/60 flex flex-wrap gap-x-4 gap-y-1.5 text-[10px] text-text-secondary font-mono">
            {event.source_type && (
              <div>
                <span className="text-text-secondary/50">Lane:</span>{' '}
                <span className="text-text-secondary/85 capitalize">{event.source_type.replace('_', ' ')}</span>
              </div>
            )}
            {event.parser && (
              <div>
                <span className="text-text-secondary/50">Parser:</span>{' '}
                <span className="text-text-secondary/85">{event.parser}</span>
              </div>
            )}
            {event.source_hash && (
              <div title={event.source_hash}>
                <span className="text-text-secondary/50">SHA-256:</span>{' '}
                <span className="text-text-secondary/85">{formatHash(event.source_hash)}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
