import { useState, useEffect } from 'react';
import type { Account } from '../types/evidence';
import { fetchAccounts } from '../services/api';

export function useAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    fetchAccounts({ limit: 1000 })
      .then(res => {
        if (mounted) {
          setAccounts((res as any).accounts || []);
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

  return { accounts, total, loading };
}
