import { useEffect, useRef } from 'react';
import type { ContentEntry } from '../api';
import { fmtBytes, fmtPct } from '../lib/format';
import { checkState, type Row } from '../lib/tree';

interface Props {
  rows: Row[];
  totalBytes: number;
  isExcluded: (name: string) => boolean;
  onToggle: (names: string[], on: boolean) => void;
  onExpand: (key: string) => void;
}

function fmtRate(hz: number): string {
  if (hz === 0) return '—';
  if (hz >= 10) return `${hz.toFixed(0)}/s`;
  if (hz >= 0.1) return `${hz.toFixed(1)}/s`;
  return '<0.1/s';
}

function Check({ state, label, onChange }: { state: 'none' | 'some' | 'all'; label: string; onChange: (on: boolean) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = state === 'some';
  }, [state]);
  return <input ref={ref} type="checkbox" aria-label={label} checked={state === 'all'} onChange={(e) => onChange(e.target.checked)} />;
}

function Flags({ e }: { e: ContentEntry }) {
  return (
    <span className="flags">
      {e.constant && <span className="flag const" title="One value for the whole analysed window">constant</span>}
      <span className={`flag cls-${e.cls}`} title={e.cls === 'output' ? 'Computed by the robot code; replay regenerates it' : e.cls === 'replay-input' ? 'Recorded by Logger.processInputs; replay reads it back' : e.cls === 'structural' ? 'Needed to read the log at all' : 'Written by wpilog-janitor'}>
        {e.cls === 'replay-input' ? 'input' : e.cls}
      </span>
      {e.protected && (
        <span className="lock" role="img" aria-label={`Protected: ${e.protected}`} title={e.protected}>
          🔒
        </span>
      )}
    </span>
  );
}

export function TreeTable({ rows, totalBytes, isExcluded, onToggle, onExpand }: Props) {
  if (rows.length === 0) return <p className="empty">No entries match.</p>;
  return (
    <div className="table-wrap tall">
      <table className="tree">
        <thead>
          <tr>
            <th aria-label="Exclude" />
            <th>Entry</th>
            <th>Size in window</th>
            <th className="r">Share</th>
            <th className="r">Records</th>
            <th className="r">Rate</th>
            <th>Type</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ node, expanded, hasChildren }) => {
            const e = node.entry;
            const state = checkState(node.leaves, isExcluded);
            const share = totalBytes > 0 ? (node.bytes / totalBytes) * 100 : 0;
            const isFolder = hasChildren;
            return (
              <tr key={node.key} className={`${state === 'all' ? 'excluded' : ''} ${isFolder ? 'folder' : ''}`}>
                <td className="check">
                  <Check
                    state={state}
                    label={`Exclude ${node.key}${isFolder ? ` and everything under it (${node.leaves.length} entries)` : ''}`}
                    onChange={(on) => onToggle(node.leaves.map((l) => l.name), on)}
                  />
                </td>
                <td className="name" style={{ paddingLeft: 8 + node.depth * 16 }}>
                  {isFolder ? (
                    <button type="button" className="chev" aria-expanded={expanded} aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.key}`} onClick={() => onExpand(node.key)}>
                      {expanded ? '▾' : '▸'}
                    </button>
                  ) : (
                    <span className="chev-space" />
                  )}
                  <span className="label" title={e ? `${e.name}${e.sample ? `\nlatest value: ${e.sample}` : ''}` : node.key}>
                    {node.label}
                  </span>
                  {isFolder && <span className="muted small"> {node.leaves.length} entries</span>}
                  {e && <Flags e={e} />}
                </td>
                <td className="sizecell">
                  <span className="minibar" aria-hidden="true">
                    <span style={{ width: `${Math.max(share > 0 ? 0.5 : 0, Math.min(100, share))}%` }} />
                  </span>
                  <span className="num-txt">{fmtBytes(node.bytes)}</span>
                </td>
                <td className="r">{share > 0 ? fmtPct(share) : '—'}</td>
                <td className="r">{node.records.toLocaleString()}</td>
                <td className="r muted">{e ? fmtRate(e.hz) : ''}</td>
                <td className="muted small">{e ? e.type : ''}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
