import { useState, useEffect } from 'react';
import type {  SearchResult  } from '../types/evidence';
import { searchEvidence } from '../services/api';

export function useSearch(query: string, delay = 300) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }

    const timer = setTimeout(() => {
      setLoading(true);
      searchEvidence(query)
        .then(res => {
          setResults(res);
          setLoading(false);
        })
        .catch(() => {
          setResults([]);
          setLoading(false);
        });
    }, delay);

    return () => clearTimeout(timer);
  }, [query, delay]);

  return { results, loading };
}
