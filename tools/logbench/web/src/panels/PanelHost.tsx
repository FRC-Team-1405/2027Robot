// Maps spec.panels -> components, and spec.layout -> a grid.
//
// The only place that knows which panel types exist. Adding a panel type is: write the
// component, add one line here. Nothing about the domain (cameras, vision) appears in
// any of them -- panels read tracks by id and draw whatever kind of data the spec says
// those tracks hold.

import { useState } from 'react';

import { FieldPanel } from './FieldPanel';
import { ReadoutPanel } from './ReadoutPanel';
import { TimeSeriesPanel } from './TimeSeriesPanel';
import { usePlayer } from '../player/PlayerContext';
import type { Panel } from '../player/types';

type LegendItem = [string, string];

function HealthLegend({ panel }: { panel: Panel }) {
  const legend = panel.options.legend as LegendItem[] | undefined;
  if (!legend?.length) return null;
  return (
    <details className="health-legend">
      <summary>How to read camera health</summary>
      <p>All percentages are goodness scores: higher is better.</p>
      <dl>
        {legend.map(([term, description]) => <div key={term}><dt>{term}</dt><dd>{description}</dd></div>)}
      </dl>
    </details>
  );
}

const REGISTRY: Record<string, ((props: { panel: Panel }) => React.JSX.Element) | undefined> = {
  field: FieldPanel,
  readout: ReadoutPanel,
  timeseries: TimeSeriesPanel,
};

function UnknownPanel({ panel }: { panel: Panel }) {
  return (
    <div className="panel">
      <div className="panel__title">{panel.title}</div>
      <div className="panel__empty">
        No renderer for panel type “{panel.type}”. Add one in panels/PanelHost.tsx.
      </div>
    </div>
  );
}

export function PanelHost() {
  const { spec } = usePlayer();
  const byId = Object.fromEntries(spec.panels.map((p) => [p.id, p]));
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [timelinesOpen, setTimelinesOpen] = useState(true);
  const [fieldWidth, setFieldWidth] = useState(520);

  const field = spec.panels.find((p) => p.type === 'field');
  const readout = spec.panels.find((p) => p.type === 'readout');
  const timelines = spec.panels.filter((p) => p.type === 'timeseries');

  // The camera-health layout benefits from an analysis workspace, but other specs keep
  // their declared layout unchanged. This keeps the player core metric-agnostic.
  if (field && timelines.length) {
    const resize = (event: React.PointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = fieldWidth;
      const move = (e: PointerEvent) =>
        setFieldWidth(Math.max(520, Math.min(1100, startWidth + e.clientX - startX)));
      const stop = () => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', stop);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', stop);
    };

    return (
      <div className="analysis-layout">
        <div className={`analysis-workspace${inspectorOpen ? ' analysis-workspace--inspect' : ''}`} style={{ '--field-width': `${fieldWidth}px` } as React.CSSProperties}>
          <div className="analysis-main">
            <div className="analysis-main__head">
              <span>Playback view</span>
              <button className="panel-action" onClick={() => setInspectorOpen((v) => !v)} aria-expanded={inspectorOpen}>
                {inspectorOpen ? 'Hide chart inspector' : 'Inspect camera timelines'}
              </button>
            </div>
            <div className="analysis-field-row">
              <FieldPanel panel={field} />
            </div>
          </div>
          {inspectorOpen && (
            <aside className="inspector" aria-label="Camera timeline inspector">
              <div className="inspector__handle" onPointerDown={resize} title="Drag to resize" />
              <div className="inspector__heading">
                <span>Camera timeline</span>
                <span>Shift + scroll to zoom · hover for samples</span>
              </div>
              <div className="inspector__charts">
                {timelines.map((panel) => <TimeSeriesPanel key={panel.id} panel={panel} expanded />)}
              </div>
            </aside>
          )}
        </div>
        {readout && <>
          <ReadoutPanel panel={readout} />
          <HealthLegend panel={readout} />
        </>}
        <section className="timeline-dock">
          <button className="timeline-dock__toggle" onClick={() => setTimelinesOpen((v) => !v)} aria-expanded={timelinesOpen}>
            <span>Camera timelines</span><span>{timelinesOpen ? 'Collapse' : 'Expand'}</span>
          </button>
          {timelinesOpen && <div className="timeline-dock__content">{timelines.map((panel) => <TimeSeriesPanel key={panel.id} panel={panel} />)}</div>}
        </section>
      </div>
    );
  }

  return (
    <div className="grid">
      {spec.layout.map((row, i) => (
        <div className="grid__row" key={i} data-cols={row.length}>
          {row.map((id) => {
            const panel = byId[id];
            if (!panel) return null;
            const Component = REGISTRY[panel.type] ?? UnknownPanel;
            return <Component key={id} panel={panel} />;
          })}
        </div>
      ))}
    </div>
  );
}
