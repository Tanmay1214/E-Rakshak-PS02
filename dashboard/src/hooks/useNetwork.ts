import { useState, useEffect } from 'react';
import type { NetworkEvent } from '../types/evidence';
import { fetchNetwork } from '../services/api';

export function useNetwork() {
  const [events, setEvents] = useState<NetworkEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchNetwork({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setEvents((res as any).network_events || []);
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
