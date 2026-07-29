import { useState, useEffect } from 'react';
import type { Contact } from '../types/evidence';
import { fetchContacts } from '../services/api';

export function useContacts() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchContacts({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setContacts((res as any).contacts || []);
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

  return { contacts, total, loading };
}
