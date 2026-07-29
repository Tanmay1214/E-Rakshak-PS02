import { useState, useEffect } from 'react';
import type { MediaItem } from '../types/evidence';
import { fetchMedia } from '../services/api';

export function useMedia() {
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchMedia({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setMedia((res as any).media || []);
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

  return { media, total, loading };
}
