// The delta/verdict table -- one row per (metric, camera) pair, same granularity as the
// CLI's `logbench compare` text output. Takes a list of deltas rather than a whole result so
// the category panels can each show their own slice; `descriptions` (metric id -> plain-language
// meaning) is optional and, when given, prints under each metric's name once (not per camera).
import type { MetricDelta, Verdict } from './types';

const VERDICT_LABEL: Record<Verdict, string> = {
  improved: 'improved',
  regressed: 'regressed',
  neutral: 'neutral',
  'n/a': 'n/a',
  context: 'not judged',
};

export function fmt(v: number | null, unit: string | null): string {
  if (v === null) return 'n/a';
  const digits = Math.abs(v) < 10 ? 2 : 1;
  return `${v.toFixed(digits)}${unit ? ` ${unit}` : ''}`;
}

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`compare-verdict compare-verdict--${verdict.replace('/', '')}`}>
      {VERDICT_LABEL[verdict]}
    </span>
  );
}

export function ResultsTable({
  deltas,
  descriptions,
}: {
  deltas: MetricDelta[];
  descriptions?: Record<string, string>;
}) {
  // rowSpan the metric name over its camera rows, so a description prints once per metric.
  const firstOfMetric = new Set<number>();
  const spanFor = new Map<string, number>();
  deltas.forEach((d, i) => {
    if (!spanFor.has(d.id)) firstOfMetric.add(i);
    spanFor.set(d.id, (spanFor.get(d.id) ?? 0) + 1);
  });

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
          {deltas.map((d, i) => (
            <tr key={`${d.id}-${d.camera}-${i}`}>
              {firstOfMetric.has(i) && (
                <td rowSpan={spanFor.get(d.id)} className="compare-table__metric">
                  <div>{d.label}</div>
                  {descriptions?.[d.id] && (
                    <div className="compare-table__desc">{descriptions[d.id]}</div>
                  )}
                </td>
              )}
              <td>{d.camera}</td>
              <td className="compare-table__num">{fmt(d.a, d.unit)}</td>
              <td className="compare-table__num">{fmt(d.b, d.unit)}</td>
              <td className="compare-table__num">{fmt(d.delta, d.unit)}</td>
              <td>
                <VerdictChip verdict={d.verdict} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
