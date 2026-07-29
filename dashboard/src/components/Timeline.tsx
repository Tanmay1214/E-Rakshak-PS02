import type { TimelineEvent } from '../types/evidence';
import EventCard from './EventCard';
import LoadingSpinner from './LoadingSpinner';
import EmptyState from './EmptyState';
import { formatEventDate } from '../utils/formatters';

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

  const renderedElements: React.ReactNode[] = [];
  let lastDateStr = '';

  events.forEach((evt, idx) => {
    const currentDateStr = formatEventDate(evt.timestamp, evt.timestamp_sort);
    
    if (currentDateStr !== lastDateStr) {
      lastDateStr = currentDateStr;
      renderedElements.push(
        <div 
          key={`date-header-${currentDateStr}-${idx}`} 
          className="relative pl-10 my-6 first:mt-2 flex items-center gap-3"
        >
          <div className="absolute left-[12px] w-2 h-2 rounded-full bg-accent ring-4 ring-accent/20 z-10" />
          <span className="text-[11px] font-bold text-accent bg-accent/10 border border-accent/20 px-3 py-1 rounded-full font-mono uppercase tracking-wider">
            {currentDateStr}
          </span>
          <div className="flex-1 h-px bg-border/60" />
        </div>
      );
    }

    renderedElements.push(
      <EventCard 
        key={`${evt.id}-${idx}`} 
        event={evt} 
        onSelect={onSelectEvent} 
        isSelected={selectedEventId === evt.id} 
      />
    );
  });

  return (
    <div className="py-2">
      <div className="space-y-0">
        {renderedElements}
      </div>
      
      {loading && <LoadingSpinner />}
      
      {hasMore && !loading && events.length > 0 && (
        <button 
          onClick={onLoadMore}
          className="mt-6 w-full py-2.5 bg-panel hover:bg-border border border-border rounded-lg text-xs font-semibold text-text-secondary hover:text-text-primary transition-all duration-200"
        >
          Load More
        </button>
      )}
    </div>
  );
}
