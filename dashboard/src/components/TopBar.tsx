import type { CaseSummary } from '../types/evidence';
import { Download, ShieldCheck, AlertTriangle } from 'lucide-react';
import { exportReport, verifyHashes } from '../services/api';

interface TopBarProps {
  summary: CaseSummary | null;
  timeRange: string;
  warningsCount?: number;
  onShowWarnings?: () => void;
}

export default function TopBar({ summary, timeRange, warningsCount = 0, onShowWarnings }: TopBarProps) {
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
      alert('Hashes verified successfully.');
    } catch (err) {
      alert('Verification failed.');
    }
  };

  const getTimeRangeLabel = (range: string) => {
    switch (range) {
      case '24h': return 'Last 24 Hours';
      case '7d': return 'Last 7 Days';
      case 'custom': return 'Custom Range';
      default: return 'All Time';
    }
  };

  // Determine forensic status badge styling
  const getForensicStatus = () => {
    if (!summary) return { label: 'Unknown', style: 'bg-slate-500/10 text-slate-400 border border-slate-500/30' };
    
    const status = summary.acquisition_status;
    if (status === 'Complete' && warningsCount === 0) {
      return { 
        label: 'Verified & Built', 
        style: 'bg-success/20 text-success border border-success/35' 
      };
    }
    if (status === 'Partial' || warningsCount > 0) {
      return { 
        label: 'Partial (Warnings)', 
        style: 'bg-warning/20 text-warning border border-warning/35' 
      };
    }
    return { 
      label: 'Acquisition Failed', 
      style: 'bg-danger/20 text-danger border border-danger/35' 
    };
  };

  const forensicStatus = getForensicStatus();

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between px-6 py-3.5 bg-panel border-b border-border text-xs gap-3">
      {/* Tool Branding */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <h1 className="text-base font-black tracking-wider text-accent leading-none">E-RAKSHAK</h1>
          <span className="text-text-secondary text-[9px] font-bold uppercase tracking-wider mt-0.5">Forensic Triage Suite</span>
        </div>
        <div className={`px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${forensicStatus.style}`}>
          {forensicStatus.label}
        </div>
      </div>
      
      {/* Case Identity Metadata */}
      {summary && (
        <div className="flex flex-wrap items-center gap-3 text-text-secondary font-medium">
          <div className="px-3 py-1.5 bg-panel-alt rounded-lg border border-border">
            Case ID: <span className="text-text-primary font-bold font-mono">{summary.case_id}</span>
          </div>
          <div className="px-3 py-1.5 bg-panel-alt rounded-lg border border-border">
            Exhibit: <span className="text-text-primary font-bold font-mono">{summary.exhibit_id}</span>
          </div>
          <div className="hidden lg:flex gap-3 px-3 py-1.5 bg-panel-alt rounded-lg border border-border">
            <span>Device: <span className="text-text-primary font-semibold">{summary.device_info.manufacturer} {summary.device_info.model}</span></span>
            <span className="text-border">|</span>
            <span>OS: <span className="text-text-primary font-semibold">Android {summary.device_info.android_version}</span></span>
            <span className="text-border">|</span>
            <span>Patch: <span className="text-text-primary font-mono">{summary.device_info.security_patch}</span></span>
          </div>
          <div className="px-3 py-1.5 bg-panel-alt rounded-lg border border-border text-accent flex items-center gap-1.5">
            <span className="text-text-secondary">Range:</span>
            <span className="font-bold">{getTimeRangeLabel(timeRange)}</span>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        {summary && (
          <div className={`px-2.5 py-1 rounded-md text-[10px] font-extrabold uppercase tracking-wide ${
            summary.acquisition_status === 'Complete' ? 'bg-success/15 text-success border border-success/20' :
            summary.acquisition_status === 'Partial' ? 'bg-warning/15 text-warning border border-warning/20' :
            'bg-danger/15 text-danger border border-danger/20'
          } border`}>
            {summary.acquisition_status}
          </div>
        )}
        {warningsCount > 0 && (
          <div 
            onClick={onShowWarnings}
            className="px-2.5 py-1 bg-warning/10 border border-warning/35 text-warning hover:bg-warning/20 rounded-md text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 cursor-pointer transition-all hover:scale-105 active:scale-95"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{warningsCount} Warnings</span>
          </div>
        )}
        <button 
          onClick={handleVerify} 
          className="p-2 bg-panel-alt border border-border hover:border-text-secondary rounded-lg text-text-secondary hover:text-text-primary transition-all duration-150" 
          title="Verify Case Hashes"
        >
          <ShieldCheck className="w-4 h-4" />
        </button>
        <button 
          onClick={handleExport} 
          className="flex items-center gap-1.5 px-3 py-2 bg-accent hover:bg-accent-hover text-white font-bold rounded-lg transition-all duration-150 shadow-md"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Report</span>
        </button>
      </div>
    </div>
  );
}
