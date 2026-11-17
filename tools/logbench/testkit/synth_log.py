"""A small, match-shaped AdvantageKit .wpilog written from scratch.

It has the driver-station mode signals, a drivetrain pose and per-camera health signals, in
the key shapes `server/specs/camera_health.py` reads, so the dashboard has something to chart
without a 27 MB real log. The values are made up (a slow lap of the field; health scores that
wobble); only the timeline shape matters.
"""
import math
import struct
from typing import List, Sequence, Tuple

MAGIC = b'WPILOG'

# (mode, seconds). The default has the proportions of a real qualification match log: a long
# disabled lead-in, a short auto, a pause, teleop, then a disabled tail.
DEFAULT_SPANS: List[Tuple[str, float]] = [
    ('disabled', 315.0), ('auto', 10.0), ('disabled', 12.0), ('teleop', 140.0), ('disabled', 77.0),
]

HEALTH_FACTORS = ('StillnessPercent', 'AreaPercent', 'AmbiguityPercent', 'FpsPercent', 'JitterPercent',
                  'AcceptanceRateFactorPercent', 'LatencyPercent', 'MultiTagRatioPercent')


def _le(n: int, width: int) -> bytes:
    return n.to_bytes(width, 'little')


def _min_width(n: int) -> int:
    return max(1, (n.bit_length() + 7) // 8)


def _record(entry_id: int, ts_us: int, payload: bytes) -> bytes:
    e, s, t = _min_width(entry_id), _min_width(len(payload)), _min_width(ts_us)
    return (bytes([(e - 1) | ((s - 1) << 2) | ((t - 1) << 4)]) + _le(entry_id, e)
            + _le(len(payload), s) + _le(ts_us, t) + payload)


def _lp(s: str) -> bytes:
    b = s.encode()
    return struct.pack('<I', len(b)) + b


def _start(entry_id: int, name: str, typ: str, ts_us: int) -> bytes:
    payload = b'\x00' + struct.pack('<I', entry_id) + _lp(name) + _lp(typ) + _lp('{"source":"AdvantageKit"}')
    return _record(0, ts_us, payload)


def build_match_log(spans: Sequence[Tuple[str, float]] = DEFAULT_SPANS,
                    cameras: Sequence[str] = ('LeftCam', 'RightCam'),
                    cycle_ms: int = 100, t0_sec: float = 1.6) -> Tuple[bytes, dict]:
    """Returns (wpilog bytes, info). `info` = {'t0', 't1', 'spans': [(mode, abs_start, abs_end)],
    'cameras'} in the log's own timebase (seconds), which is also the recorder's `t_sec` domain."""
    parts: List[bytes] = [MAGIC + struct.pack('<H', 0x0100) + struct.pack('<I', 12) + b'AdvantageKit']
    ids = {}

    def entry(name: str, typ: str) -> int:
        eid = len(ids) + 1
        ids[name] = eid
        parts.append(_start(eid, name, typ, int(t0_sec * 1e6)))
        return eid

    entry('/Timestamp', 'int64')
    entry('/DriverStation/Enabled', 'boolean')
    entry('/DriverStation/Autonomous', 'boolean')
    entry('/RealOutputs/Drivetrain/Pose', 'struct:Pose2d')
    for cam in cameras:
        base = f'/RealOutputs/Vision/{cam}'
        entry(f'{base}/Health/ScorePercent', 'double')
        entry(f'{base}/Health/Reason', 'string')
        entry(f'{base}/AcceptedPoses', 'struct[]:Pose2d')
        for factor in HEALTH_FACTORS:
            entry(f'{base}/Health/{factor}', 'double')

    bounds: List[Tuple[str, float, float]] = []
    t_us = int(round(t0_sec * 1e6))
    cur_enabled = cur_auto = None
    cycle = 0
    for mode, secs in spans:
        end_us = t_us + int(round(secs * 1e6))
        bounds.append((mode, t_us / 1e6, end_us / 1e6))
        enabled, auto = mode != 'disabled', mode == 'auto'
        while t_us < end_us:
            parts.append(_record(ids['/Timestamp'], t_us, struct.pack('<q', t_us)))
            if enabled != cur_enabled:
                parts.append(_record(ids['/DriverStation/Enabled'], t_us, b'\x01' if enabled else b'\x00'))
                cur_enabled = enabled
            if auto != cur_auto:
                parts.append(_record(ids['/DriverStation/Autonomous'], t_us, b'\x01' if auto else b'\x00'))
                cur_auto = auto
            t = t_us / 1e6
            pose = struct.pack('<ddd', 2.0 + 1.5 * math.cos(t / 12.0), 4.0 + 1.5 * math.sin(t / 12.0),
                               (t / 12.0) % math.tau)
            parts.append(_record(ids['/RealOutputs/Drivetrain/Pose'], t_us, pose))
            for k, cam in enumerate(cameras):
                base = f'/RealOutputs/Vision/{cam}'
                score = 70.0 + 20.0 * math.sin(t / 7.0 + k) if enabled else 0.0
                parts.append(_record(ids[f'{base}/Health/ScorePercent'], t_us, struct.pack('<d', score)))
                parts.append(_record(ids[f'{base}/Health/Reason'], t_us, b'' if enabled else b'disabled'))
                parts.append(_record(ids[f'{base}/AcceptedPoses'], t_us, pose))
                for j, factor in enumerate(HEALTH_FACTORS):
                    value = 50.0 + 40.0 * math.sin(t / (3.0 + j) + k)
                    parts.append(_record(ids[f'{base}/Health/{factor}'], t_us, struct.pack('<d', value)))
            t_us += cycle_ms * 1000
            cycle += 1
    info = {'t0': t0_sec, 't1': t_us / 1e6, 'spans': bounds, 'cameras': list(cameras)}
    return b''.join(parts), info
