import { useState, useEffect, useCallback } from 'react';
import type {  TimelineEvent, TimelineFilters  } from '../types/evidence';
import { fetchTimeline } from '../services/api';

export function useTimeline(filters: TimelineFilters) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchTimeline({ ...filters, page: 1 })
      .then(res => {
        if (mounted) {
          setEvents(res.events);
          setTotal(res.total);
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          console.error(err);
          setLoading(false);
        }
      });
      
    return () => { mounted = false; };
  }, [JSON.stringify(filters)]);

  const loadMore = useCallback(() => {
    const nextPage = Math.ceil(events.length / (filters.limit || 50)) + 1;
    fetchTimeline({ ...filters, page: nextPage }).then(res => {
      setEvents(prev => [...prev, ...res.events]);
      setTotal(res.total);
    });
  }, [events.length, filters]);

  return { events, total, loading, loadMore };
}
