import { useState, useEffect } from 'react';
import type { Message } from '../types/evidence';
import { fetchMessages } from '../services/api';

export function useMessages() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchMessages({ limit: 1000 })
      .then(res => {
        if (mounted) {
          // the api returns {"messages": [...], "total": ...}
          setMessages((res as any).messages || []);
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

  return { messages, total, loading };
}
