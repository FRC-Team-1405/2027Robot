"""Regenerates tests/golden/legacy_fingerprints.json from the ORIGINAL vision_analyzer code.

Run once, before the parser moved into wpilog_utils (see docs/wpilog-janitor-plan.md, M0). The
JSON it wrote is what test_characterization.py holds wpilog_utils to. Re-running it now goes
through the vision_analyzer shim, i.e. through wpilog_utils, so it can no longer catch drift --
it is kept only so the fingerprint format is documented and reproducible.
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]          # tools/
sys.path.insert(0, str(ROOT / 'vision-analyzer'))
from vision_analyzer.parser import parse_wpilog, trim_wpilog_bytes, _parse_wpilog_bytes  # noqa: E402
from vision_analyzer import metrics as m                                                    # noqa: E402

NOTES = ROOT.parent / 'notes' / '6-20'
NAMES = ['akit_26-06-20_14-22-29_cameraConfigChange.wpilog', 'akit_26-06-20_13-33-46_baseline.wpilog']


def sha(obj) -> str:
    return hashlib.sha256(repr(obj).encode()).hexdigest()


def fingerprint(name: str) -> dict:
    raw = (NOTES / name).read_bytes()
    sigs = _parse_wpilog_bytes(raw)
    t0 = min(s[0][0] for s in sigs.values() if s)
    t1 = max(s[-1][0] for s in sigs.values() if s)
    lo, hi = t0 + 5.0, t0 + 20.0
    trimmed = trim_wpilog_bytes(raw, lo, hi)
    return {
        'file_bytes': len(raw),
        'n_signals': len(sigs),
        'signals': {k: [len(v), sha(v)] for k, v in sorted(sigs.items())},
        't0': t0, 't1': t1,
        'mode_spans': [list(s) for s in m._compute_mode_spans(sigs, t0, t1)],
        'filtered_sha': sha(m._filter_signals_by_time(sigs, lo, hi)),
        'trim_window': [lo, hi],
        'trim_len': len(trimmed),
        'trim_sha256': hashlib.sha256(trimmed).hexdigest(),
    }


if __name__ == '__main__':
    out = {n: fingerprint(n) for n in NAMES}
    dest = pathlib.Path(__file__).with_name('legacy_fingerprints.json')
    dest.write_text(json.dumps(out, indent=1, sort_keys=True))
    print('wrote', dest, {n: (v['n_signals'], v['trim_len']) for n, v in out.items()})
