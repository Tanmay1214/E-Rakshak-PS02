import { MapPin, Copy } from 'lucide-react';

interface LocationPreviewProps {
  latitude: number;
  longitude: number;
  accuracy: number;
}

export default function LocationPreview({ latitude, longitude, accuracy }: LocationPreviewProps) {
  const handleCopy = () => {
    navigator.clipboard.writeText(`${latitude}, ${longitude}`);
  };

  return (
    <div className="border border-border rounded-lg p-4 bg-panel-alt">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-danger/10 rounded-full text-danger">
            <MapPin className="w-5 h-5" />
          </div>
          <span className="font-medium text-text-primary">Coordinates</span>
        </div>
        <button onClick={handleCopy} className="p-1.5 hover:bg-border rounded text-text-secondary transition-colors" title="Copy coordinates">
          <Copy className="w-4 h-4" />
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="block text-xs text-text-secondary mb-1">Latitude</span>
          <span className="font-mono text-text-primary">{latitude.toFixed(6)}</span>
        </div>
        <div>
          <span className="block text-xs text-text-secondary mb-1">Longitude</span>
          <span className="font-mono text-text-primary">{longitude.toFixed(6)}</span>
        </div>
      </div>
      
      <div className="mt-3 pt-3 border-t border-border text-xs text-text-secondary flex justify-between">
        <span>Accuracy</span>
        <span>±{accuracy}m</span>
      </div>
    </div>
  );
}
