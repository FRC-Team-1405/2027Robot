"""Save every Quick (spin & drive) result to disk as it is produced, so it can be committed later.

Files go in tools/camera-calibration/results/ (git-ignored on purpose: nothing is committed until you
decide). To keep one for the docs:  git add -f tools/camera-calibration/results/<file>
Each solve writes a .json (everything, for re-analysis) and a .md (readable, for the write-up).
"""
from __future__ import annotations

import datetime
import json
import pathlib
import subprocess

import numpy as np

RESULTS_DIR = pathlib.Path(__file__).parents[1] / 'results'


def _git_sha() -> str:
    try:
        repo = pathlib.Path(__file__).parents[3]
        out = subprocess.run(['git', 'rev-parse', '--short=12', 'HEAD'], cwd=repo,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or 'unknown'
    except Exception:  # noqa: BLE001 - metadata only
        return 'unknown'


def _stamp() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


def _clean(o):
    """Make numpy values JSON-safe."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def _table(headers, rows) -> str:
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def save_result(camera: str, res, run: dict, tag_ids, current_params: dict, phases: list,
                log_name: str | None, results_dir: pathlib.Path | None = None,
                drive_check: list | None = None, standstill: dict | None = None) -> pathlib.Path:
    """Write <stamp>_<camera>_autocal.json and .md; return the .md path."""
    results_dir = results_dir or RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    stem = f'{_stamp()}_{camera}_autocal'
    new = res.params
    rows = []
    for label, key, sk, unit in (
        ('x', 'x_in', 'x_mm', 'in'), ('y', 'y_in', 'y_mm', 'in'), ('z', 'z_in', 'z_mm', 'in'),
        ('roll', 'roll_deg', 'roll_deg', 'deg'), ('pitch', 'pitch_deg', 'pitch_deg', 'deg'),
        ('yaw', 'yaw_deg', 'yaw_deg', 'deg'),
    ):
        sig = res.sigma[sk]
        rows.append([label, f'{current_params[key]:.3f}', f'{new[key]:.3f}', f'{new[key] - current_params[key]:+.3f}',
                     f'{sig / 25.4:.3f} in' if unit == 'in' else f'{sig:.2f} deg', unit])

    data = {
        'kind': 'camera-autocal',
        'saved': datetime.datetime.now().isoformat(timespec='seconds'),
        'git_sha': _git_sha(),
        'log_file': log_name,
        'camera': camera,
        'tag_ids': sorted(int(i) for i in tag_ids),
        'calibration_window_s': run['info'].get('window'),
        'samples': {'used': res.n_inliers, 'total': res.n_samples,
                    'results_in_window': run['info'].get('results_in_window'),
                    'dropped_by_tag_filter': run['info'].get('results_dropped_by_tag_filter')},
        'current_mount': current_params,
        'calibrated_mount': new,
        'sigma_1': res.sigma,
        'residual_rms': {'position_mm': res.rms_t_mm, 'rotation_deg': res.rms_r_deg},
        'clock_offset_ms': res.tau_s * 1000,
        'odometry_scale': res.odo_scale,
        'repeatability_split_half': res.split_half,
        'phases': phases,
        'drive_check': drive_check or [],
        'standstill': standstill or {},
        'warnings': list(res.warnings) + list(run.get('notes', [])),
        'java_snippet': res.java_snippet,
    }
    (results_dir / f'{stem}.json').write_text(json.dumps(_clean(data), indent=1), encoding='utf-8')

    md = [f'# Camera auto-calibration: {camera}', '',
          f'- Saved: {data["saved"]}  (repo {data["git_sha"]})',
          f'- Log: `{log_name}`, calibration window {data["calibration_window_s"]}',
          f'- Tags used: {data["tag_ids"]}',
          f'- Vision samples used: {res.n_inliers} of {res.n_samples}', '',
          '## Mount (inches / degrees)', '',
          _table(['Parameter', 'Current', 'Calibrated', 'Change', '+-1 sigma', 'Unit'], rows), '',
          f'- Position residual (RMS): {res.rms_t_mm:.1f} mm; rotation residual (RMS): {res.rms_r_deg:.2f} deg',
          f'- Vision-vs-odometry clock offset: {res.tau_s * 1000:+.0f} ms; wheel-odometry distance scale: '
          f'{res.odo_scale:.3f}']
    sh = res.split_half
    if sh:
        md.append(f'- Repeatability (two halves solved separately differ by): {sh["dx_mm"]:+.1f} / '
                  f'{sh["dy_mm"]:+.1f} / {sh["dz_mm"]:+.1f} mm and {sh["rot_deg"]:.2f} deg')
    md += ['', '## Warnings', '']
    md += [f'- {w}' for w in data['warnings']] or ['None.']
    if phases:
        md += ['', '## By phase of the routine', '',
               _table(['Phase', 'Seconds', 'Samples', 'Samples/s', 'Position err (mm, RMS)', 'Rotation err (deg, RMS)'],
                      [[p['phase'], f'{p["seconds"]:.1f}', p['samples'], f'{p["rate"]:.0f}',
                        '-' if p['rms_t_mm'] is None else f'{p["rms_t_mm"]:.1f}',
                        '-' if p['rms_r_deg'] is None else f'{p["rms_r_deg"]:.2f}'] for p in phases])]
    if drive_check:
        def f(v, fmt):
            return '-' if v is None else format(v, fmt)
        md += ['', '## Straight drives: wheels vs camera', '',
               _table(['Drive', 'Wheels say (mm)', 'Camera saw (mm)', 'Ratio camera/wheels', 'Direction vs typical drive (deg)'],
                      [[d['phase'], f(d['odo_mm'], '.0f'), f(d['vision_mm'], '.0f'), f(d['ratio'], '.3f'),
                        f(d.get('angle_dev_deg'), '.1f')] for d in drive_check])]
    if standstill:
        nz, cl = standstill.get('noise'), standstill.get('closure')
        md += ['', '## Standing still', '']
        if nz:
            md.append(f'- Vision noise at the start hold ({nz["n"]} samples): x {nz["x_mm"]:.1f}, y {nz["y_mm"]:.1f}, '
                      f'z {nz["z_mm"]:.1f} mm; rotation {nz["rot_deg"]:.2f} deg (1 sigma)')
        if cl:
            md.append(f'- Start hold vs end hold (the robot returns to its start): camera says {cl["vision_mm"]:.0f} mm '
                      f'(z {cl["vision_z_mm"]:+.0f} mm) and {cl["vision_deg"]:.2f} deg apart; wheels say {cl["wheels_mm"]:.0f} mm')
    md += ['', '## Java', '', '```java', res.java_snippet, '```', '']
    path = results_dir / f'{stem}.md'
    path.write_text('\n'.join(md), encoding='utf-8')
    return path


def save_agreement(name_a: str, name_b: str, old: dict, new: dict, log_name: str | None,
                   results_dir: pathlib.Path | None = None) -> pathlib.Path:
    results_dir = results_dir or RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    stem = f'{_stamp()}_{name_a}-vs-{name_b}_agreement'
    data = {'kind': 'camera-agreement', 'saved': datetime.datetime.now().isoformat(timespec='seconds'),
            'git_sha': _git_sha(), 'log_file': log_name, 'cameras': [name_a, name_b],
            'current_mounts': old, 'calibrated_mounts': new}
    (results_dir / f'{stem}.json').write_text(json.dumps(_clean(data), indent=1), encoding='utf-8')
    rows = [['Current mounts', old.get('n'), f'{old.get("pos_median_mm", float("nan")):.1f}',
             f'{old.get("pos_p95_mm", float("nan")):.1f}', f'{old.get("yaw_median_deg", float("nan")):.2f}'],
            ['Calibrated mounts', new.get('n'), f'{new.get("pos_median_mm", float("nan")):.1f}',
             f'{new.get("pos_p95_mm", float("nan")):.1f}', f'{new.get("yaw_median_deg", float("nan")):.2f}']]
    md = [f'# Do {name_a} and {name_b} agree?', '', f'- Log: `{log_name}`  (repo {data["git_sha"]})', '',
          _table(['Mounts', 'Pairs', 'Position median (mm)', 'Position p95 (mm)', 'Heading median (deg)'], rows), '']
    path = results_dir / f'{stem}.md'
    path.write_text('\n'.join(md), encoding='utf-8')
    return path
