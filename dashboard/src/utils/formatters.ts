function parseTimestampToDate(ts: string | number | undefined | null): Date | null {
  if (ts === undefined || ts === null || ts === '') return null;

  let numVal: number | null = null;
  if (typeof ts === 'number') {
    numVal = ts;
  } else if (typeof ts === 'string') {
    const trimmed = ts.trim();
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
      numVal = parseFloat(trimmed);
    }
  }

  if (numVal !== null && !isNaN(numVal)) {
    const ms = numVal < 100000000000 ? numVal * 1000 : numVal;
    return new Date(ms);
  }

  const d = new Date(ts);
  return isNaN(d.getTime()) ? null : d;
}

export function formatEventDate(timestamp: string | number | undefined | null, timestampSort: string | number | undefined | null): string {
  const dateObj = parseTimestampToDate(timestamp) || parseTimestampToDate(timestampSort);
  if (!dateObj) return 'Unknown date';
  
  const day = dateObj.getDate();
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[dateObj.getMonth()];
  const year = dateObj.getFullYear();
  return `${day} ${month} ${year}`;
}

export function formatEventTime(timestamp: string | number | undefined | null, timestampSort: string | number | undefined | null): string {
  const dateObj = parseTimestampToDate(timestamp) || parseTimestampToDate(timestampSort);
  if (!dateObj) return '00:00:00';

  const hours = String(dateObj.getHours()).padStart(2, '0');
  const minutes = String(dateObj.getMinutes()).padStart(2, '0');
  const seconds = String(dateObj.getSeconds()).padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

export function formatTimestamp(ts: string | number | undefined | null): string {
  if (!ts) return '';
  const tsStr = String(ts).trim();
  // If it's already a formatted display timestamp (e.g. "27 Jul 2026, 06:35:05 PM"), return as-is
  if (/[a-zA-Z]{3}\s+\d{4}/.test(tsStr) && (tsStr.includes(",") || tsStr.includes("AM") || tsStr.includes("PM"))) {
    return tsStr;
  }
  const dateObj = parseTimestampToDate(ts);
  if (!dateObj) return String(ts);
  return `${formatEventDate(ts, undefined)} ${formatEventTime(ts, undefined)}`;
}

export function formatDuration(seconds: number): string {
  if (isNaN(seconds)) return '0s';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function formatPhone(phone: string): string {
  return phone;
}

export function truncateText(text: string, max: number): string {
  if (!text) return '';
  if (text.length <= max) return text;
  return text.substring(0, max) + '...';
}

export function timeAgo(ts: string): string {
  if (!ts) return '';
  const date = new Date(ts);
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);

  let interval = seconds / 31536000;
  if (interval > 1) return Math.floor(interval) + ' years ago';
  interval = seconds / 2592000;
  if (interval > 1) return Math.floor(interval) + ' months ago';
  interval = seconds / 86400;
  if (interval > 1) return Math.floor(interval) + ' days ago';
  interval = seconds / 3600;
  if (interval > 1) return Math.floor(interval) + ' hours ago';
  interval = seconds / 60;
  if (interval > 1) return Math.floor(interval) + ' minutes ago';
  return Math.floor(seconds) + ' seconds ago';
}
