import { useState, useEffect } from 'react';
import type {  CaseSummary  } from '../types/evidence';
import { fetchCaseSummary } from '../services/api';

export function useCaseSummary() {
  const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = async () => {
    setLoading(true);
    try {
      const data = await fetchCaseSummary();
      setSummary(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch case summary');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refetch();
  }, []);

  return { summary, loading, error, refetch };
}
