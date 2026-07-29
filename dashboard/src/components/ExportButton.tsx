import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { exportReport } from '../services/api';

export default function ExportButton() {
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      await exportReport();
      alert('Report exported successfully');
    } catch (err) {
      alert('Failed to export report');
    } finally {
      setLoading(false);
    }
  };

  return (
    <button 
      onClick={handleExport} 
      disabled={loading}
      className="flex items-center gap-2 px-3 py-2 bg-accent hover:bg-accent-hover disabled:bg-accent/50 text-white rounded-md transition-colors shadow-lg"
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
      <span>{loading ? 'Generating...' : 'Export Report'}</span>
    </button>
  );
}
