// The compare page's result view, laid out by *what kind of question* each metric answers
// (docs/adr/0001, D1) instead of as one flat table:
//
//   headline strip   Availability | Quality | Context, side by side. The two scored categories
//                    show A-vs-B score bars; Context sits beside them as plain numbers on a
//                    dashed border, tagged "not scored", so it reads as an explanation of the
//                    other two rather than a third score.
//   detail sections  one table per category, every metric with its plain-language meaning.
//   legacy           the older composites that mix categories, collapsed out of the way.
//
// Nothing here decides which category a metric is in or whether it is judged: that comes from the
// server (catalog + each delta's `category` and `verdict`), so the page cannot drift from core/.
import { ResultsTable, VerdictChip, fmt } from './ResultsTable';
import type { CategoryDef, CompareResult, MetricCatalog, MetricDelta } from './types';

// The headline number for each scored category. Context deliberately has none.
const SCORE_ID: Record<string, string> = {
  availability: 'availability_score',
  quality: 'quality_score',
};
const OVERALL_ID = 'health_score';

function ScoreBar({ tone, value }: { tone: 'a' | 'b'; value: number | null }) {
  const width = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="cat-bar">
      <span className="cat-bar__side">{tone.toUpperCase()}</span>
      <div className="cat-bar__track">
        <div className={`cat-bar__fill cat-bar__fill--${tone}`} style={{ width: `${width}%` }} />
      </div>
      <span className="cat-bar__value">{value === null ? 'n/a' : value.toFixed(1)}</span>
    </div>
  );
}

function ScoreRow({ d }: { d: MetricDelta }) {
  return (
    <div className="cat-score">
      <div className="cat-score__camera">{d.camera}</div>
      <div className="cat-score__bars">
        <ScoreBar tone="a" value={d.a} />
        <ScoreBar tone="b" value={d.b} />
      </div>
      <div className="cat-score__delta">
        <span>{d.delta === null ? '' : `${d.delta > 0 ? '+' : ''}${d.delta.toFixed(1)}`}</span>
        <VerdictChip verdict={d.verdict} />
      </div>
    </div>
  );
}

function ScoredCard({ def, deltas }: { def: CategoryDef; deltas: MetricDelta[] }) {
  const scores = deltas.filter((d) => d.id === SCORE_ID[def.id]);
  return (
    <section className={`cat-card cat-card--${def.id}`}>
      <h3 className="cat-card__title">{def.label}</h3>
      <div className="cat-card__question">{def.question}</div>
      {scores.length > 0 ? (
        scores.map((d) => <ScoreRow key={d.camera} d={d} />)
      ) : (
        <div className="cat-card__empty">
          Select “{def.label} score” under Metrics to see its headline number.
        </div>
      )}
      <div className="cat-card__low">
        <strong>If low:</strong> {def.low_means}
      </div>
    </section>
  );
}

function ContextCard({ def, deltas }: { def: CategoryDef; deltas: MetricDelta[] }) {
  const rows = deltas.filter((d) => d.category === 'context');
  return (
    <section className="cat-card cat-card--context">
      <h3 className="cat-card__title">
        {def.label} <span className="cat-badge">not scored</span>
      </h3>
      <div className="cat-card__question">{def.question}</div>
      {rows.length > 0 ? (
        <div className="cat-context">
          {rows.map((d, i) => (
            <div className="cat-context__row" key={`${d.id}-${d.camera}-${i}`}>
              <span className="cat-context__label">
                {d.label}
                {d.camera !== 'All' && <span className="cat-context__camera"> · {d.camera}</span>}
              </span>
              <span className="cat-context__values">
                {fmt(d.a, d.unit)} → {fmt(d.b, d.unit)}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="cat-card__empty">No context metrics selected.</div>
      )}
      <div className="cat-card__low">{def.low_means}</div>
    </section>
  );
}

export function CategoryPanels({
  result,
  catalog,
}: {
  result: CompareResult;
  catalog: MetricCatalog;
}) {
  const descriptions: Record<string, string> = {};
  for (const m of catalog.metrics) descriptions[m.id] = m.description;

  const byCategory = (id: string) => result.deltas.filter((d) => d.category === id);
  const overall = result.deltas.filter((d) => d.id === OVERALL_ID);
  const legacy = byCategory('legacy');
  const def = (id: string) => catalog.categories.find((c) => c.id === id);
  const availability = def('availability');
  const quality = def('quality');
  const context = def('context');

  return (
    <div className="cat-panels">
      <div className="cat-strip">
        {availability && <ScoredCard def={availability} deltas={result.deltas} />}
        {quality && <ScoredCard def={quality} deltas={result.deltas} />}
        {context && <ContextCard def={context} deltas={result.deltas} />}
      </div>

      {overall.length > 0 && (
        <div className="cat-overall">
          <strong>Overall</strong> (availability × quality, context never included):{' '}
          {overall.map((d, i) => (
            <span key={d.camera}>
              {i > 0 && ' · '}
              {d.camera} {fmt(d.a, null)} → {fmt(d.b, null)}
            </span>
          ))}
          . Read the two scores above rather than this product: it can hide which one moved.
        </div>
      )}

      {catalog.categories.map((c) => {
        // Composite scores are shown in the headline; the detail table is the metrics behind them.
        const rows = byCategory(c.id).filter((d) => d.id !== SCORE_ID[c.id]);
        if (rows.length === 0) return null;
        return (
          <section key={c.id} className={`cat-detail cat-detail--${c.id}`}>
            <h3 className="cat-detail__title">
              {c.label}
              {!c.scored && <span className="cat-badge">not scored</span>}
            </h3>
            <ResultsTable deltas={rows} descriptions={descriptions} />
          </section>
        );
      })}

      {legacy.length > 0 && (
        <details className="cat-legacy">
          <summary>Legacy composites ({legacy.length} rows) · mix categories, kept for continuity</summary>
          <ResultsTable deltas={legacy} descriptions={descriptions} />
        </details>
      )}
    </div>
  );
}
