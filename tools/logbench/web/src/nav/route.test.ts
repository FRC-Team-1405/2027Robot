import { describe, expect, it } from 'vitest';
import { buildSearch, parseRoute, resolveView, routeFromHref } from './route';

describe('route', () => {
  it('reads the page and the open log from the query string', () => {
    expect(parseRoute('?view=vision&log=a%2Fb.wpilog')).toEqual({ view: 'vision', log: 'a/b.wpilog' });
    expect(parseRoute('')).toEqual({ view: null, log: null });
  });

  it('lands on Health Check, keeps old ?log= links on Vision Logs, and maps the old pit name', () => {
    expect(resolveView({ view: null, log: null })).toBe('health');
    expect(resolveView({ view: null, log: 'x.wpilog' })).toBe('replay');
    expect(resolveView({ view: 'pit', log: null })).toBe('health');
    expect(resolveView({ view: 'compare', log: 'x' })).toBe('compare');
    expect(resolveView({ view: 'compare', log: 'x' }, true)).toBe('replay');
  });

  it('changes the page without dropping the open log, and the log without dropping the page', () => {
    expect(buildSearch('?view=health&log=x.wpilog', { view: 'battery' })).toBe('?view=battery&log=x.wpilog');
    expect(buildSearch('?view=health&log=x.wpilog', { log: 'y z.wpilog' })).toBe('?view=health&log=y+z.wpilog');
    expect(buildSearch('?view=health&log=x.wpilog', { log: null })).toBe('?view=health');
  });

  it('leaves parameters it does not own alone', () => {
    expect(buildSearch('?debug&spec=camera_health', { view: 'replay', log: 'x' })).toBe('?debug=&spec=camera_health&view=replay&log=x');
  });

  it('treats ?view= links as in-app navigation and ignores everything else', () => {
    expect(routeFromHref('?view=fetch')).toEqual({ view: 'fetch' });
    expect(routeFromHref('?view=health&log=a%2Fb.wpilog')).toEqual({ view: 'health', log: 'a/b.wpilog' });
    expect(routeFromHref('?log=a.wpilog')).toEqual({ view: 'replay', log: 'a.wpilog' });
    expect(routeFromHref('/api/compare/export?x=1')).toBeNull();
    expect(routeFromHref('https://example.com/?view=fetch')).toBeNull();
    expect(routeFromHref('?something=else')).toBeNull();
  });
});
