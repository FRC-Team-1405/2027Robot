#!/usr/bin/env python3
"""
Verifies that a trimmed .wpilog produces identical metrics to its original
over the trimmed window. Trim preserves original timestamps verbatim, so the
trimmed log's own start/end is exactly the boundary the trim used — filtering
both logs to that boundary and comparing should yield zero diffs.

Usage:
    python verify_trim.py original.wpilog original_trimmed.wpilog
"""
import sys

from vision_analyzer.parser import parse_wpilog
from vision_analyzer.metrics import (
    discover_cameras,
    detect_format,
    find_drivetrain_speeds,
    compute_camera_metrics,
    _filter_signals_by_time,
)

COUNT_FIELDS = [
    'total_accepted', 'total_results', 'total_rejected',
    'acceptance_rate', 'rej_velocity_pct', 'rej_boundary_pct', 'rej_ambiguity_pct',
    'fps_mean', 'conn_uptime_pct',
]


def _metrics_for(signals, t_lo, t_hi, chart_origin):
    filtered = _filter_signals_by_time(signals, t_lo, t_hi)
    cameras = discover_cameras(filtered)
    lin_key, omega_key = find_drivetrain_speeds(filtered)
    linear_sig = filtered[lin_key] if lin_key else None
    omega_sig = filtered[omega_key] if omega_key else None
    out = {}
    for cam in cameras:
        fmt = detect_format(filtered, cam)
        out[cam] = compute_camera_metrics(
            filtered, cam, fmt, t_lo, t_hi, linear_sig, omega_sig,
            chart_origin=chart_origin,
        )
    return out


def main() -> None:
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} original.wpilog trimmed.wpilog')
        sys.exit(1)

    orig_path, trim_path = sys.argv[1], sys.argv[2]
    signals_orig = parse_wpilog(orig_path)
    signals_trim = parse_wpilog(trim_path)

    ts_trim = [t for sig in signals_trim.values() for t, _ in sig]
    start_t_trim = min(ts_trim)
    end_t_trim = max(ts_trim)
    print(f'Trimmed log window (ground truth): [{start_t_trim:.6f}, {end_t_trim:.6f}] '
          f'({end_t_trim - start_t_trim:.3f} s)')

    m_orig = _metrics_for(signals_orig, start_t_trim, end_t_trim, start_t_trim)
    m_trim = _metrics_for(signals_trim, start_t_trim, end_t_trim, start_t_trim)

    cams = sorted(set(m_orig) | set(m_trim))
    if not cams:
        print('No cameras found in either log — nothing to compare.')
        sys.exit(1)

    failures = 0
    for cam in cams:
        print(f'\n=== {cam} ===')
        a, b = m_orig.get(cam), m_trim.get(cam)
        if a is None or b is None:
            print(f'  MISSING in {"trimmed" if a else "original"} log')
            failures += 1
            continue
        for field in COUNT_FIELDS:
            va, vb = a.get(field), b.get(field)
            ok = va == vb
            status = 'OK' if ok else 'MISMATCH'
            print(f'  {field:20s} orig={va!r:>12}  trim={vb!r:>12}  [{status}]')
            if not ok:
                failures += 1

        acc_ts_a, acc_ts_b = a.get('acc_ts', []), b.get('acc_ts', [])
        ts_ok = acc_ts_a == acc_ts_b
        print(f'  {"acc_ts (bit-exact)":20s} len_orig={len(acc_ts_a):>5}  '
              f'len_trim={len(acc_ts_b):>5}  [{"OK" if ts_ok else "MISMATCH"}]')
        if not ts_ok:
            failures += 1

    print(f'\n{"PASS" if failures == 0 else f"FAIL ({failures} mismatch(es))"}')
    sys.exit(0 if failures == 0 else 1)


if __name__ == '__main__':
    main()
