"""Metrics for the camera-setting crossover experiment (see README.md).

Run from the repo root, after the runs (python -m exprunner run runs.toml, from tools/exprunner):
    python docs/experiments/vision/2026-11-14-pv-crossover-odometry/analyze.py

It reads the experiment runner's manifest.json (which log belongs to which run, the robot-time window the
robot was enabled, which setting each camera was on) and runs.toml (what each setting means). For every run
it reads, from the log itself (never from notes): each camera's PhotonVision settings (camera mode,
decimate, threads, exposure, gain), the git SHA and feature switches, and checks them against what the
run asked for. Then, from each camera's RAW per-camera robot-pose estimates
(logged before any filtering, so the robot's filter and trust settings do not matter), it computes:

  * results/s, the longest gap, the share of the run in gaps longer than 50 ms
  * PhotonVision's processing latency per result
  * jitter: how far each estimate wanders from a smooth curve through its neighbours (a quadratic over
    +-0.12 s, leave-one-out). It needs no ground truth and works while the robot moves.
  * noise_per_sqrt_s: jitter divided by sqrt(results/s): the noise left after one second of averaging,
    which is how more precise results and fewer results are weighed against each other
  * Left-minus-Right: the mean difference (bias) and scatter between the two cameras' estimates.

Then it compares setting B with setting A on the same camera across the crossover runs.
Writes results.json next to this file.
"""
import argparse
import bisect
import json as _json
import json
import math
import statistics
import sys
import tomllib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "wpilog-utils"))
from wpilog_utils.decode import parse_wpilog  # noqa: E402
from wpilog_utils.modes import compute_mode_spans  # noqa: E402

LOGS = REPO / "logs" / "offseason"
WINDOW_S = 0.12          # half-width of the local quadratic used for jitter
MIN_POINTS = 8           # points needed in a window to score a sample
GAP_S = 0.05             # a gap longer than this counts as a dropout


# --------------------------------------------------------------------------- reading a log

def find(sig, key):
    for prefix in ("RealOutputs/", ""):
        if prefix + key in sig:
            return sig[prefix + key]
    low = key.lower()
    for k, v in sig.items():
        kl = k.lower()
        if kl == low or kl == "realoutputs/" + low:
            return v
    return None


def last(sig, key):
    s = find(sig, key)
    return s[-1][1] if s else None


def auto_window(sig):
    """(t0, t1) of the longest autonomous span, in the log's own time."""
    start = min(s[0][0] for s in sig.values() if s)
    end = max(s[-1][0] for s in sig.values() if s)
    spans = [(a + start, b + start) for a, b, m in compute_mode_spans(sig, start, end) if m == "auto"]
    if not spans:
        return None
    return max(spans, key=lambda s: s[1] - s[0])


def pv_settings(sig, pi, cam):
    """The camera's PhotonVision settings as the Pi publisher logged them, with the runner's names."""
    b = f"OrangePi/{pi}/"
    return {
        "camera_mode": last(sig, b + "Video/video0/Mode"),
        "decimate": last(sig, b + f"PhotonVision/{cam}/Decimate"),
        "threads": last(sig, b + f"PhotonVision/{cam}/Threads"),
        "exposure": last(sig, b + f"PhotonVision/{cam}/Exposure"),
        "gain": last(sig, b + f"PhotonVision/{cam}/Gain"),
        "multitag": last(sig, b + f"PhotonVision/{cam}/MultiTag"),
        "low_latency": last(sig, b + f"PhotonVision/{cam}/LowLatencyMode"),
        "pipeline": last(sig, b + f"PhotonVision/{cam}/PipelineName"),
    }


def matches(want, got):
    if got is None:
        return False
    if isinstance(want, bool) or isinstance(got, bool):
        return bool(want) == bool(got)
    if isinstance(want, (int, float)):
        try:
            return abs(float(want) - float(got)) < 1e-6 * max(1.0, abs(float(want)))
        except (TypeError, ValueError):
            return False
    return str(want).split(" ")[0] == str(got).split(" ")[0] and str(want).split("@")[-1].strip() == str(got).split("@")[-1].strip()


