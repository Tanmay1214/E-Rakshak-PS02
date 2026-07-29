import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';

interface KeywordSearchProps {
  onSearch: (query: string) => void;
}

export default function KeywordSearch({ onSearch }: KeywordSearchProps) {
  const [val, setVal] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(val);
    }, 300);
    return () => clearTimeout(timer);
  }, [val, onSearch]);

  return (
    <div className="relative w-full max-w-md">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Search className="h-4 w-4 text-text-secondary" />
      </div>
      <input
        type="text"
        className="block w-full pl-10 pr-3 py-2 border border-border rounded-md bg-panel-alt/50 backdrop-blur text-sm text-text-primary placeholder-text-secondary focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-all"
        placeholder="Keyword search..."
        value={val}
        onChange={e => setVal(e.target.value)}
      />
    </div>
  );
}
