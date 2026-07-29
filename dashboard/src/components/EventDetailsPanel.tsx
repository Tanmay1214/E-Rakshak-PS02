import { useEffect, useState } from 'react';
import type { TimelineEvent } from '../types/evidence';
import { X, AlertTriangle, Copy, Check, MapPin, ImageIcon, FileText } from 'lucide-react';
import { getIconForSource } from '../utils/icons';
import { formatTimestamp } from '../utils/formatters';
import { fetchTimelineEvent } from '../services/api';
import LoadingSpinner from './LoadingSpinner';

interface EventDetailsPanelProps {
  eventId?: string;
  onClose?: () => void;
}

export default function EventDetailsPanel({ eventId, onClose }: EventDetailsPanelProps) {
  const [event, setEvent] = useState<TimelineEvent | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) {
      setEvent(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchTimelineEvent(eventId)
      .then(res => {
        setEvent(res);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [eventId]);

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

  if (!eventId) {
    return (
      <div className="w-full md:w-96 bg-panel border border-border rounded-xl h-full flex flex-col items-center justify-center p-6 text-center text-text-secondary select-none">
        <AlertTriangle className="w-8 h-8 text-text-secondary/40 mb-3" />
        <p className="text-sm font-medium">No Event Selected</p>
        <p className="text-xs text-text-secondary/60 mt-1 max-w-[200px]">
          Select a timeline event to view detailed forensic metadata and parameters.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="w-full md:w-96 bg-panel border border-border rounded-xl h-full flex items-center justify-center p-6">
        <LoadingSpinner />
      </div>
    );
  }

  if (!event) {
    return (
      <div className="w-full md:w-96 bg-panel border border-border rounded-xl h-full flex items-center justify-center p-6 text-danger text-center">
        <p className="text-sm font-semibold">Failed to load event details.</p>
      </div>
    );
  }

  const { icon: Icon, color, bg, border } = getIconForSource(event.source_app, event.event_type);

  return (
    <div className="w-full md:w-96 bg-panel border border-border rounded-xl h-full flex flex-col overflow-hidden shadow-xl animate-in slide-in-from-right duration-200">
      {/* Panel Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-panel-alt">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`p-2 rounded-lg flex-shrink-0 ${bg} border ${border}`}>
            <Icon className={`w-5 h-5 ${color}`} />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-text-primary truncate">Event Details</h2>
            <p className="text-[10px] text-text-secondary uppercase tracking-wider font-semibold font-mono">{event.event_type}</p>
          </div>
        </div>
        {onClose && (
          <button 
            onClick={onClose} 
            className="p-1 hover:bg-panel-alt rounded-md text-text-secondary hover:text-text-primary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Content Scroller */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Core Description Box */}
        <section>
          <div className="p-4 bg-panel-alt rounded-xl border border-border text-sm text-text-primary leading-relaxed whitespace-pre-wrap break-words max-h-48 overflow-y-auto font-sans shadow-inner">
            {redactValue(event.summary)}
          </div>
        </section>

        {/* Date & Time parameters */}
        <section className="grid grid-cols-2 gap-3 text-xs">
          <div className="p-3 bg-panel-alt rounded-lg border border-border">
            <p className="text-[10px] font-bold text-text-secondary uppercase mb-1">Date</p>
            <p className="font-semibold text-text-primary">{formatTimestamp(event.timestamp).split(' ')[0]}</p>
          </div>
          <div className="p-3 bg-panel-alt rounded-lg border border-border">
            <p className="text-[10px] font-bold text-text-secondary uppercase mb-1">Time</p>
            <p className="font-semibold text-text-primary font-mono">{formatTimestamp(event.timestamp).split(' ').slice(1).join(' ')}</p>
          </div>
        </section>

        {/* Identity & Actors */}
        {(event.sender || event.receiver || event.phone_number || event.email) && (
          <section className="space-y-2.5">
            <h3 className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Communication Participants</h3>
            <div className="bg-panel-alt rounded-xl border border-border p-3 space-y-2 text-xs">
              {event.sender && (
                <div className="flex justify-between py-1 border-b border-border/40 last:border-0">
                  <span className="text-text-secondary">Sender:</span>
                  <span className="text-text-primary font-semibold truncate max-w-[180px]" title={event.sender}>{redactValue(event.sender)}</span>
                </div>
              )}
              {event.receiver && (
                <div className="flex justify-between py-1 border-b border-border/40 last:border-0">
                  <span className="text-text-secondary">Receiver:</span>
                  <span className="text-text-primary font-semibold truncate max-w-[180px]" title={event.receiver}>{redactValue(event.receiver)}</span>
                </div>
              )}
              {event.phone_number && (
                <div className="flex justify-between py-1 border-b border-border/40 last:border-0">
                  <span className="text-text-secondary">Phone:</span>
                  <span className="text-text-primary font-mono font-semibold truncate max-w-[180px]" title={event.phone_number}>{event.phone_number}</span>
                </div>
              )}
              {event.email && (
                <div className="flex justify-between py-1 border-b border-border/40 last:border-0">
                  <span className="text-text-secondary">Email:</span>
                  <span className="text-text-primary font-mono font-semibold truncate max-w-[180px]" title={event.email}>{event.email}</span>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Location Mini Card */}
        {(event.location_lat || event.location_lon) && (
          <section className="space-y-2">
            <h3 className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Geographic Location</h3>
            <div className="bg-panel-alt rounded-xl border border-border p-3 text-xs flex items-start gap-3">
              <MapPin className="w-5 h-5 text-amber-400 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-text-primary">Latitude: {event.location_lat}</p>
                <p className="font-semibold text-text-primary">Longitude: {event.location_lon}</p>
                {event.location_accuracy !== undefined && (
                  <p className="text-xs text-text-secondary mt-1">Accuracy: {event.location_accuracy}m</p>
                )}
                {event.source_type && (
                  <p className="text-[10px] text-text-secondary font-mono mt-1 uppercase">Source: {event.source_type}</p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* File and Media paths */}
        {(event.media_path || event.file_path) && (
          <section className="space-y-2">
            <h3 className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">File System Assets</h3>
            <div className="bg-panel-alt rounded-xl border border-border p-3 space-y-2.5 text-xs">
              {event.media_path && (
                <div className="flex flex-col gap-1">
                  <span className="text-text-secondary flex items-center gap-1"><ImageIcon className="w-3.5 h-3.5" /> Media Path:</span>
                  <div className="flex gap-2 items-center">
                    <span className="text-text-primary font-mono bg-bg px-2 py-1 rounded border border-border flex-1 truncate select-all">{event.media_path}</span>
                    <button 
                      onClick={() => copyToClipboard(event.media_path || '', 'media')} 
                      className="p-1.5 bg-bg border border-border rounded-md hover:bg-border text-text-secondary hover:text-text-primary"
                    >
                      {copiedField === 'media' ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              )}
              {event.file_path && (
                <div className="flex flex-col gap-1">
                  <span className="text-text-secondary flex items-center gap-1"><FileText className="w-3.5 h-3.5" /> File Path:</span>
                  <div className="flex gap-2 items-center">
                    <span className="text-text-primary font-mono bg-bg px-2 py-1 rounded border border-border flex-1 truncate select-all">{event.file_path}</span>
                    <button 
                      onClick={() => copyToClipboard(event.file_path || '', 'file')} 
                      className="p-1.5 bg-bg border border-border rounded-md hover:bg-border text-text-secondary hover:text-text-primary"
                    >
                      {copiedField === 'file' ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Forensic Metadata parameters */}
        <section className="space-y-2">
          <h3 className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Forensic Metadata</h3>
          <div className="bg-panel-alt rounded-xl border border-border p-3 space-y-2.5 text-xs font-mono">
            <div>
              <span className="text-text-secondary block mb-0.5">Event ID:</span>
              <span className="text-text-primary break-all">{event.id}</span>
            </div>
            {event.parser && (
              <div className="flex justify-between border-t border-border/40 pt-2">
                <span className="text-text-secondary">Parser:</span>
                <span className="text-text-primary font-semibold">{event.parser}</span>
              </div>
            )}
            {event.source_file && (
              <div className="border-t border-border/40 pt-2">
                <span className="text-text-secondary block mb-0.5">Source DB File:</span>
                <span className="text-text-primary break-all select-all">{event.source_file}</span>
              </div>
            )}
            {event.source_hash && (
              <div className="border-t border-border/40 pt-2">
                <span className="text-text-secondary block mb-0.5">Source Hash:</span>
                <div className="flex gap-2 items-center mt-1">
                  <span className="text-text-primary break-all select-all flex-1">{event.source_hash}</span>
                  <button 
                    onClick={() => copyToClipboard(event.source_hash || '', 'hash')} 
                    className="p-1 bg-bg border border-border rounded hover:bg-border text-text-secondary hover:text-text-primary"
                  >
                    {copiedField === 'hash' ? <Check className="w-3 h-3 text-success" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Forensic Warnings Footer */}
      <div className="p-3 bg-warning/10 border-t border-border flex items-center justify-center gap-2 text-warning text-[10px] font-bold tracking-wider uppercase">
        <AlertTriangle className="w-4 h-4 text-warning" />
        <span>Forensic Preview Only — Not a Full Examination</span>
      </div>
    </div>
  );
}
