import type { CaseSummary } from '../types/evidence';
import { Download, Shield, Calendar, Folder, MoreVertical } from 'lucide-react';
import { exportReport } from '../services/api';

interface TopBarProps {
  summary: CaseSummary | null;
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
}

export default function TopBar({ summary, timeRange, onTimeRangeChange }: TopBarProps) {
  
  const handleExport = async () => {
    try {
      await exportReport();
      alert('Report exported successfully.');
    } catch (err) {
      alert('Export failed.');
    }
  };

  const getAcquisitionStatus = () => {
    if (!summary) return { text: 'No Device', style: 'bg-slate-500/10 text-slate-400 border border-slate-500/30' };
    
    const hasTimeline = (summary.counts.timeline_events || 0) > 0;
    const hasWarnings = (summary.warnings?.length || 0) > 0 || (summary.missing_sources?.length || 0) > 0;
    
    if (hasTimeline) {
      if (hasWarnings) {
        return {
          text: 'Partial Acquisition',
          style: 'bg-warning/10 text-warning border-warning/20'
        };
      }
      return {
        text: 'Timeline Built',
        style: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      };
    }
    
    return {
      text: 'Acquisition Failed',
      style: 'bg-danger/10 text-danger border-danger/20'
    };
  };

  const status = getAcquisitionStatus();

  return (
    <div className="flex items-center justify-between px-6 py-2.5 bg-panel border-b border-border text-xs z-50 flex-shrink-0 select-none">
      
      {/* Left Title & Branding */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent shadow-sm">
          <Shield className="w-5 h-5 fill-accent/10" />
        </div>
        <div className="flex flex-col">
          <h1 className="text-sm font-black tracking-wider text-text-primary uppercase leading-none">E-RAKSHAK</h1>
          <span className="text-text-secondary text-[9px] font-bold tracking-wide mt-0.5">Rapid Evidence Triage</span>
        </div>
        
        {/* Rapid Evidence Triage badge wrapper */}
        <div className="h-6 w-px bg-border/60 mx-1.5" />
        <div className="flex flex-col">
          <span className="text-text-primary text-[11px] font-bold">Rapid Evidence Triage</span>
          <span className="text-text-secondary text-[8px] font-semibold mt-0.5">Android Forensic Preview Tool</span>
        </div>
      </div>

      {/* Center metadata boxes */}
      {summary && (
        <div className="flex items-center gap-3">
          {/* Case ID */}
          <div className="flex flex-col px-3 py-1 bg-panel-alt rounded border border-border">
            <span className="text-[8px] text-text-secondary font-bold uppercase tracking-wider">Case ID</span>
            <span className="text-text-primary font-bold font-mono text-[10px] mt-0.5">{summary.case_id}</span>
          </div>

          {/* Evidence ID */}
          <div className="flex flex-col px-3 py-1 bg-panel-alt rounded border border-border">
            <span className="text-[8px] text-text-secondary font-bold uppercase tracking-wider">Evidence ID</span>
            <span className="text-text-primary font-bold font-mono text-[10px] mt-0.5">{summary.exhibit_id}</span>
          </div>

          {/* Device and Android OS */}
          <div className="flex flex-col px-3 py-1 bg-panel-alt rounded border border-border max-w-[200px] truncate">
            <span className="text-[8px] text-text-secondary font-bold uppercase tracking-wider">Device</span>
            <span className="text-text-primary font-semibold text-[10px] mt-0.5 truncate">
              {summary.device_info.manufacturer} {summary.device_info.model} (Android {summary.device_info.android_version})
            </span>
          </div>

          {/* Acquisition status pill */}
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] border font-bold uppercase tracking-wide ${status.style}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              status.text === 'Timeline Built' ? 'bg-emerald-500 animate-pulse' :
              status.text === 'Partial Acquisition' ? 'bg-amber-500' : 'bg-red-500'
            }`} />
            <span>{status.text}</span>
          </div>

          {/* Time Window Selector Dropdown */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-panel-alt rounded border border-border text-text-primary text-[10px] font-bold">
            <Calendar className="w-3.5 h-3.5 text-text-secondary" />
            <select 
              value={timeRange} 
              onChange={(e) => onTimeRangeChange(e.target.value)} 
              className="bg-transparent border-none focus:outline-none pr-1 cursor-pointer font-bold"
            >
              <option value="24h" className="bg-panel text-text-primary">Last 24 Hours</option>
              <option value="7d" className="bg-panel text-text-primary">Last 7 Days</option>
              <option value="custom" className="bg-panel text-text-primary">Custom Range</option>
            </select>
          </div>
        </div>
      )}

      {/* Right-side action buttons */}
      <div className="flex items-center gap-2">
        <button 
          onClick={handleExport} 
          className="flex items-center gap-1.5 px-3 py-1.5 bg-accent hover:bg-accent-hover text-white font-bold rounded shadow-md transition-all duration-150"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Report</span>
        </button>

        <button 
          onClick={() => alert('Accessing local exhibit case directory: ' + (summary?.case_id || 'EXH-001'))}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-panel-alt hover:bg-panel-alt/80 border border-border text-text-primary font-bold rounded transition-all duration-150"
        >
          <Folder className="w-3.5 h-3.5 text-accent" />
          <span>Case Folder</span>
        </button>

        <button 
          onClick={() => alert('Forensic triage actions menu.')}
          className="p-1.5 bg-panel-alt hover:bg-panel-alt/80 border border-border text-text-secondary hover:text-text-primary rounded transition-all duration-150"
        >
          <MoreVertical className="w-3.5 h-3.5" />
        </button>
      </div>

    </div>
  );
}
