import { 
  MessageSquare, Phone, Image as ImageIcon, MapPin, 
  Package, Wifi, Terminal, ShieldCheck, Globe, Hash
} from 'lucide-react';

export function getIconForSource(source: string | undefined | null, type?: string) {
  const s = (source || '').toLowerCase();
  const t = (type || '').toLowerCase();

  // WhatsApp
  if (s.includes('whatsapp')) {
    return { icon: MessageSquare, color: 'text-whatsapp', bg: 'bg-whatsapp/10', border: 'border-whatsapp/30' };
  }
  // Telegram
  if (s.includes('telegram')) {
    return { icon: MessageSquare, color: 'text-telegram', bg: 'bg-telegram/10', border: 'border-telegram/30' };
  }
  // Signal
  if (s.includes('signal')) {
    return { icon: MessageSquare, color: 'text-signal', bg: 'bg-signal/10', border: 'border-signal/30' };
  }
  // SMS
  if (s.includes('sms') || t.includes('sms')) {
    return { icon: MessageSquare, color: 'text-violet-400', bg: 'bg-violet-400/10', border: 'border-violet-400/30' };
  }
  // Calls/Phone
  if (t === 'call' || t.includes('call') || s.includes('call') || s === 'phone') {
    return { icon: Phone, color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
  }
  // Browser/Chrome
  if (t === 'browser' || t.includes('browser') || s.includes('browser') || s.includes('chrome')) {
    return { icon: Globe, color: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' };
  }
  // Media
  if (t === 'media' || t.includes('media') || s.includes('media')) {
    return { icon: ImageIcon, color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/30' };
  }
  // Location
  if (t === 'location' || t.includes('location') || s.includes('location') || s.includes('gps')) {
    return { icon: MapPin, color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/30' };
  }
  // Apps
  if (t === 'app' || t.includes('app')) {
    return { icon: Package, color: 'text-emerald-500', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
  }
  // Network
  if (t === 'network' || t.includes('network')) {
    return { icon: Wifi, color: 'text-sky-400', bg: 'bg-sky-400/10', border: 'border-sky-400/30' };
  }
  // System
  if (t === 'system' || t.includes('system') || t.includes('logcat')) {
    return { icon: Terminal, color: 'text-slate-400', bg: 'bg-slate-400/10', border: 'border-slate-400/30' };
  }
  // Integrity
  if (t === 'integrity' || t.includes('integrity')) {
    return { icon: ShieldCheck, color: 'text-success', bg: 'bg-success/10', border: 'border-success/30' };
  }

  return { icon: Hash, color: 'text-text-secondary', bg: 'bg-panel-alt', border: 'border-border' };
}
