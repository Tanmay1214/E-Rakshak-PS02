import type { CaseSummary } from '../types/evidence';
import { RefreshCw } from 'lucide-react';

interface BottomSummaryStripProps {
  summary: CaseSummary | null;
}

export default function BottomSummaryStrip({ summary }: BottomSummaryStripProps) {
  if (!summary) return null;

  const browserCount = (summary.counts.browser_history || 0) + 
                       (summary.counts.browser_searches || 0) + 
                       (summary.counts.browser_downloads || 0);

  return (
    <div className="bg-panel border-t border-border flex items-center justify-between px-6 py-2.5 z-40 select-none flex-shrink-0 text-xs shadow-inner">
      {/* Left side counter values matching the mockup format */}
      <div className="flex items-center gap-6">
        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-text-secondary/70 font-bold uppercase tracking-wider">Total Events</span>
          <span className="text-sm font-extrabold text-accent font-mono">{summary.counts.timeline_events.toLocaleString()}</span>
        </div>
        <div className="h-3 w-px bg-border/60" />
        
        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-text-secondary/70 font-bold uppercase tracking-wider">Messages</span>
          <span className="text-sm font-extrabold text-whatsapp font-mono">{summary.counts.messages.toLocaleString()}</span>
        </div>
        <div className="h-3 w-px bg-border/60" />

        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-text-secondary/70 font-bold uppercase tracking-wider">Calls</span>
          <span className="text-sm font-extrabold text-blue-500 font-mono">{summary.counts.calls.toLocaleString()}</span>
        </div>
        <div className="h-3 w-px bg-border/60" />

        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-text-secondary/70 font-bold uppercase tracking-wider">Media</span>
          <span className="text-sm font-extrabold text-orange-500 font-mono">{summary.counts.media.toLocaleString()}</span>
        </div>
        <div className="h-3 w-px bg-border/60" />

        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-text-secondary/70 font-bold uppercase tracking-wider">Locations</span>
          <span className="text-sm font-extrabold text-amber-400 font-mono">{summary.counts.locations.toLocaleString()}</span>
        </div>
        <div className="h-3 w-px bg-border/60" />

        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-text-secondary/70 font-bold uppercase tracking-wider">Browser</span>
          <span className="text-sm font-extrabold text-yellow-500 font-mono">{browserCount.toLocaleString()}</span>
        </div>
      </div>

      {/* Right side lane deduplication status badge */}
      <div className="flex items-center gap-2 bg-panel-alt px-3 py-1 rounded-lg border border-border text-[10px] text-text-secondary font-semibold">
        <RefreshCw className="w-3 h-3 text-emerald-500 animate-spin-slow" />
        <span>Dedupe: SMS/Calls merged across ADB + Collector lanes</span>
      </div>
    </div>
  );
}
