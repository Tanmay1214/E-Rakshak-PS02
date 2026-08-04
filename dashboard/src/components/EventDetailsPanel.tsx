import { useEffect, useState } from 'react';
import type { TimelineEvent } from '../types/evidence';
import { X, AlertTriangle, Copy, Check } from 'lucide-react';
import { getIconForSource } from '../utils/icons';
import { formatTimestamp, formatEventTime } from '../utils/formatters';
import { fetchTimelineEvent, fetchTimelineEventContext } from '../services/api';
import LoadingSpinner from './LoadingSpinner';

interface EventDetailsPanelProps {
  eventId?: string;
  onClose?: () => void;
  filteredEvents?: TimelineEvent[];
  onSelectEvent?: (event: TimelineEvent) => void;
  caseId?: string;
  exhibitId?: string;
}

export default function EventDetailsPanel({
  eventId,
  onClose,
  onSelectEvent,
  caseId,
  exhibitId
}: EventDetailsPanelProps) {
  const [event, setEvent] = useState<TimelineEvent | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [contextData, setContextData] = useState<{
    previous: TimelineEvent[];
    current: TimelineEvent | null;
    next: TimelineEvent[];
  }>({
    previous: [],
    current: null,
    next: []
  });

  useEffect(() => {
    if (!eventId) {
      setEvent(null);
      setContextData({ previous: [], current: null, next: [] });
      setLoading(false);
      return;
    }
    setLoading(true);
    
    const contextFetch = caseId && exhibitId
      ? fetchTimelineEventContext(caseId, exhibitId, eventId)
      : fetchTimelineEventContext(undefined, undefined, eventId);

    Promise.all([
      fetchTimelineEvent(eventId),
      contextFetch
    ])
      .then(([eventRes, contextRes]) => {
        setEvent(eventRes);
        setContextData(contextRes);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading event detail / context", err);
        setLoading(false);
      });
  }, [eventId, caseId, exhibitId]);

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(fieldName);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  const redactValue = (val: any): string => {
    if (val === undefined || val === null) return '';
    const str = String(val);
    if (/^[0-9a-fA-F]{64}$/.test(str)) {
      return '<REDACTED>';
    }
    return str;
  };

  // Compile context list chronologically: previous -> current -> next
  const contextEvents = [
    ...contextData.previous,
    ...(contextData.current ? [contextData.current] : (event ? [event] : [])),
    ...contextData.next
  ];

  if (!eventId) {
    return (
      <div className="w-full h-full bg-panel border border-border rounded-xl flex flex-col items-center justify-center p-6 text-center text-text-secondary select-none">
        <AlertTriangle className="w-8 h-8 text-text-secondary/40 mb-3" />
        <p className="text-sm font-semibold">No Event Selected</p>
        <p className="text-xs text-text-secondary/60 mt-1 max-w-[200px]">
          Select an event in the timeline to preview complete forensic detail analysis and nearby chronological context.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="w-full h-full bg-panel border border-border rounded-xl flex items-center justify-center p-6">
        <LoadingSpinner />
      </div>
    );
  }

  if (!event) {
    return (
      <div className="w-full h-full bg-panel border border-border rounded-xl flex items-center justify-center p-6 text-danger text-center">
        <p className="text-sm font-semibold">Failed to load event details.</p>
      </div>
    );
  }

  const { icon: Icon, color, bg, border } = getIconForSource(event.source_app, event.event_type);

  // Shorten hash for display
  const getDisplayHash = (hash: string | undefined) => {
    if (!hash) return 'None';
    const clean = hash.trim();
    if (clean.length > 12) {
      return `${clean.substring(0, 8)}...${clean.substring(clean.length - 6)}`;
    }
    return clean;
  };

  return (
    <div className="w-full h-full bg-panel border border-border rounded-xl flex flex-col overflow-hidden shadow-xl animate-in slide-in-from-right duration-250 select-none">
      
      {/* Event Details Panel Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-panel-alt">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${bg} border ${border}`}>
            <Icon className={`w-4.5 h-4.5 ${color}`} />
          </div>
          <div>
            <h2 className="text-xs font-black tracking-wider uppercase text-text-primary">Event Details</h2>
            <p className="text-[10px] text-text-secondary font-bold font-mono uppercase mt-0.5">{event.source_app || 'System'}</p>
          </div>
        </div>
        {onClose && (
          <button 
            onClick={onClose} 
            className="p-1 hover:bg-panel rounded text-text-secondary hover:text-text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Main Panel Content Scroller */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        
        {/* Title and summary header box */}
        <div className={`p-3 bg-panel-alt rounded-lg border flex flex-col gap-1.5 ${
          event.deleted ? 'border-red-500/30' : 'border-border'
        }`}>
          <span className={`text-[11px] font-extrabold ${event.deleted ? 'text-red-500' : 'text-accent'}`}>
            {event.title}
          </span>
          <p className="text-xs text-text-primary leading-relaxed whitespace-pre-wrap break-words font-medium">
            {redactValue(event.summary)}
          </p>
        </div>

        {/* Dense field mapping list */}
        <div className="space-y-1.5 text-[11px] font-mono">
          
          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Event ID:</span>
            <span className="text-text-primary font-bold text-right break-all max-w-[200px] select-all">{event.id || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Event Type:</span>
            <span className="text-text-primary font-bold text-right">{event.event_type || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Timestamp:</span>
            <span className="text-text-primary font-bold text-right">{formatTimestamp(event.timestamp) || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Source App:</span>
            <span className="text-text-primary font-bold text-right">{event.source_app || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Source Type:</span>
            <span className="text-text-primary font-bold text-right">{event.source_type || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Category:</span>
            <span className="text-text-primary font-bold text-right">{event.category || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Direction:</span>
            <span className="text-text-primary font-bold capitalize text-right">{event.direction || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">From:</span>
            <span className="text-text-primary font-bold text-right truncate max-w-[180px]" title={event.sender || ''}>{redactValue(event.sender) || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">To:</span>
            <span className="text-text-primary font-bold text-right truncate max-w-[180px]" title={event.receiver || ''}>{redactValue(event.receiver) || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Phone Number:</span>
            <span className="text-text-primary font-bold text-right truncate max-w-[180px]">{event.phone_number || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Email:</span>
            <span className="text-text-primary font-bold text-right truncate max-w-[180px]">{event.email || 'Not available'}</span>
          </div>

          <div className="flex flex-col gap-0.5 border-b border-border/40 py-1">
            <span className="text-text-secondary">Message/Summary:</span>
            <span className="text-text-primary font-bold break-words leading-tight text-left mt-0.5">{redactValue(event.summary) || 'Not available'}</span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Deleted Status:</span>
            <span className={`px-1.5 py-0.5 rounded font-extrabold uppercase text-[9px] ${
              event.deleted 
                ? 'bg-red-500/15 text-red-500 border border-red-500/25' 
                : 'text-text-secondary/70'
            }`}>
              {event.deleted_status || 'Not available'}
            </span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Recovered Status:</span>
            <span className={`px-1.5 py-0.5 rounded font-extrabold uppercase text-[9px] ${
              event.recovered 
                ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/25 animate-pulse' 
                : 'text-text-secondary/70'
            }`}>
              {event.recovered_status || 'Not available'}
            </span>
          </div>

          <div className="flex justify-between items-baseline border-b border-border/40 py-1">
            <span className="text-text-secondary">Parser:</span>
            <span className="text-text-primary font-bold text-right">{event.parser || 'Not available'}</span>
          </div>

          <div className="flex flex-col gap-0.5 border-b border-border/40 py-1">
            <span className="text-text-secondary">Source File:</span>
            <span className="text-text-primary font-bold break-all leading-tight text-right select-all">{event.source_file || 'Not available'}</span>
          </div>

          <div className="flex flex-col gap-0.5 border-b border-border/40 py-1">
            <span className="text-text-secondary">Hash:</span>
            <div className="flex gap-2 items-center justify-between mt-0.5">
              <span className="text-text-primary font-bold break-all select-all flex-1 text-left">{event.source_hash ? getDisplayHash(event.source_hash) : 'Not available'}</span>
              {event.source_hash && (
                <button 
                  onClick={() => copyToClipboard(event.source_hash || '', 'hash')} 
                  className="p-1 bg-panel-alt border border-border rounded hover:bg-border text-text-secondary hover:text-text-primary"
                  title="Copy full hash"
                >
                  {copiedField === 'hash' ? <Check className="w-3 h-3 text-success" /> : <Copy className="w-3 h-3" />}
                </button>
              )}
            </div>
          </div>

          <div className="flex justify-between items-center border-b border-border/40 py-1">
            <span className="text-text-secondary">Confidence:</span>
            <span className={`px-1.5 py-0.5 rounded border text-[9px] font-extrabold uppercase ${
              event.confidence && event.confidence.toLowerCase() === 'high' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
              event.confidence && event.confidence.toLowerCase() === 'medium' ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' :
              event.confidence && event.confidence.toLowerCase() === 'low' ? 'bg-red-500/10 border-red-500/30 text-red-400' :
              'bg-slate-500/10 border-slate-500/30 text-slate-400'
            }`}>
              {event.confidence || 'Not available'}
            </span>
          </div>
        </div>

        {/* TIMELINE CONTEXT Section */}
        {contextEvents.length > 0 && (
          <div className="pt-3 border-t border-border/60 space-y-2">
            <h3 className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Timeline Context</h3>
            
            <div className="space-y-1.5">
              {contextEvents.map(evt => {
                const isCurrent = evt.id === event.id;
                const isEvtDeleted = !!evt.deleted;
                const timeStr = formatEventTime(evt.timestamp, evt.timestamp_sort);
                
                // Color dots for tiny timeline
                const dotColorClass = isEvtDeleted 
                  ? 'bg-red-500' 
                  : evt.source_app.toLowerCase().includes('whatsapp') ? 'bg-emerald-500' :
                    evt.source_app.toLowerCase().includes('telegram') ? 'bg-cyan-500' :
                    evt.source_app.toLowerCase().includes('signal') ? 'bg-indigo-500' :
                    evt.source_app.toLowerCase().includes('sms') ? 'bg-violet-500' :
                    evt.source_app.toLowerCase().includes('phone') ? 'bg-blue-500' :
                    evt.source_app.toLowerCase().includes('chrome') ? 'bg-cyan-400' :
                    'bg-slate-500';

                return (
                  <div
                    key={evt.id}
                    onClick={() => onSelectEvent?.(evt)}
                    className={`flex items-center gap-2.5 p-2 rounded cursor-pointer transition-all ${
                      isCurrent 
                        ? isEvtDeleted 
                          ? 'bg-red-500/10 border border-red-500/40' 
                          : 'bg-accent/10 border border-accent/40'
                        : 'bg-panel-alt hover:bg-panel-alt/60 border border-transparent'
                    }`}
                  >
                    {/* Timestamp */}
                    <span className="text-[9.5px] text-text-secondary font-mono flex-shrink-0">{timeStr}</span>
                    
                    {/* Tiny connector dot */}
                    <span className={`w-2 h-2 rounded-full ${dotColorClass}`} />
                    
                    {/* Event short text */}
                    <div className="min-w-0 flex-1">
                      <p className={`text-[10.5px] font-bold truncate ${
                        isCurrent 
                          ? isEvtDeleted ? 'text-red-400' : 'text-accent'
                          : 'text-text-primary'
                      }`}>
                        {evt.title}
                      </p>
                      {isCurrent && (
                        <p className="text-[9.5px] text-text-secondary truncate mt-0.5 leading-tight">{evt.summary}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
