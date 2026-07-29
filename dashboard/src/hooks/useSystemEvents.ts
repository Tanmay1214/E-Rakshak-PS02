import { useState, useEffect } from 'react';
import type { SystemEvent } from '../types/evidence';
import { fetchSystem } from '../services/api';

export function useSystemEvents() {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchSystem({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setEvents((res as any).system_events || []);
          setTotal(res.total || 0);
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
  }, []);

  return { events, total, loading };
}
