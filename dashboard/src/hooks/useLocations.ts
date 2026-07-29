import { useState, useEffect } from 'react';
import type { Location } from '../types/evidence';
import { fetchLocations } from '../services/api';

export function useLocations() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchLocations({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setLocations((res as any).locations || []);
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

  return { locations, total, loading };
}
