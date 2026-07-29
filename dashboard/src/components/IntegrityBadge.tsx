import { ShieldCheck, ShieldAlert, Shield } from 'lucide-react';

interface IntegrityBadgeProps {
  status: 'Verified' | 'Partial' | 'Mismatch' | 'Unknown';
}

export default function IntegrityBadge({ status }: IntegrityBadgeProps) {
  if (status === 'Verified') {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-success/20 text-success text-xs font-semibold">
        <ShieldCheck className="w-3.5 h-3.5" />
        <span>Verified</span>
      </div>
    );
  }
  if (status === 'Partial') {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-warning/20 text-warning text-xs font-semibold">
        <ShieldAlert className="w-3.5 h-3.5" />
        <span>Partial</span>
      </div>
    );
  }
  if (status === 'Mismatch') {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-danger/20 text-danger text-xs font-semibold">
        <ShieldAlert className="w-3.5 h-3.5" />
        <span>Mismatch</span>
      </div>
    );
  }
  
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-panel-alt text-text-secondary border border-border text-xs font-semibold">
      <Shield className="w-3.5 h-3.5" />
      <span>Unknown</span>
    </div>
  );
}
