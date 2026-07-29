interface FiltersBarProps {
  activeFilter: string;
  onFilterChange: (filter: string) => void;
}

export default function FiltersBar({ activeFilter, onFilterChange }: FiltersBarProps) {
  const filters = [
    { id: 'all', label: 'All' },
    { id: 'messages', label: 'Messages', color: 'bg-text-secondary' },
    { id: 'calls', label: 'Calls', color: 'bg-accent' },
    { id: 'whatsapp', label: 'WhatsApp', color: 'bg-whatsapp' },
    { id: 'telegram', label: 'Telegram', color: 'bg-telegram' },
    { id: 'signal', label: 'Signal', color: 'bg-signal' },
    { id: 'location', label: 'Location', color: 'bg-danger' },
    { id: 'media', label: 'Media', color: 'bg-text-secondary' },
    { id: 'system', label: 'System', color: 'bg-text-primary' },
  ];

  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      {filters.map(f => {
        const isActive = activeFilter === f.id;
        return (
          <button
            key={f.id}
            onClick={() => onFilterChange(f.id)}
            className={`whitespace-nowrap px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
              isActive 
                ? `${f.color || 'bg-accent'} text-white shadow-lg` 
                : 'bg-panel-alt text-text-secondary border border-border hover:border-text-secondary'
            }`}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}
