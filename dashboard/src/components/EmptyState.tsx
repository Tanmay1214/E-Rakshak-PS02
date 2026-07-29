import type { ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';

interface EmptyStateProps {
  message?: string;
  icon?: ReactNode;
}

export default function EmptyState({ message = 'No data available', icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-text-secondary">
      {icon || <AlertCircle className="w-12 h-12 mb-4 opacity-50" />}
      <p className="text-lg font-medium">{message}</p>
    </div>
  );
}
