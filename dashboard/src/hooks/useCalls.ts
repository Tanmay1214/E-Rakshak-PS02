import { useState, useEffect } from 'react';
import type { Call } from '../types/evidence';
import { fetchCalls } from '../services/api';

export function useCalls() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchCalls({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setCalls((res as any).calls || []);
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

  return { calls, total, loading };
}
