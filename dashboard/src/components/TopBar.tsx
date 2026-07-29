import type {  CaseSummary  } from '../types/evidence';
import { Download, ShieldCheck } from 'lucide-react';
import { exportReport, verifyHashes } from '../services/api';

interface TopBarProps {
  summary: CaseSummary | null;
}

export default function TopBar({ summary }: TopBarProps) {
  const handleExport = async () => {
    try {
      await exportReport();
      alert('Report exported successfully.');
    } catch (err) {
      alert('Export failed.');
    }
  };

  const handleVerify = async () => {
    try {
      await verifyHashes();
      alert('Hashes verified.');
    } catch (err) {
      alert('Verification failed.');
    }
  };

  return (
    <div className="flex items-center justify-between px-6 py-4 bg-panel border-b border-border text-sm">
      <div className="flex flex-col">
        <h1 className="text-xl font-bold tracking-wider text-accent">E-RAKSHAK</h1>
        <span className="text-text-secondary text-xs">Rapid Evidence Triage</span>
      </div>
      
      {summary && (
        <div className="flex items-center gap-4 text-text-secondary">
          <div className="px-3 py-1 bg-panel-alt rounded-md border border-border">
            Case: <span className="text-text-primary font-mono">{summary.case_id}</span>
          </div>
          <div className="px-3 py-1 bg-panel-alt rounded-md border border-border">
            Exhibit: <span className="text-text-primary font-mono">{summary.exhibit_id}</span>
          </div>
          <div className="hidden md:flex gap-3 px-3 py-1 bg-panel-alt rounded-md border border-border">
            <span>{summary.device_info.manufacturer} {summary.device_info.model}</span>
            <span className="text-border">|</span>
            <span>Android {summary.device_info.android_version}</span>
            <span className="text-border">|</span>
            <span>Patch {summary.device_info.security_patch}</span>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        {summary && (
          <div className={`px-3 py-1 rounded-md text-xs font-semibold ${
            summary.acquisition_status === 'Complete' ? 'bg-success/20 text-success' :
            summary.acquisition_status === 'Partial' ? 'bg-warning/20 text-warning' :
            'bg-danger/20 text-danger'
          }`}>
            {summary.acquisition_status}
          </div>
        )}
        <button onClick={handleVerify} className="p-2 bg-panel-alt hover:bg-border rounded-md text-text-secondary transition-colors" title="Verify Hashes">
          <ShieldCheck className="w-5 h-5" />
        </button>
        <button onClick={handleExport} className="flex items-center gap-2 px-3 py-2 bg-accent hover:bg-accent-hover text-white rounded-md transition-colors shadow-lg">
          <Download className="w-4 h-4" />
          <span>Export Report</span>
        </button>
      </div>
    </div>
  );
}
