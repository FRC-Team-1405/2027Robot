// Replaces the old <details> dropdown menu (and, briefly, a collapsible hamburger
// version of this component) with a plain, always-visible tab bar -- collapsing it
// bought no vertical space back since the bar stayed on screen either way, and hiding
// navigation behind a click made "which page am I on" harder to answer, not easier.
// Still query-param routing (?view=...), no router dependency. Rendered once at the top
// of App.tsx so every view (including Compare/Pit Check/Fetch Bundle/the log picker) gets
// the same bar, instead of each page rolling its own back-link.

interface Tab {
  label: string;
  view: string | null; // null = default view (Vision Logs / replay)
}

const TABS: Tab[] = [
  { label: 'Vision Logs', view: null },
  { label: 'Compare', view: 'compare' },
  { label: 'Battery Insights', view: 'battery' },
  { label: 'Pit Check', view: 'pit' },
  { label: 'Fetch Bundle', view: 'fetch' },
];

function href(view: string | null): string {
  return view ? `?view=${view}` : window.location.pathname;
}

export function TabNav() {
  const activeView = new URLSearchParams(window.location.search).get('view');

  return (
    <nav className="tab-nav">
      {TABS.map((tab) => {
        const isActive = tab.view === activeView || (tab.view === null && !activeView);
        return (
          <a
            key={tab.label}
            className={`tab-nav__tab${isActive ? ' tab-nav__tab--active' : ''}`}
            href={href(tab.view)}
          >
            {tab.label}
          </a>
        );
      })}
    </nav>
  );
}
