"""Metrics for the 2026-10-27 PhotonVision throughput experiment (see README.md).

Run from the repo root:  python docs/experiments/vision/2026-10-27-pv-throughput/analyze.py
Reads the WPILog Janitor-trimmed logs in logs/offseason/10-27/ (enabled time only) and writes
results.json next to this file. Window = every enabled span longer than 5 s.

Dropped frames: gaps in Vision/<cam>/RawTimestampsSec longer than 1.6x the median interval.
RawTimestampsSec only has frames where a pose was estimated, so a gap is either a frame PhotonVision
skipped or a frame with no tag. In the circle auto a tag is always in view; in the driven heat
soak it isn't, so the soak slices only count gaps under 50 ms.
"""
import sys, math, statistics as st, json, os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "wpilog-utils"))
from wpilog_utils.decode import parse_wpilog

LOG_DIR = REPO / "logs" / "offseason" / "10-27"
RUNS = [
    ("T1", "800x600 @100 fps, decimate 3 (baseline)", "akit_26-10-27_22-13-27"),
    ("T2", "800x600 @100 fps, decimate 2", "akit_26-10-27_22-37-33"),
    ("T3", "800x600 @100 fps, decimate 1", "akit_26-10-27_22-42-57"),
    ("T4", "1280x800, decimate 3", "akit_26-10-27_23-07-45"),
    ("T5", "1280x800, decimate 2", "akit_26-10-27_23-21-27"),
    ("T5.1", "800x600 @120 fps, decimate 3", "akit_26-10-27_23-27-43"),
    ("T6", "800x600 @120 fps, decimate 3, recorder stopped", "akit_26-10-27_23-37-01"),
    ("T7", "800x600 @120 fps, decimate 3, heat soak (driven)", "akit_26-10-27_23-42-41"),
]


