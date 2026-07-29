import { useState, useEffect } from 'react';
import type { BrowserHistoryRecord, BrowserSearchRecord, BrowserDownloadRecord } from '../types/evidence';
import { fetchBrowserHistory, fetchBrowserSearches, fetchBrowserDownloads } from '../services/api';

export function useBrowserHistory() {
  const [history, setHistory] = useState<BrowserHistoryRecord[]>([]);
  const [searches, setSearches] = useState<BrowserSearchRecord[]>([]);
  const [downloads, setDownloads] = useState<BrowserDownloadRecord[]>([]);
  const [totalHistory, setTotalHistory] = useState(0);
  const [totalSearches, setTotalSearches] = useState(0);
  const [totalDownloads, setTotalDownloads] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    
    Promise.all([
      fetchBrowserHistory({ limit: 1000 }),
      fetchBrowserSearches({ limit: 1000 }),
      fetchBrowserDownloads({ limit: 1000 }),
    ])
      .then(([histRes, searchRes, dlRes]) => {
        if (mounted) {
          setHistory((histRes as any).history || []);
          setTotalHistory(histRes.total || 0);
          setSearches((searchRes as any).searches || []);
          setTotalSearches(searchRes.total || 0);
          setDownloads((dlRes as any).downloads || []);
          setTotalDownloads(dlRes.total || 0);
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

  return { history, searches, downloads, totalHistory, totalSearches, totalDownloads, loading };
}
