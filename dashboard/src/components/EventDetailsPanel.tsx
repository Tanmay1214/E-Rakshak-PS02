import { useEffect, useState } from 'react';
import type {  TimelineEvent  } from '../types/evidence';
import { X, AlertTriangle } from 'lucide-react';
import { getIconForSource } from '../utils/icons';
import { formatTimestamp, timeAgo } from '../utils/formatters';
import { fetchTimelineEvent } from '../services/api';
import LoadingSpinner from './LoadingSpinner';

interface EventDetailsPanelProps {
  eventId: string;
  onClose: () => void;
}

export default function EventDetailsPanel({ eventId, onClose }: EventDetailsPanelProps) {
  const [event, setEvent] = useState<TimelineEvent | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchTimelineEvent(eventId)
      .then(res => {
        setEvent(res);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [eventId]);

  if (loading) {
    return (
      <div className="w-96 bg-panel border-l border-border h-full flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!event) return null;

  const { icon: Icon, color } = getIconForSource(event.source_app, event.event_type);

  return (
    <div className="w-96 bg-panel border-l border-border h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
      <div className="flex items-center justify-between p-4 border-b border-border bg-panel-alt">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-panel shadow-sm ${color}`}>
            <Icon className="w-5 h-5" />
          </div>
          <h2 className="font-semibold text-text-primary capitalize">{event.event_type} Details</h2>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-panel rounded-md text-text-secondary transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Source</h3>
          <div className="p-3 bg-panel-alt rounded border border-border flex items-center justify-between">
            <span className={`font-medium ${color}`}>{event.source_app || 'System'}</span>
            <span className="text-xs text-text-secondary">Parser: {event.source_app.toLowerCase()}</span>
          </div>
        </section>

        <section>
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Timing</h3>
          <div className="p-3 bg-panel-alt rounded border border-border text-sm">
            <div className="text-text-primary font-mono">{formatTimestamp(event.timestamp)}</div>
            <div className="text-xs text-text-secondary mt-1">{timeAgo(event.timestamp)}</div>
          </div>
        </section>

        <section>
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Content</h3>
          <div className="p-4 bg-panel-alt rounded border border-border text-sm text-text-primary whitespace-pre-wrap">
            {event.summary}
          </div>
        </section>

        <section>
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Status</h3>
          <div className="flex flex-wrap gap-2">
            {event.deleted && <span className="px-2 py-1 bg-danger/20 text-danger rounded text-xs font-bold">DELETED</span>}
            {event.recovered && <span className="px-2 py-1 bg-success/20 text-success rounded text-xs font-bold">RECOVERED</span>}
            <span className="px-2 py-1 bg-panel-alt border border-border rounded text-xs text-text-secondary">
              Confidence: <span className="text-text-primary capitalize">{event.confidence}</span>
            </span>
          </div>
        </section>
        
        <section>
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Forensic Metadata</h3>
          <div className="space-y-2 text-xs font-mono text-text-secondary bg-bg p-3 rounded border border-border">
            <div className="break-all"><span className="text-text-primary">Event ID:</span> {event.id}</div>
          </div>
        </section>
      </div>

      <div className="p-3 bg-warning/10 border-t border-warning/20 flex items-center gap-2 text-warning text-xs font-semibold">
        <AlertTriangle className="w-4 h-4" />
        <span>Forensic Preview Only — Not a Full Examination</span>
      </div>
    </div>
  );
}
