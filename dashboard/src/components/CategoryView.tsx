import type { ReactNode } from 'react';
import LoadingSpinner from './LoadingSpinner';
import EmptyState from './EmptyState';

interface Column {
  key: string;
  label: string;
  render?: (val: any, row: any) => ReactNode;
}

interface CategoryViewProps {
  title: string;
  columns: Column[];
  data: any[];
  loading: boolean;
  total: number;
  onLoadMore?: () => void;
  onRowClick?: (row: any) => void;
}

export default function CategoryView({ title, columns, data, loading, total, onLoadMore, onRowClick }: CategoryViewProps) {
  return (
    <div className="bg-panel rounded-lg border border-border shadow-sm flex flex-col h-full overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex justify-between items-center bg-panel-alt">
        <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
        <span className="text-sm text-text-secondary">Showing {data.length} of {total}</span>
      </div>

      <div className="flex-1 overflow-auto">
        {data.length === 0 && !loading ? (
          <EmptyState message={`No ${title.toLowerCase()} found`} />
        ) : (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-panel border-b border-border shadow-sm z-10">
              <tr>
                {columns.map(col => (
                  <th key={col.key} className="px-6 py-3 text-xs font-medium text-text-secondary uppercase tracking-wider whitespace-nowrap">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((row, idx) => (
                <tr 
                  key={row.id || idx} 
                  onClick={() => onRowClick?.(row)}
                  className={`hover:bg-panel-alt transition-colors ${onRowClick ? 'cursor-pointer' : ''}`}
                >
                  {columns.map(col => (
                    <td key={col.key} className="px-6 py-4 text-sm text-text-primary whitespace-nowrap">
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {loading && <LoadingSpinner />}
        
        {data.length > 0 && data.length < total && !loading && onLoadMore && (
          <div className="p-4 border-t border-border flex justify-center bg-panel-alt">
            <button 
              onClick={onLoadMore}
              className="px-4 py-2 bg-panel hover:bg-border border border-border rounded-md text-sm text-text-secondary transition-colors"
            >
              Load More
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