def camera_series(sig, cam, window):
    """Flatten one camera's raw per-result estimates inside the window."""
    poses = find(sig, f"Vision/{cam}/rawEstimatedPoses") or []
    stamps = dict(find(sig, f"Vision/{cam}/rawTimestampsSec") or [])
    lats = find(sig, f"Vision/{cam}/PipelineLatenciesMs") or []
    counts = dict(find(sig, f"Vision/{cam}/rawTagCountsPerResult") or [])
    dists = dict(find(sig, f"Vision/{cam}/rawAvgDistancesMeters") or [])
    t, x, y, yaw, z, ntag, dist = [], [], [], [], [], [], []
    for rec_t, ps in poses:
        if window and not (window[0] <= rec_t <= window[1]):
            continue
        ts = stamps.get(rec_t) or []
        cs = counts.get(rec_t) or []
        ds = dists.get(rec_t) or []
        for j, p in enumerate(ps):
            if j >= len(ts):
                continue
            t.append(float(ts[j]))
            x.append(p["x"])
            y.append(p["y"])
            z.append(p["z"])
            yaw.append(2.0 * math.atan2(p["qz"], p["qw"]))
            ntag.append(cs[j] if j < len(cs) else float("nan"))
            dist.append(ds[j] if j < len(ds) else float("nan"))
    order = np.argsort(t)
    arr = lambda v: np.array(v, float)[order]  # noqa: E731
    out = {"t": arr(t), "x": arr(x), "y": arr(y), "z": arr(z), "yaw": np.unwrap(arr(yaw)),
           "ntag": arr(ntag), "dist": arr(dist)}
    out["latency_ms"] = [v for rec_t, vs in lats if (not window or window[0] <= rec_t <= window[1]) for v in vs]
    return out


# --------------------------------------------------------------------------- metrics

def local_jitter(t, v):
    """Leave-one-out residual of a local quadratic (+-WINDOW_S). Returns residuals (NaN where not scored)."""
    n = len(t)
    res = np.full(n, np.nan)
    for i in range(n):
        lo = bisect.bisect_left(t, t[i] - WINDOW_S)
        hi = bisect.bisect_right(t, t[i] + WINDOW_S)
        idx = [k for k in range(lo, hi) if k != i]
        if len(idx) < MIN_POINTS:
            continue
        tt = t[idx] - t[i]
        A = np.vander(tt, 3)                      # [t^2, t, 1]
        coef, *_ = np.linalg.lstsq(A, v[idx], rcond=None)
        pred = coef[2]                            # value at t[i] (tt = 0)
        # leave-one-out prediction variance is sigma^2 * (1 + h), h = leverage of the prediction point
        h = float(np.linalg.inv(A.T @ A)[2, 2])
        res[i] = (v[i] - pred) / math.sqrt(1.0 + h)
    return res


def camera_metrics(s, window):
    t = s["t"]
    out = {"n": int(len(t))}
    if len(t) < 5 or not window:
        return out
    dur = window[1] - window[0]
    iv = np.diff(t)
    gaps = iv[iv > GAP_S]
    out.update({
        "results_per_s": len(t) / dur,
        "median_interval_ms": float(np.median(iv) * 1000),
        "max_gap_ms": float(iv.max() * 1000),
        "gap_share_pct": float(gaps.sum() / dur * 100),
        "dropouts": int(len(gaps)),
        "latency_ms_mean": float(np.mean(s["latency_ms"])) if s["latency_ms"] else None,
        "tags_mean": float(np.nanmean(s["ntag"])) if np.isfinite(s["ntag"]).any() else None,
        "distance_m_mean": float(np.nanmean(s["dist"])) if np.isfinite(s["dist"]).any() else None,
    })
    rx, ry, ryaw = local_jitter(t, s["x"]), local_jitter(t, s["y"]), local_jitter(t, s["yaw"])
    m = np.isfinite(rx) & np.isfinite(ry)
    if m.sum() >= 10:
        out["jitter_xy_mm"] = float(np.sqrt(np.mean(rx[m] ** 2 + ry[m] ** 2)) * 1000)
        out["jitter_yaw_deg"] = float(np.degrees(np.sqrt(np.mean(ryaw[m] ** 2))))
        out["jitter_scored"] = int(m.sum())
        # Averaging N independent results per second cuts noise by sqrt(N), so this is the noise left after one
        # second of averaging. It is the number that says whether more precise results are worth fewer of them.
        # Frame-to-frame errors that are NOT independent (a bias that depends on where the robot is) do not average.
        out["noise_per_sqrt_s_mm"] = out["jitter_xy_mm"] / math.sqrt(out["results_per_s"])
    return out


