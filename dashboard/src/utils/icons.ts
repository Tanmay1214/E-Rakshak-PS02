import { 
  MessageSquare, Phone, Image as ImageIcon, MapPin, 
  Package, User, Wifi, Terminal, ShieldCheck, Globe, Hash
} from 'lucide-react';

export function getIconForSource(source: string, type?: string) {
  const s = source?.toLowerCase() || '';
  if (s.includes('whatsapp')) return { icon: MessageSquare, color: 'text-whatsapp' };
  if (s.includes('telegram')) return { icon: MessageSquare, color: 'text-telegram' };
  if (s.includes('signal')) return { icon: MessageSquare, color: 'text-signal' };
  if (type === 'call') return { icon: Phone, color: 'text-accent' };
  if (type === 'media') return { icon: ImageIcon, color: 'text-text-secondary' };
  if (type === 'location') return { icon: MapPin, color: 'text-danger' };
  if (type === 'browser') return { icon: Globe, color: 'text-warning' };
  if (type === 'system') return { icon: Terminal, color: 'text-text-primary' };
  if (type === 'network') return { icon: Wifi, color: 'text-text-secondary' };
  if (type === 'app') return { icon: Package, color: 'text-accent' };
  if (type === 'account') return { icon: User, color: 'text-text-secondary' };
  if (type === 'integrity') return { icon: ShieldCheck, color: 'text-success' };
  return { icon: Hash, color: 'text-text-secondary' };
}
