import { useState, useEffect } from 'react';
import type { App } from '../types/evidence';
import { fetchApps } from '../services/api';

export function useApps() {
  const [apps, setApps] = useState<App[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchApps({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setApps((res as any).apps || []);
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

  return { apps, total, loading };
}
