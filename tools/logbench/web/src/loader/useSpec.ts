// Where the spec comes from. Three delivery targets, one loading rule.
//
//   1. Standalone export: server/export.py inlines `window.__MATCH_SPEC__` ahead of the
//      bundle. No network at all -- which is the point, since a competition venue's wifi
//      cannot be relied on.
//   2. Server app: fetch from FastAPI, chosen by ?log=... in the query string.
//   3. Dev: falls back to the checked-in fixture in public/.
//
// Because the app just asks for "a spec", the same build serves all three.

import { useEffect, useState } from 'react';

import { decodeSpec } from '../player/decode';
import type { Spec, WireSpec } from '../player/types';

declare global {
  interface Window {
    __MATCH_SPEC__?: WireSpec;
  }
}

export type SpecState =
  | { status: 'loading' }
  | { status: 'ready'; spec: Spec }
  | { status: 'picker' }
  | { status: 'error'; message: string };

export function useSpec(): SpecState {
  const [state, setState] = useState<SpecState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;

    // Inlined by the standalone export -- decode synchronously, never touch the network.
    if (window.__MATCH_SPEC__) {
      try {
        setState({ status: 'ready', spec: decodeSpec(window.__MATCH_SPEC__) });
      } catch (err) {
        setState({ status: 'error', message: String(err) });
      }
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const log = params.get('log');
    const specName = params.get('spec');

    // No log chosen: in dev, fall through to the checked-in fixture so `npm run dev`
    // needs no server; in a real build, ask the user which log they want.
    if (!log) {
      if (import.meta.env.DEV) {
        fetch('/sample-spec.json')
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error('no dev fixture'))))
          .then((wire: WireSpec) => {
            if (!cancelled) setState({ status: 'ready', spec: decodeSpec(wire) });
          })
          .catch(() => {
            if (!cancelled) setState({ status: 'picker' });
          });
      } else {
        setState({ status: 'picker' });
      }
      return () => {
        cancelled = true;
      };
    }

    const url = `/api/spec?log=${encodeURIComponent(log)}${specName ? `&spec=${encodeURIComponent(specName)}` : ''}`;

    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
        return res.json() as Promise<WireSpec>;
      })
      .then((wire) => {
        if (!cancelled) setState({ status: 'ready', spec: decodeSpec(wire) });
      })
      .catch((err) => {
        if (!cancelled) setState({ status: 'error', message: String(err) });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
