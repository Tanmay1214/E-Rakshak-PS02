import { Search, Clock, ListFilter } from 'lucide-react';

interface FiltersBarProps {
  activeFilter: string;
  onFilterChange: (filter: string) => void;
  searchTerm: string;
  onSearchChange: (search: string) => void;
  bucketMode: '15m' | '1h' | 'exact';
  onBucketModeChange: (mode: '15m' | '1h' | 'exact') => void;
}

export default function FiltersBar({
  activeFilter,
  onFilterChange,
  searchTerm,
  onSearchChange,
  bucketMode,
  onBucketModeChange,
}: FiltersBarProps) {
  
  const chips = [
    { id: 'all', label: 'All' },
    { id: 'messages', label: 'SMS' },
    { id: 'calls', label: 'Calls' },
    { id: 'whatsapp', label: 'WhatsApp' },
    { id: 'telegram', label: 'Telegram' },
    { id: 'signal', label: 'Signal' },
    { id: 'location', label: 'Location' },
    { id: 'media', label: 'Media' },
    { id: 'browser', label: 'Browser' },
    { id: 'apps', label: 'Apps' },
    { id: 'network', label: 'Network' },
    { id: 'system', label: 'System' },
  ];

  return (
    <div className="space-y-3.5 w-full select-none">
      
      {/* Category Chips row */}
      <div className="flex flex-wrap gap-1.5 items-center">
        {chips.map(chip => {
          const isActive = activeFilter === chip.id;
          return (
            <button
              key={chip.id}
              onClick={() => onFilterChange(chip.id)}
              className={`px-3.5 py-1 rounded text-xs font-semibold border transition-all duration-150 ${
                isActive
                  ? 'bg-accent border-transparent text-white shadow-sm'
                  : 'bg-panel border-border text-text-secondary hover:border-text-secondary hover:text-text-primary'
              }`}
            >
              {chip.label}
            </button>
          );
        })}
      </div>

      {/* Bucket controls & search row */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-panel p-2 rounded-lg border border-border">
        
        <div className="flex items-center gap-2">
          {/* 15-minute buckets button */}
          <button
            onClick={() => onBucketModeChange('15m')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-[11px] font-bold border transition-all duration-150 ${
              bucketMode === '15m'
                ? 'bg-accent/15 border-accent text-accent'
                : 'bg-panel-alt border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>15-minute buckets</span>
          </button>

          {/* 1-hour buckets button */}
          <button
            onClick={() => onBucketModeChange('1h')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-[11px] font-bold border transition-all duration-150 ${
              bucketMode === '1h'
                ? 'bg-accent/15 border-accent text-accent'
                : 'bg-panel-alt border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>1-hour buckets</span>
          </button>

          {/* Events sorted by exact timestamp button */}
          <button
            onClick={() => onBucketModeChange('exact')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-[11px] font-bold border transition-all duration-150 ${
              bucketMode === 'exact'
                ? 'bg-accent/15 border-accent text-accent'
                : 'bg-panel-alt border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            <ListFilter className="w-3.5 h-3.5" />
            <span>Events sorted by exact timestamp</span>
          </button>
        </div>

        {/* Integrated search input */}
        <div className="flex items-center gap-2 bg-panel-alt border border-border rounded px-2.5 py-1 w-full sm:w-60">
          <Search className="w-3.5 h-3.5 text-text-secondary" />
          <input
            type="text"
            placeholder="Search sender, number, content..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="bg-transparent text-[11px] text-text-primary focus:outline-none w-full placeholder:text-text-secondary/50 font-medium"
          />
        </div>

      </div>

    </div>
  );
}
