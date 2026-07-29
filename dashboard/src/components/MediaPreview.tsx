import { Image as ImageIcon, File, Video, Music } from 'lucide-react';
import { formatBytes } from '../utils/formatters';

interface MediaPreviewProps {
  filename: string;
  mimeType: string;
  sizeBytes: number;
  filePath: string;
}

export default function MediaPreview({ filename, mimeType, sizeBytes, filePath }: MediaPreviewProps) {
  const isImage = mimeType.startsWith('image/');
  const isVideo = mimeType.startsWith('video/');
  const isAudio = mimeType.startsWith('audio/');

  return (
    <div className="border border-border rounded-lg p-4 bg-panel-alt flex flex-col items-center justify-center gap-3">
      {isImage ? (
        <div className="w-full aspect-video bg-panel rounded flex items-center justify-center border border-border">
          <ImageIcon className="w-12 h-12 text-text-secondary opacity-50" />
        </div>
      ) : isVideo ? (
        <Video className="w-12 h-12 text-accent" />
      ) : isAudio ? (
        <Music className="w-12 h-12 text-warning" />
      ) : (
        <File className="w-12 h-12 text-text-secondary" />
      )}
      
      <div className="text-center w-full">
        <p className="text-sm font-medium text-text-primary truncate" title={filename}>{filename}</p>
        <div className="flex items-center justify-center gap-2 text-xs text-text-secondary mt-1">
          <span>{mimeType}</span>
          <span>•</span>
          <span>{formatBytes(sizeBytes)}</span>
        </div>
        <p className="text-[10px] text-text-secondary mt-2 break-all font-mono opacity-50">{filePath}</p>
      </div>
    </div>
  );
}
