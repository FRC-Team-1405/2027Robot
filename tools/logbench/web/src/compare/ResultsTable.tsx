// The delta/verdict table -- one row per (metric, camera) pair, same granularity as the
// CLI's `logbench compare` text output.
import type { CompareResult, Verdict } from './types';

const VERDICT_LABEL: Record<Verdict, string> = {
  improved: 'improved',
  regressed: 'regressed',
  neutral: 'neutral',
  'n/a': 'n/a',
};

function fmt(v: number | null, unit: string | null): string {
  if (v === null) return 'n/a';
  const digits = Math.abs(v) < 10 ? 2 : 1;
  return `${v.toFixed(digits)}${unit ? ` ${unit}` : ''}`;
}

export function ResultsTable({ result }: { result: CompareResult }) {
  return (
    <div className="compare-results">
      <table className="compare-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Camera</th>
            <th>A</th>
            <th>B</th>
            <th>&Delta;</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          {result.deltas.map((d, i) => (
            <tr key={`${d.id}-${d.camera}-${i}`}>
              <td>{d.label}</td>
              <td>{d.camera}</td>
              <td className="compare-table__num">{fmt(d.a, d.unit)}</td>
              <td className="compare-table__num">{fmt(d.b, d.unit)}</td>
              <td className="compare-table__num">{fmt(d.delta, d.unit)}</td>
              <td>
                <span className={`compare-verdict compare-verdict--${d.verdict.replace('/', '')}`}>
                  {VERDICT_LABEL[d.verdict]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
