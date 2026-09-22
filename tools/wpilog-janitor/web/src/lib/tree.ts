// The entry tree for the Content page: entries grouped by path, sizes rolled up. Pure, unit-tested.
import type { ContentEntry } from '../api';

export interface TreeNode {
  key: string; // '/Vision/Left' — unique, also the expand/collapse id
  label: string; // 'Left'
  depth: number;
  entry: ContentEntry | null; // set when an entry has exactly this name (a node can be both an entry and a parent)
  children: TreeNode[];
  bytes: number; // rolled up over the whole subtree
  records: number;
  leaves: ContentEntry[]; // every entry in the subtree, own included
}

export interface Row {
  node: TreeNode;
  expanded: boolean;
  hasChildren: boolean;
}

const parts = (name: string) => name.split('/').filter((p) => p !== '');

export function buildTree(entries: ContentEntry[]): TreeNode[] {
  const root: TreeNode = { key: '', label: '', depth: -1, entry: null, children: [], bytes: 0, records: 0, leaves: [] };
  const index = new Map<string, TreeNode>();
  for (const e of entries) {
    let parent = root;
    let path = '';
    const segs = parts(e.name);
    segs.forEach((seg, i) => {
      path += '/' + seg;
      let node = index.get(path);
      if (!node) {
        node = { key: path, label: seg, depth: i, entry: null, children: [], bytes: 0, records: 0, leaves: [] };
        index.set(path, node);
        parent.children.push(node);
      }
      node.bytes += e.bytes;
      node.records += e.records;
      node.leaves.push(e);
      if (i === segs.length - 1) node.entry = e;
      parent = node;
    });
  }
  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => b.bytes - a.bytes || a.label.localeCompare(b.label));
    nodes.forEach((n) => sort(n.children));
  };
  sort(root.children);
  return root.children;
}

/** Rows to draw: children of expanded nodes only. With a filter, every node containing a match is expanded and
 *  everything else is hidden (a match is any entry whose full name contains every word). */
export function flatten(nodes: TreeNode[], expanded: ReadonlySet<string>, filter: string): Row[] {
  const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (e: ContentEntry) => {
    const n = e.name.toLowerCase();
    return words.every((w) => n.includes(w));
  };
  const rows: Row[] = [];
  const visit = (node: TreeNode) => {
    if (words.length > 0 && !node.leaves.some(matches)) return;
    const hasChildren = node.children.length > 0;
    const open = words.length > 0 ? hasChildren : expanded.has(node.key);
    rows.push({ node, expanded: open && hasChildren, hasChildren });
    if (open) node.children.forEach(visit);
  };
  nodes.forEach(visit);
  return rows;
}

export function allKeys(nodes: TreeNode[]): string[] {
  const out: string[] = [];
  const visit = (n: TreeNode) => {
    if (n.children.length) out.push(n.key);
    n.children.forEach(visit);
  };
  nodes.forEach(visit);
  return out;
}

export type CheckState = 'none' | 'some' | 'all';

/** Whether none / some / all of these entries are excluded. */
export function checkState(leaves: ContentEntry[], isExcluded: (name: string) => boolean): CheckState {
  if (leaves.length === 0) return 'none';
  let n = 0;
  for (const l of leaves) if (isExcluded(l.name)) n++;
  return n === 0 ? 'none' : n === leaves.length ? 'all' : 'some';
}