def left_minus_right(a, b, max_dt=0.006):
    """Mean and scatter of the Left-minus-Right pose difference at matched capture times."""
    ta, tb = a["t"], b["t"]
    if len(ta) < 5 or len(tb) < 5:
        return {}
    j = np.clip(np.searchsorted(tb, ta), 1, len(tb) - 1)
    j = np.where(np.abs(tb[j - 1] - ta) < np.abs(tb[j] - ta), j - 1, j)
    ok = np.abs(tb[j] - ta) <= max_dt
    if ok.sum() < 20:
        return {"pairs": int(ok.sum())}
    dx = a["x"][ok] - b["x"][j[ok]]
    dy = a["y"][ok] - b["y"][j[ok]]
    dyaw = np.degrees(np.angle(np.exp(1j * (a["yaw"][ok] - b["yaw"][j[ok]]))))
    return {"pairs": int(ok.sum()), "bias_xy_mm": float(np.hypot(dx.mean(), dy.mean()) * 1000),
            "scatter_xy_mm": float(np.sqrt(dx.var() + dy.var()) * 1000),
            "bias_yaw_deg": float(dyaw.mean()), "scatter_yaw_deg": float(dyaw.std())}


# --------------------------------------------------------------------------- a run

def find_log(name):
    stem = Path(name).name
    if not stem.endswith(".wpilog"):
        stem += ".wpilog"
    hits = sorted(LOGS.glob(f"**/{stem}")) or sorted((REPO / "logs").glob(f"**/{stem}"))
    if not hits:
        raise FileNotFoundError(f"{stem} (looked under logs/)")
    return hits[0]


def analyze_run(run_id, entry, plan):
    """One run from the runner's manifest entry. `plan` is the parsed runs.toml."""
    path = find_log(entry["log"]["name"])
    sig = parse_wpilog(str(path))
    win = entry.get("enable_window") or {}
    window = (win["t_enable"], win["t_disable"]) if win.get("t_enable") and win.get("t_disable") else None
    source = "enable window from the runner"
    if window is None:
        window = auto_window(sig)
        source = "longest autonomous span in the log"
    cams = {}
    for pi, cam in (c.split("/") for c in plan["cameras"]):
        side = "left" if "left" in cam.lower() else "right" if "right" in cam.lower() else cam
        cams[side] = (pi, cam)
    res = {"id": run_id, "log": path.name, "window_s": None if not window else window[1] - window[0],
           "window_source": source, "git_sha": last(sig, "RealMetadata/GitSHA"),
           "git_dirty": last(sig, "RealMetadata/GitDirty"),
           "feature_switches": last(sig, "RealMetadata/FeatureSwitches"), "cameras": {}, "problems": []}
    series = {}
    for side, (pi, cam) in cams.items():
        name = entry["use"][cam]
        want = {**plan.get("defaults", {}), **plan["settings"][name]}
        got = pv_settings(sig, pi, cam)
        for k, v in want.items():
            if not matches(v, got.get(k)):
                res["problems"].append(f"{side} ({cam}) {k}: asked for {v}, the log says {got.get(k)}")
        s_ = camera_series(sig, cam, window)
        series[side] = s_
        res["cameras"][side] = {"camera": cam, "setting": name, "log_settings": got, **camera_metrics(s_, window)}
    res["left_minus_right"] = left_minus_right(series["left"], series["right"]) if len(series) == 2 else {}
    if entry.get("drifted_during_run"):
        res["problems"].append(f"settings changed during the run: {entry['drifted_during_run']}")
    if window is None:
        res["problems"].append("no enable window and no autonomous span found in the log")
    return res


# --------------------------------------------------------------------------- comparing settings

