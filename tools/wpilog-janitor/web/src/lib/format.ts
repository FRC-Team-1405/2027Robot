export function fmtBytes(n: number): string {
  if (!Number.isFinite(n)) return '—';
  const sign = n < 0 ? '-' : '';
  n = Math.abs(n);
  if (n < 1024) return `${sign}${Math.round(n)} B`;
  const units = ['KB', 'MB', 'GB'];
  let i = -1;
  do {
    n /= 1024;
    i++;
  } while (n >= 1024 && i < units.length - 1);
  return `${sign}${n >= 100 ? n.toFixed(0) : n.toFixed(1)} ${units[i]}`;
}

/** Seconds as `12.3 s`, or `2:05.3` once past a minute. */
export function fmtTime(s: number): string {
  if (!Number.isFinite(s)) return '—';
  const sign = s < 0 ? '-' : '';
  s = Math.abs(s);
  if (s < 60) return `${sign}${s.toFixed(s < 10 ? 2 : 1)} s`;
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return `${sign}${m}:${rest.toFixed(1).padStart(4, '0')}`;
}

export function fmtDuration(s: number): string {
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min ${Math.round(s - m * 60)} s` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function fmtPct(p: number): string {
  return `${p >= 99.95 ? p.toFixed(0) : p.toFixed(1)}%`;
}

export function fmtDate(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** `logs/offseason/9-1/x.wpilog` -> `x` */
export function stemOf(path: string): string {
  const name = path.split('/').pop() ?? path;
  return name.replace(/\.wpilog$/i, '');
}