def pct(xs, p):
    if not xs:
        return float('nan')
    xs = sorted(xs); k = (len(xs) - 1) * p / 100; f = math.floor(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def spans(sig):
    en = sig.get("DriverStation/Enabled", [])
    out = []; s0 = None
    for t, v in en:
        if v and s0 is None:
            s0 = t
        elif not v and s0 is not None:
            out.append((s0, t)); s0 = None
    if s0 is not None:
        end = max(s[-1][0] for s in sig.values() if s)
        out.append((s0, end))
    return out


def inspan(t, sp):
    return any(a <= t <= b for a, b in sp)


def win(series, sp):
    return [(t, v) for t, v in series if inspan(t, sp)]


def yaw(p):
    qw, qx, qy, qz = p.get('qw', 1), p.get('qx', 0), p.get('qy', 0), p.get('qz', 0)
    return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def cam_stats(sig, cam, sp, dur):
    c = {}
    ts = []
    for t, v in win(sig.get(f"Vision/{cam}/RawTimestampsSec", []), sp):
        ts += list(v)
    ts = sorted(set(ts))
    seq = []
    for t, v in win(sig.get(f"Vision/{cam}/SequenceIds", []), sp):
        seq += list(v)
    seq = sorted(set(seq))
    c["results"] = len(ts)
    c["results_per_s"] = round(len(ts) / dur, 1) if dur else None
    d = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
    if d:
        med = st.median(d)
        nondrop = [x for x in d if x < 1.6 * med]
        p_mean = st.mean(nondrop)
        c["frame_ms_median"] = round(med, 2)
        c["nominal_fps"] = round(1000 / p_mean, 1)
        drops = [x for x in d if x >= 1.6 * med]
        missing = sum(max(1, round(x / p_mean) - 1) for x in drops)
        c["dropped_frames"] = missing
        c["drop_events"] = len(drops)
        c["dropped_pct"] = round(100 * missing / (len(ts) + missing), 2)
        c["gaps_ge_50ms"] = sum(1 for x in d if x >= 50)
        c["max_gap_ms"] = round(max(d), 1)
    if seq:
        c["seq_missing"] = (seq[-1] - seq[0] + 1) - len(seq)
    mr = win(sig.get(f"RealOutputs/Vision/{cam}/MissedResults", []), sp)
    c["MissedResults_max"] = max([v for t, v in mr], default=None)
    lat = []
    for t, v in win(sig.get(f"Vision/{cam}/PipelineLatenciesMs", []), sp):
        lat += list(v)
    if lat:
        c["pv_ms_med"] = round(st.median(lat), 2); c["pv_ms_p95"] = round(pct(lat, 95), 2); c["pv_ms_max"] = round(max(lat), 2)
    tl = [v for t, v in win(sig.get(f"RealOutputs/Vision/{cam}/LatencyMsLatest", []), sp)]
    if tl:
        c["total_lat_med"] = round(st.median(tl), 1); c["total_lat_p95"] = round(pct(tl, 95), 1)
    fps = [v for t, v in win(sig.get(f"Vision/{cam}/CurrentFps", []), sp)]
    if fps:
        c["CurrentFps_med"] = round(st.median(fps), 1); c["CurrentFps_min"] = round(min(fps), 1)
    dist = []
    for t, v in win(sig.get(f"Vision/{cam}/RawAvgDistancesMeters", []), sp):
        dist += list(v)
    if dist:
        c["dist_med"] = round(st.median(dist), 2); c["dist_max"] = round(max(dist), 2); c["dist_min"] = round(min(dist), 2)
    ids = set(); tc = []
    for t, v in win(sig.get(f"Vision/{cam}/RawTagIdsFlat", []), sp):
        ids |= set(v)
    for t, v in win(sig.get(f"Vision/{cam}/RawTagCountsPerResult", []), sp):
        tc += list(v)
    c["tag_ids"] = sorted(ids)
    if tc:
        c["tags_per_result_mean"] = round(st.mean(tc), 2)
    ar = []
    for t, v in win(sig.get(f"Vision/{cam}/RawSumTagAreas", []), sp):
        ar += list(v)
    if ar:
        c["area_med"] = round(st.median(ar), 3)
    xs = []; ys = []; hs = []
    for t, v in win(sig.get(f"Vision/{cam}/RawEstimatedPoses", []), sp):
        for p in v:
            xs.append(p['x']); ys.append(p['y']); hs.append(math.degrees(yaw(p)))
    if len(xs) > 2:
        h0 = hs[0]; hs = [((h - h0 + 180) % 360) - 180 for h in hs]
        c["x_std_cm"] = round(100 * st.pstdev(xs), 3); c["y_std_cm"] = round(100 * st.pstdev(ys), 3)
        c["x_p2p_cm"] = round(100 * (pct(xs, 99) - pct(xs, 1)), 2)
        c["h_std_deg"] = round(st.pstdev(hs), 3); c["h_p2p_deg"] = round(pct(hs, 99) - pct(hs, 1), 3)
        c["pose_mean"] = (round(st.mean(xs), 3), round(st.mean(ys), 3), round(h0 + st.mean(hs), 2))
    acc = [v for t, v in win(sig.get(f"RealOutputs/Vision/{cam}/AcceptanceRatePercent", []), sp)]
    if acc:
        c["accept_med"] = round(st.median(acc), 1)
    hp = [v for t, v in win(sig.get(f"RealOutputs/Vision/{cam}/Health/ScorePercent", []), sp)]
    if hp:
        c["health_med"] = round(st.median(hp), 1)
    return c


def pi_stats(sig, pi, cam, sp):
    p = {}; base = f"RealOutputs/OrangePi/{pi}/"

    def vals(k):
        return [v for t, v in win(sig.get(base + k, []), sp)]

    def allv(k):
        return sig.get(base + k, [])

    for k in ("CpuCoreMaxPct", "CPU_Pct", "PvCpuPct", "PublisherCpuPct"):
        v = vals(k)
        if v:
            p[k] = (round(st.median(v), 1), round(max(v), 1))
    cores = vals("CpuCorePct")
    if cores:
        n = len(cores[0])
        p["core_med"] = [round(st.median([c[i] for c in cores if len(c) == n])) for i in range(n)]
    for k in ("CpuFreqMHz", "CpuFreqCapMHz", "CpuFreqMaxMHz"):
        inv = vals(k)
        before = [x for t, x in allv(k) if t <= sp[-1][1]]
        seq_ = inv or before[-1:]
        if seq_:
            p[k] = [min(x[i] for x in seq_) for i in range(len(seq_[0]))]
    th = [x for t, x in allv("CpuThrottled") if t <= sp[-1][1]]
    p["throttled_any"] = any(vals("CpuThrottled")) or (bool(th[-1]) if th else None)
    tm = allv("TempMaxC")
    if tm and sp:
        def at(t):
            b = [v for tt, v in tm if tt <= t]
            return b[-1] if b else tm[0][1]
        p["temp_start"] = at(sp[0][0]); p["temp_end"] = at(sp[-1][1])
        iv = vals("TempMaxC"); p["temp_max"] = max(iv) if iv else None
        p["temp_series"] = [(round(t - sp[0][0]), v) for t, v in tm if sp[0][0] - 1 <= t <= sp[-1][1]][::4]
    rb = f"Recorders/{cam}/"
    sfps = vals(rb + "StreamFps")
    if sfps:
        p["rec_streamfps_med"] = round(st.median(sfps), 1)
    p["rec_states"] = [(round(t - sp[0][0]), v) for t, v in allv(rb + "State")][-5:]
    p["rec_session_frames"] = [v for t, v in win(allv(rb + "SessionFrames"), sp)][-1:]
    p["NetSpeedMbps"] = [v for t, v in allv("NetSpeedMbps")][-1:]
    top = vals("PvTopThreadPct")
    if top:
        p["top_thread_med"] = round(st.median([x[0] for x in top if x])); p["top_thread_max"] = max(x[0] for x in top if x)
    tc = vals("PvTopThreadCore")
    if tc:
        p["top_thread_core_mode"] = st.mode([x[0] for x in tc if x])
    return p


def analyze(path):
    sig = parse_wpilog(path)
    sp = [s for s in spans(sig) if s[1] - s[0] > 5]
    R = {"file": os.path.basename(path), "spans": [(round(a, 1), round(b - a, 1)) for a, b in sp]}
    dur = sum(b - a for a, b in sp)
    R["enabled_s"] = round(dur, 1)
    for cam in ("LeftCam", "RightCam"):
        R[cam] = cam_stats(sig, cam, sp, dur)
    R["LeftPi"] = pi_stats(sig, "LeftPi", "LeftCam", sp)
    R["RightPi"] = pi_stats(sig, "RightPi", "RightCam", sp)
    rio = {}
    for k, lab in (("RealOutputs/Diagnostics/LoopMs", "loop"), ("RealOutputs/LoggedRobot/FullCycleMS", "fullcycle"),
                   ("RealOutputs/Timing/VisionMs", "visionms"), ("RealOutputs/LoggedRobot/UserCodeMS", "usercode"),
                   ("SystemStats/BatteryVoltage", "batt"), ("SystemStats/CANBus/Utilization", "can")):
        v = [x for t, x in win(sig.get(k, []), sp)]
        if v:
            rio[lab] = (round(st.median(v), 2), round(pct(v, 95), 2), round(max(v), 2))
    lv = [x for t, x in win(sig.get("RealOutputs/LoggedRobot/FullCycleMS", []), sp)]
    if lv:
        rio["cycles_over_20ms_pct"] = round(100 * sum(1 for x in lv if x > 20) / len(lv), 1)
    oc = win(sig.get("RealOutputs/Diagnostics/LoopOverrunCount", []), sp)
    if oc:
        rio["overruns_in_span"] = oc[-1][1] - oc[0][1]
    for cam in ("LeftCam", "RightCam"):
        v = [x for t, x in win(sig.get(f"RealOutputs/Timing/Vision/{cam}/ReadInputsMs", []), sp)]
        if v:
            rio[cam + "_read_ms"] = (round(st.median(v), 2), round(pct(v, 95), 2))
    vx = [abs(x) for t, x in win(sig.get("RealOutputs/Drivetrain/Speeds/vxMetersPerSecond", []), sp)]
    om = [abs(x) for t, x in win(sig.get("RealOutputs/Drivetrain/Speeds/omegaRadiansPerSecond", []), sp)]
    rio["max_vx"] = round(max(vx), 3) if vx else None; rio["max_omega"] = round(max(om), 3) if om else None
    poses = [p[0] for t, p in win(sig.get("RealOutputs/Drivetrain/Pose", []), sp) if p]
    if poses:
        rio["fused_x_std_cm"] = round(100 * st.pstdev([p['x'] for p in poses]), 3)
        rio["fused_h_std_deg"] = round(st.pstdev([math.degrees(p['rot']) for p in poses]), 3)
    for k, lab in (("RealOutputs/Vision/CrossCameraAgreement/TranslationDeltaMeters", "xcam_trans_m"),
                   ("RealOutputs/Vision/CrossCameraAgreement/RotationDeltaDegrees", "xcam_rot_deg"),
                   ("RealOutputs/Vision/CrossCameraAgreement/ScorePercent", "xcam_score"),
                   ("RealOutputs/Vision/CorrectionMagnitude", "correction_m")):
        v = [x for t, x in win(sig.get(k, []), sp)]
        if v:
            rio[lab] = (round(st.median(v), 4), round(pct(v, 95), 4), round(max(v), 4))
    ph = sig.get("RealOutputs/CircleFacingTag/Phase", [])
    rio["circle_phase_times"] = [(round(t - sp[0][0], 1), x) for t, x in ph] if sp else []
    rio["circle_phases"] =[x for t, x in sig.get("RealOutputs/CircleFacingTag/Phase", [])]
    md = sig.get("RealMetadata/GitSHA", []); rio["sha"] = md[-1][1][:8] if md else None
    R["rio"] = rio
    return R


def soak_slices(path, edges=(0, 30, 60, 90, 120, 165)):
    """Per-30 s slices of a long run: results, in-view drop %, PhotonVision's own fps."""
    sig = parse_wpilog(path)
    sp = [s for s in spans(sig) if s[1] - s[0] > 5]
    a0 = sp[0][0]; out = {}
    for cam in ("LeftCam", "RightCam"):
        ts = []
        for t, v in win(sig.get(f"Vision/{cam}/RawTimestampsSec", []), sp):
            ts += list(v)
        ts = sorted(set(ts))
        fps = sig.get(f"Vision/{cam}/CurrentFps", [])
        rows = []
        for lo, hi in zip(edges, edges[1:]):
            sl = [x for x in ts if a0 + lo <= x < a0 + hi]
            short = [(b - a) * 1000 for a, b in zip(sl, sl[1:]) if (b - a) * 1000 < 50]
            per = st.median(short) if short else 1
            nondrop = [x for x in short if x < 1.6 * per]
            p_mean = st.mean(nondrop) if nondrop else per
            miss = sum(max(1, round(x / p_mean) - 1) for x in short if x >= 1.6 * per)
            f = [v for t, v in fps if a0 + lo <= t < a0 + hi]
            rows.append({"from_s": lo, "to_s": hi, "results": len(sl),
                         "in_view_drop_pct": round(100 * miss / (len(short) + miss), 2) if short else None,
                         "CurrentFps_med": round(st.median(f), 1) if f else None})
        out[cam] = rows
    return out


if __name__ == "__main__":
    out = []
    for run_id, setting, stem in RUNS:
        path = LOG_DIR / f"{stem}-bundle" / f"{stem}.trimmed.wpilog"
        r = analyze(str(path)); r["id"] = run_id; r["setting"] = setting
        if run_id == "T7":
            r["soak_slices"] = soak_slices(str(path))
        out.append(r)
        c = (r["LeftCam"], r["RightCam"])
        print(f"{run_id:5s} {setting:48s} results/s {c[0]['results_per_s']:6.1f} / {c[1]['results_per_s']:6.1f}"
              f"  drop% {c[0].get('dropped_pct')} / {c[1].get('dropped_pct')}"
              f"  PV ms {c[0].get('pv_ms_med')} / {c[1].get('pv_ms_med')}")
    json.dump(out, open(Path(__file__).with_name("results.json"), "w"), indent=1, default=str)
