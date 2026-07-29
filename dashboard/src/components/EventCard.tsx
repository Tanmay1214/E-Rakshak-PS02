import type { TimelineEvent } from '../types/evidence';
import { getIconForSource } from '../utils/icons';
import { formatEventDate, formatEventTime } from '../utils/formatters';
import { AlertCircle } from 'lucide-react';

interface EventCardProps {
  event: TimelineEvent;
  onSelect: (event: TimelineEvent) => void;
  isSelected?: boolean;
}

export default function EventCard({ event, onSelect, isSelected }: EventCardProps) {
  const { icon: Icon, color, bg, border } = getIconForSource(event.source_app, event.event_type);
  const isDeleted = !!event.deleted;

  const dotClass = getDotStyle(event.source_app || '', event.event_type || '', isDeleted);
  const appBadgeClass = getAppBadgeStyle(event.source_app || event.event_type || '');

  // Confidence color map
  const getConfidenceStyle = (conf: string | undefined) => {
    if (!conf) return 'border-slate-500/20 text-slate-400';
    const c = conf.toLowerCase();
    if (c === 'high') return 'border-emerald-500/30 text-emerald-400';
    if (c === 'medium') return 'border-amber-500/30 text-amber-400';
    return 'border-red-500/30 text-red-400';
  };

  // Check if this is a QR code mockup event
  const isQR = event.summary && (event.summary.toLowerCase().includes('qr') || event.summary.toLowerCase().includes('payment') || event.summary.toLowerCase().includes('payment_qr'));

  return (
    <div 
      onClick={() => onSelect(event)}
      className="flex items-stretch select-none cursor-pointer group py-1.5"
    >
      {/* 1. Time details left column */}
      <div className="w-24 text-right pr-5 flex-shrink-0 font-mono self-center">
        <div className="text-[11px] text-text-primary font-bold tracking-tight">
          {formatEventDate(event.timestamp, event.timestamp_sort)}
        </div>
        <div className="text-[9.5px] text-text-secondary font-medium mt-0.5 opacity-80">
          {formatEventTime(event.timestamp, event.timestamp_sort)}
        </div>
      </div>

      {/* 2. Middle timeline bullet point and vertical connector line */}
      <div className="w-8 relative flex flex-col items-center flex-shrink-0">
        {/* Continuous connector line */}
        <div className={`absolute top-0 bottom-0 w-[1.5px] bg-border/60 ${
          isSelected ? 'bg-accent/40' : 'group-hover:bg-border/80'
        }`} />
        
        {/* Circle dot node */}
        <div className={`absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full border-2 z-10 transition-all duration-200 ${dotClass} ${
          isSelected ? 'scale-125 ring-4 ring-accent/20' : 'group-hover:scale-110'
        }`} />
      </div>

      {/* 3. Card body container on the right */}
      <div className={`flex-1 ml-3 bg-panel border rounded-lg p-3 transition-all duration-200 flex items-center justify-between shadow-sm min-w-0 ${
        isDeleted 
          ? isSelected 
            ? 'border-red-500/70 bg-red-500/5 shadow-red-500/5 ring-1 ring-red-500/20'
            : 'border-red-500/40 hover:border-red-500/60 bg-red-500/[0.02]'
          : isSelected
            ? 'border-accent bg-accent/[0.03] ring-1 ring-accent/30 shadow-md translate-x-0.5'
            : 'border-border hover:border-border-hover hover:bg-panel-alt/30'
      }`}>
        
        {/* Left inner block: App Icon, Title, and Preview Summary */}
        <div className="flex items-center gap-3.5 min-w-0 flex-1">
          {/* Circular App icon */}
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${bg} border ${border} ${
            isDeleted ? 'bg-red-500/10 border-red-500/30' : ''
          }`}>
            {isDeleted ? (
              <AlertCircle className="w-4.5 h-4.5 text-red-500 animate-pulse" />
            ) : (
              <Icon className={`w-4.5 h-4.5 ${color}`} />
            )}
          </div>

          {/* Title and Summary lines */}
          <div className="min-w-0 flex-1">
            <h4 className={`text-xs font-bold truncate transition-colors ${
              isDeleted 
                ? 'text-red-500' 
                : isSelected ? 'text-accent' : 'text-text-primary group-hover:text-accent/80'
            }`}>
              {event.title}
            </h4>
            <p className="text-[11px] text-text-secondary/90 truncate mt-0.5 font-medium min-w-0 block">
              {event.summary}
            </p>
          </div>
        </div>

        {/* Right inner block: Metadata badges stack */}
        <div className="flex items-center gap-4 flex-shrink-0 ml-4">
          
          {/* App / Source text details */}
          <div className="flex flex-col items-end gap-1 font-mono text-[9px] text-right">
            <div className="flex items-center gap-1.5">
              {isDeleted && (
                <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 text-[8px] font-extrabold uppercase tracking-wide">
                  Deleted Marker
                </span>
              )}
              {event.source_app && (
                <span className={`px-1.5 py-0.5 rounded font-bold uppercase border tracking-wider text-[8px] ${appBadgeClass}`}>
                  {event.source_app}
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-1.5">
              {event.confidence && (
                <span className={`px-1.5 py-0.5 rounded border uppercase tracking-wider text-[8px] font-bold ${getConfidenceStyle(event.confidence)}`}>
                  {event.confidence}
                </span>
              )}
              {event.source_type && (
                <span className="text-text-secondary/70 max-w-[120px] truncate text-[9px] uppercase tracking-wider">
                  {event.source_type}
                </span>
              )}
            </div>
          </div>

          {/* Scannable payment QR placeholder for matches */}
          {isQR && (
            <div className="w-9 h-9 border border-border bg-white rounded flex items-center justify-center p-0.5 shadow-sm hover:scale-105 transition-transform" title="Scanned QR asset">
              <img 
                src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=forensic-exhibit-qr" 
                alt="QR Code" 
                className="w-full h-full object-contain filter contrast-125 brightness-95" 
                onError={(e) => {
                  // Fallback if network offline
                  e.currentTarget.style.display = 'none';
                }}
              />
            </div>
          )}

        </div>

      </div>
    </div>
  );
}

// Color helpers
const getDotStyle = (sourceApp: string, eventType: string, isDeleted: boolean) => {
  if (isDeleted) {
    return 'bg-red-500 border-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]';
  }
  const s = sourceApp.toLowerCase();
  const t = eventType.toLowerCase();
  if (s.includes('whatsapp')) return 'bg-emerald-500 border-emerald-500/50 shadow-[0_0_6px_rgba(16,185,129,0.3)]';
  if (s.includes('telegram')) return 'bg-cyan-500 border-cyan-500/50 shadow-[0_0_6px_rgba(6,182,212,0.3)]';
  if (s.includes('signal')) return 'bg-indigo-500 border-indigo-500/50 shadow-[0_0_6px_rgba(99,102,241,0.3)]';
  if (s.includes('sms') || t.includes('sms')) return 'bg-violet-500 border-violet-500/50 shadow-[0_0_6px_rgba(139,92,246,0.3)]';
  if (t.includes('call') || s.includes('call') || s === 'phone') return 'bg-blue-500 border-blue-500/50 shadow-[0_0_6px_rgba(59,130,246,0.3)]';
  if (t.includes('browser') || s.includes('browser') || s.includes('chrome')) return 'bg-cyan-400 border-cyan-400/50 shadow-[0_0_6px_rgba(34,211,238,0.3)]';
  if (t.includes('location') || s.includes('location') || s.includes('gps')) return 'bg-amber-500 border-amber-500/50 shadow-[0_0_6px_rgba(245,158,11,0.3)]';
  if (t.includes('media') || s.includes('media')) return 'bg-purple-500 border-purple-500/50 shadow-[0_0_6px_rgba(168,85,247,0.3)]';
  return 'bg-slate-500 border-slate-500/50';
};

const getAppBadgeStyle = (app: string) => {
  const a = app.toLowerCase();
  if (a.includes('whatsapp')) return 'bg-emerald-500/10 border-emerald-500/35 text-emerald-400';
  if (a.includes('telegram')) return 'bg-cyan-500/10 border-cyan-500/35 text-cyan-400';
  if (a.includes('signal')) return 'bg-indigo-500/10 border-indigo-500/35 text-indigo-400';
  if (a.includes('sms')) return 'bg-violet-500/10 border-violet-500/35 text-violet-400';
  if (a.includes('phone') || a.includes('call')) return 'bg-blue-500/10 border-blue-500/35 text-blue-400';
  if (a.includes('chrome') || a.includes('browser')) return 'bg-sky-500/10 border-sky-500/35 text-sky-400';
  if (a.includes('location') || a.includes('exif')) return 'bg-amber-500/10 border-amber-500/35 text-amber-400';
  if (a.includes('media') || a.includes('mediastore')) return 'bg-purple-500/10 border-purple-500/35 text-purple-400';
  return 'bg-slate-500/10 border-slate-500/35 text-slate-400';
};
