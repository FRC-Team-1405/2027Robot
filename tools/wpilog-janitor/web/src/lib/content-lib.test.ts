import { describe, expect, it } from 'vitest';
import type { ContentEntry } from '../api';
import { clearExcluded, countExcluded, isExcluded, setExcluded, totalRules } from './exclusions';
import { allKeys, buildTree, checkState, flatten } from './tree';

let id = 0;
const entry = (name: string, bytes: number, over: Partial<ContentEntry> = {}): ContentEntry => ({
  id: ++id,
  name,
  type: 'double',
  bytes,
  records: bytes / 10,
  hz: 1,
  changes: 0,
  distinct: 5,
  distinct_capped: false,
  constant: false,
  cls: 'replay-input',
  protected: null,
  first_s: 0,
  last_s: 1,
  sample: null,
  num: null,
  ...over,
});

const entries = [
  entry('/RealOutputs/Vision/Left/Poses', 400),
  entry('/RealOutputs/Vision/Right/Poses', 300),
  entry('/RealOutputs/Logger/Loop', 50),
  entry('/Vision/Left/Raw', 900),
  entry('/Vision/Right/Raw', 100),
  entry('/Timestamp', 20),
  entry('/Vision', 5), // an entry that is also a parent
];
const none = { exclude: [], exclude_prefixes: [] };

describe('tree', () => {
  const tree = buildTree(entries);

  it('groups by path and rolls sizes up, largest first', () => {
    expect(tree.map((n) => [n.label, n.bytes])).toEqual([
      ['Vision', 1005],
      ['RealOutputs', 750],
      ['Timestamp', 20],
    ]);
    const vision = tree[0];
    expect(vision.entry?.name).toBe('/Vision'); // both an entry and a parent
    expect(vision.children.map((c) => c.label)).toEqual(['Left', 'Right']);
    expect(vision.children[0].bytes).toBe(900);
    expect(vision.leaves).toHaveLength(3);
    expect(tree[1].children.map((c) => c.label)).toEqual(['Vision', 'Logger']);
    expect(tree.reduce((s, n) => s + n.bytes, 0)).toBe(entries.reduce((s, e) => s + e.bytes, 0));
  });

  it('flattens only what is expanded', () => {
    expect(flatten(tree, new Set(), '').map((r) => r.node.key)).toEqual(['/Vision', '/RealOutputs', '/Timestamp']);
    const rows = flatten(tree, new Set(['/Vision']), '');
    expect(rows.map((r) => r.node.key)).toEqual(['/Vision', '/Vision/Left', '/Vision/Right', '/RealOutputs', '/Timestamp']);
    expect(rows[0]).toMatchObject({ expanded: true, hasChildren: true });
    expect(rows[1]).toMatchObject({ expanded: false, hasChildren: true }); // Left has a child (Raw) but is not open
    expect(rows[4]).toMatchObject({ expanded: false, hasChildren: false });
  });

  it('a filter expands to the matches and hides the rest', () => {
    const keys = flatten(tree, new Set(), 'left').map((r) => r.node.key);
    expect(keys).toEqual([
      '/Vision',
      '/Vision/Left',
      '/Vision/Left/Raw',
      '/RealOutputs',
      '/RealOutputs/Vision',
      '/RealOutputs/Vision/Left',
      '/RealOutputs/Vision/Left/Poses',
    ]);
    expect(flatten(tree, new Set(), 'right poses').map((r) => r.node.key).pop()).toBe('/RealOutputs/Vision/Right/Poses');
    expect(flatten(tree, new Set(), 'zzz')).toEqual([]);
  });

  it('lists the nodes that can be expanded', () => {
    expect(allKeys(tree).sort()).toEqual(
      ['/RealOutputs', '/RealOutputs/Logger', '/RealOutputs/Vision', '/RealOutputs/Vision/Left', '/RealOutputs/Vision/Right', '/Vision', '/Vision/Left', '/Vision/Right'].sort(),
    );
  });

  it('reports none / some / all excluded', () => {
    const ex = { exclude: ['/Vision/Left/Raw'], exclude_prefixes: [] };
    const is = (n: string) => isExcluded(n, ex);
    expect(checkState(tree[0].children[0].leaves, is)).toBe('all');
    expect(checkState(tree[0].leaves, is)).toBe('some');
    expect(checkState(tree[1].leaves, is)).toBe('none');
    expect(checkState([], is)).toBe('none');
  });
});

describe('exclusions', () => {
  const universe = entries.map((e) => e.name);

  it('adds exact names once and removes them', () => {
    const a = setExcluded(none, ['/Vision/Left/Raw', '/Vision/Left/Raw'], true, universe);
    expect(a.exclude).toEqual(['/Vision/Left/Raw']);
    expect(setExcluded(a, ['/Vision/Left/Raw'], true, universe).exclude).toHaveLength(1);
    expect(setExcluded(a, ['Vision/Left/Raw'], false, universe).exclude).toEqual([]); // leading slash does not matter
  });

  it('recognises prefix rules and leaves them alone when adding covered names', () => {
    const p = { exclude: [], exclude_prefixes: ['/RealOutputs/Vision'] };
    expect(isExcluded('/RealOutputs/Vision/Left/Poses', p)).toBe(true);
    expect(isExcluded('/RealOutputs/VisionX', p)).toBe(false); // '/' boundary
    expect(isExcluded('/RealOutputs/Logger/Loop', p)).toBe(false);
    expect(setExcluded(p, ['/RealOutputs/Vision/Left/Poses'], true, universe)).toEqual(p);
    expect(countExcluded(universe, p)).toBe(2);
  });

  it('turning one entry back on splits the prefix rule into the entries it still covers', () => {
    const p = { exclude: [], exclude_prefixes: ['/RealOutputs/Vision'] };
    const q = setExcluded(p, ['/RealOutputs/Vision/Left/Poses'], false, universe);
    expect(q.exclude_prefixes).toEqual([]);
    expect(q.exclude).toEqual(['/RealOutputs/Vision/Right/Poses']);
    expect(isExcluded('/RealOutputs/Vision/Left/Poses', q)).toBe(false);
    expect(isExcluded('/RealOutputs/Vision/Right/Poses', q)).toBe(true);
  });

  it('clears and counts rules', () => {
    expect(totalRules(clearExcluded())).toBe(0);
    expect(totalRules({ exclude: ['/a'], exclude_prefixes: ['/b'] })).toBe(2);
  });
});