def summarize(results, cfg):
    """B vs A on the same camera, averaged over the runs where each camera had each setting."""
    out = {}
    keys = ("results_per_s", "latency_ms_mean", "jitter_xy_mm", "jitter_yaw_deg", "noise_per_sqrt_s_mm", "max_gap_ms",
            "gap_share_pct")
    for side in ("left", "right"):
        by = {"A": [], "B": []}
        for r in results:
            c = r["cameras"][side]
            if c.get("setting") in by and "jitter_xy_mm" in c and not r["problems"]:
                by[c["setting"]].append(c)
        row = {}
        for k in keys:
            a = [c[k] for c in by["A"] if c.get(k) is not None]
            b = [c[k] for c in by["B"] if c.get(k) is not None]
            if a and b:
                ma, mb = statistics.mean(a), statistics.mean(b)
                row[k] = {"A": ma, "B": mb, "change_pct": (mb - ma) / ma * 100 if ma else None,
                          "n_A": len(a), "n_B": len(b)}
        out[side] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(HERE / "runs.toml"))
    ap.add_argument("--manifest", default=None, help="default: manifest.json next to the plan")
    args = ap.parse_args()
    plan_path = Path(args.plan)
    plan = tomllib.loads(plan_path.read_text(encoding="utf-8"))
    manifest = Path(args.manifest) if args.manifest else plan_path.parent / "manifest.json"
    if not manifest.exists():
        sys.exit(f"{manifest} not found: run the experiment first (python -m exprunner run runs.toml, "
                 "from tools/exprunner)")
    runs = _json.loads(manifest.read_text(encoding="utf-8"))["runs"]
    results = []
    for r in plan["runs"]:
        entry = (runs.get(r["id"]) or {}).get("robot")
        if not entry or entry.get("status") != "ok" or not (entry.get("log") or {}).get("name"):
            print(f"{r['id']}: " + ("not run yet" if not entry else f"{entry['status']}, no usable log; skipped"))
            continue
        try:
            results.append(analyze_run(r["id"], entry, plan))
        except FileNotFoundError as e:
            print(f"{r['id']}: log not found ({e}); skipped")
    print("\nPer run (jitter = scatter around a smooth curve; smaller is better)")
    print(f"{'run':<7}{'cam':<6}{'set':<4}{'res/s':>7}{'lat ms':>8}{'jit xy mm':>10}{'jit yaw°':>9}{'max gap ms':>11}{'gap %':>7}"
          f"{'tags':>6}{'dist m':>7}")
    for r in results:
        for side in ("left", "right"):
            c = r["cameras"][side]
            f = lambda k, fmt: format(c[k], fmt) if c.get(k) is not None else "-"  # noqa: E731
            print(f"{r['id']:<7}{side:<6}{c['setting']:<4}{f('results_per_s', '7.1f')}{f('latency_ms_mean', '8.1f')}"
                  f"{f('jitter_xy_mm', '10.1f')}{f('jitter_yaw_deg', '9.2f')}{f('max_gap_ms', '11.0f')}"
                  f"{f('gap_share_pct', '7.1f')}{f('tags_mean', '6.2f')}{f('distance_m_mean', '7.2f')}")
        lr = r["left_minus_right"]
        if lr.get("bias_xy_mm") is not None:
            print(f"{'':<7}L-R: bias {lr['bias_xy_mm']:.1f} mm / {lr['bias_yaw_deg']:+.2f}°, scatter {lr['scatter_xy_mm']:.1f} mm "
                  f"/ {lr['scatter_yaw_deg']:.2f}° over {lr['pairs']} pairs")
        for p in r["problems"]:
            print(f"{'':<7}!! {p}")
    summ = summarize(results, plan)
    print("\nSetting B vs A, same camera (needs crossover runs; runs with problems are excluded)")
    for side, row in summ.items():
        for k, v in row.items():
            ch = "-" if v["change_pct"] is None else f"{v['change_pct']:+.0f}%"
            print(f"  {side:<6}{k:<22}A {v['A']:8.2f} (n={v['n_A']})  B {v['B']:8.2f} (n={v['n_B']})  change {ch}")
    out = {"plan": str(plan_path), "manifest": str(manifest), "runs": results, "summary": summ}
    (HERE / "results.json").write_text(_json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(f"\nwrote {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
