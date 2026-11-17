// Sorting and searching for the log browser, kept free of React so it is unit-tested.
import type { LogDetails, LogEntry } from '../compare/types';
import { logTime, parseLogName } from '../lib/logName';

export type SortKey = 'when' | 'name' | 'folder' | 'size';
export interface Sort { key: SortKey; dir: 'asc' | 'desc' }

const label = (log: LogEntry) => parseLogName(log.name).tag || log.name;

export function sortLogs(logs: LogEntry[], { key, dir }: Sort): LogEntry[] {
  const value = (log: LogEntry): number | string => {
    switch (key) {
      case 'when': return logTime(log);
      case 'size': return log.size;
      case 'folder': return log.folder ?? '';
      default: return label(log).toLowerCase();
    }
  };
  const sign = dir === 'asc' ? 1 : -1;
  return [...logs].sort((a, b) => {
    const x = value(a), y = value(b);
    const order = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true });
    // Ties fall back to newest first so the order never looks arbitrary.
    return sign * order || logTime(b) - logTime(a);
  });
}

/** Every word in the query must appear somewhere in the log's path, event/match, or cameras. */
export function filterLogs(logs: LogEntry[], query: string, details: Record<string, LogDetails | undefined> = {}): LogEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return logs;
  return logs.filter((log) => {
    const d = details[log.path];
    const haystack = [log.path, parseLogName(log.name).tag, ...(log.vision_cameras ?? []),
      d?.event, d?.match_type, d?.match_number == null ? null : `match ${d.match_number}`, ...(d?.cameras ?? [])]
      .filter(Boolean).join(' ').toLowerCase();
    return words.every((word) => haystack.includes(word));
  });
}
