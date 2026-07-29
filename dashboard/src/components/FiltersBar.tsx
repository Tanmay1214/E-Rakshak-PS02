import { Search, Calendar, RefreshCw } from 'lucide-react';

interface FiltersBarProps {
  activeFilter: string;
  onFilterChange: (filter: string) => void;
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
  customFromDate: string;
  onCustomFromDateChange: (val: string) => void;
  customToDate: string;
  onCustomToDateChange: (val: string) => void;
  searchTerm: string;
  onSearchChange: (search: string) => void;
  onClearFilters: () => void;
}

export default function FiltersBar({
  activeFilter,
  onFilterChange,
  timeRange,
  onTimeRangeChange,
  customFromDate,
  onCustomFromDateChange,
  customToDate,
  onCustomToDateChange,
  searchTerm,
  onSearchChange,
  onClearFilters
}: FiltersBarProps) {
  const filters = [
    { id: 'all', label: 'All', color: 'bg-accent' },
    { id: 'messages', label: 'Messages', color: 'bg-text-secondary' },
    { id: 'calls', label: 'Calls', color: 'bg-blue-500' },
    { id: 'whatsapp', label: 'WhatsApp', color: 'bg-whatsapp' },
    { id: 'telegram', label: 'Telegram', color: 'bg-telegram' },
    { id: 'signal', label: 'Signal', color: 'bg-signal' },
    { id: 'sms', label: 'SMS', color: 'bg-violet-500' },
    { id: 'location', label: 'Location', color: 'bg-amber-500' },
    { id: 'media', label: 'Media', color: 'bg-orange-500' },
    { id: 'browser', label: 'Browser', color: 'bg-yellow-500' },
    { id: 'apps', label: 'Apps', color: 'bg-emerald-500' },
    { id: 'network', label: 'Network', color: 'bg-sky-500' },
    { id: 'system', label: 'System', color: 'bg-slate-500' },
  ];

  return (
    <div className="bg-panel border border-border rounded-xl p-4 space-y-4 shadow-sm w-full">
      {/* Category Filter Chips */}
      <div className="flex flex-col gap-2">
        <span className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Evidence Sources</span>
        <div className="flex flex-wrap gap-1.5 animate-in fade-in duration-300">
          {filters.map(f => {
            const isActive = activeFilter === f.id;
            return (
              <button
                key={f.id}
                onClick={() => onFilterChange(f.id)}
                className={`whitespace-nowrap px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 border ${
                  isActive 
                    ? `${f.color || 'bg-accent'} text-white border-transparent shadow-md scale-105` 
                    : 'bg-panel-alt text-text-secondary border-border hover:border-text-secondary hover:text-text-primary'
                }`}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Inputs and Dropdowns row */}
      <div className="flex flex-col xl:flex-row items-center justify-between gap-3 pt-3 border-t border-border/50">
        <div className="flex flex-wrap items-center gap-3 w-full xl:w-auto">
          {/* Time range select */}
          <div className="flex items-center gap-2 bg-panel-alt border border-border rounded-lg px-3 py-2 w-full sm:w-48">
            <Calendar className="w-4 h-4 text-text-secondary" />
            <select
              value={timeRange}
              onChange={(e) => onTimeRangeChange(e.target.value)}
              className="bg-transparent text-xs text-text-primary focus:outline-none w-full cursor-pointer font-medium"
            >
              <option value="all" className="bg-panel">All Time</option>
              <option value="24h" className="bg-panel">Last 24 Hours</option>
              <option value="7d" className="bg-panel">Last 7 Days</option>
              <option value="custom" className="bg-panel">Custom Range</option>
            </select>
          </div>

          {/* Custom Date Pickers when active */}
          {timeRange === 'custom' && (
            <div className="flex items-center gap-2 w-full sm:w-auto animate-in slide-in-from-left duration-250">
              <input
                type="date"
                value={customFromDate}
                onChange={(e) => onCustomFromDateChange(e.target.value)}
                className="bg-panel-alt border border-border text-xs text-text-primary rounded-lg px-3 py-2 focus:outline-none"
                placeholder="From Date"
              />
              <span className="text-text-secondary text-xs">to</span>
              <input
                type="date"
                value={customToDate}
                onChange={(e) => onCustomToDateChange(e.target.value)}
                className="bg-panel-alt border border-border text-xs text-text-primary rounded-lg px-3 py-2 focus:outline-none"
                placeholder="To Date"
              />
            </div>
          )}

          {/* Search box input */}
          <div className="flex items-center gap-2 bg-panel-alt border border-border rounded-lg px-3 py-2 flex-1 sm:flex-initial sm:w-72">
            <Search className="w-4 h-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search sender, number, content..."
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
              className="bg-transparent text-xs text-text-primary focus:outline-none w-full placeholder:text-text-secondary/50 font-medium"
            />
          </div>
        </div>

        {/* Clear/Reset filters button */}
        <button
          onClick={onClearFilters}
          className="flex items-center gap-1.5 px-4 py-2 bg-panel-alt border border-border hover:border-text-secondary rounded-lg text-xs font-semibold text-text-secondary hover:text-text-primary transition-all duration-150 w-full xl:w-auto justify-center"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Reset Filters</span>
        </button>
      </div>
    </div>
  );
}
