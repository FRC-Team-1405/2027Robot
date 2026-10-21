// Everything the log picker shows about a log that can be read off its name and file stats,
// without parsing the log. Competition logs are named like akit_26-10-17_12-36-15_nyroc1_q1.wpilog:
// the recorder's local start time, then whatever the team appended (event and match).
import type { LogEntry } from '../compare/types';

export interface ParsedName {
  when: Date | null;
  /** The descriptive tail of the name ("nyroc1 q1"), empty when there is none. */
  tag: string;
}

const NAME = /^(?:akit|frc)_(\d{2})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})(?:_(.*?))?(?:\.trimmed)?\.wpilog$/i;

export function parseLogName(name: string): ParsedName {
  const m = NAME.exec(name);
  if (!m) return { when: null, tag: name.replace(/\.wpilog$/i, '').replace(/_/g, ' ') };
  const [yy, mo, dd, hh, mi, ss] = m.slice(1, 7).map(Number);
  return { when: new Date(2000 + yy, mo - 1, dd, hh, mi, ss), tag: (m[7] ?? '').replace(/_/g, ' ') };
}

/** When the log was recorded: the time in its name, else the file's modification time. Milliseconds. */
export function logTime(entry: Pick<LogEntry, 'name' | 'mtime'>): number {
  return parseLogName(entry.name).when?.getTime() ?? entry.mtime * 1000;
}

export function formatSize(bytes: number): string {
  return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} KB`;
}

export function formatWhen(ms: number): string {
  return new Date(ms).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function formatAge(ms: number, now = Date.now()): string {
  const minutes = Math.max(0, (now - ms) / 60000);
  if (minutes < 60) return `${Math.round(minutes)} min ago`;
  if (minutes < 60 * 48) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} d ago`;
}

export function formatDuration(seconds: number): string {
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** One line for a dropdown option: "Oct 17, 12:36 PM · nyroc1 q1 · 49.6 MB". */
export function logLabel(entry: LogEntry): string {
  const tag = parseLogName(entry.name).tag || entry.name;
  return `${formatWhen(logTime(entry))} · ${tag} · ${formatSize(entry.size)}`;
}
