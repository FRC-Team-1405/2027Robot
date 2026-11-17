// A plain, always-visible tab bar -- collapsing it bought no vertical space back, and hiding
// navigation behind a click made "which page am I on" harder to answer, not easier.
// Tabs are ordinary links to `?view=...`; App intercepts clicks on them (see nav/route.ts) so
// switching pages is a pushState, not a reload, and the open log travels with you.

import { resolveView, useRoute } from './route';

interface Tab {
  label: string;
  view: string;
}

const TABS: Tab[] = [
  { label: 'Health Check', view: 'health' },
  { label: 'Vision Logs', view: 'replay' },
  { label: 'Vision Insights', view: 'vision' },
  { label: 'Compare', view: 'compare' },
  { label: 'Battery Insights', view: 'battery' },
  { label: 'Connections', view: 'connections' },
  { label: 'Fetch Bundle', view: 'fetch' },
];

export function TabNav() {
  const activeView = resolveView(useRoute());

  return (
    <nav className="tab-nav">
      {TABS.map((tab) => {
        const isActive = tab.view === activeView;
        return (
          <a
            key={tab.label}
            className={`tab-nav__tab${isActive ? ' tab-nav__tab--active' : ''}`}
            href={`?view=${tab.view}`}
            aria-current={isActive ? 'page' : undefined}
          >
            {tab.label}
          </a>
        );
      })}
    </nav>
  );
}
