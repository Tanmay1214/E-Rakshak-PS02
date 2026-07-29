import type {  TimelineEvent  } from '../types/evidence';
import EventCard from './EventCard';
import LoadingSpinner from './LoadingSpinner';
import EmptyState from './EmptyState';

interface TimelineProps {
  events: TimelineEvent[];
  loading: boolean;
  onSelectEvent: (e: TimelineEvent) => void;
  selectedEventId?: string;
  onLoadMore: () => void;
  hasMore?: boolean;
}

export default function Timeline({ events, loading, onSelectEvent, selectedEventId, onLoadMore, hasMore }: TimelineProps) {
  if (events.length === 0 && !loading) {
    return <EmptyState message="No timeline events found." />;
  }

  return (
    <div className="py-4">
      <div className="space-y-0">
        {events.map((evt, idx) => (
          <EventCard 
            key={`${evt.id}-${idx}`} 
            event={evt} 
            onSelect={onSelectEvent} 
            isSelected={selectedEventId === evt.id} 
          />
        ))}
      </div>
      
      {loading && <LoadingSpinner />}
      
      {hasMore && !loading && events.length > 0 && (
        <button 
          onClick={onLoadMore}
          className="mt-6 w-full py-2 bg-panel-alt hover:bg-border border border-border rounded-md text-sm text-text-secondary transition-colors"
        >
          Load More
        </button>
      )}
    </div>
  );
}
