#!/usr/bin/env python3
"""Fake roboRIO: an NT4 *server* that plays out a match, for testing
orangepi-vision-recorder.py without a robot.

It publishes the two topics the recorder reads:
  /FMSInfo/FMSControlData  integer HAL control word (bit 0 enabled, 1 autonomous,
                           2 test, 3 eStop, 4 fmsAttached, 5 dsAttached; a connected
                           DS is 32, an FMS-attached one adds 16)
  /RobotTime/WallClockMs   integer UTC epoch ms, ~1 Hz (the recorder uses it only to
                           label session folders; skew it with --clock-offset-sec,
                           or never publish it with --no-clock)

and walks a timeline: pre-match (disabled) -> auto -> pause (disabled) -> teleop ->
post-match (disabled), optionally repeated, optionally with a simulated comms loss
(the NT server is shut down and restarted mid-teleop).

Every phase transition is printed and, with --event-log, appended as one JSON object
per line: phase, control_word, wall_ms, server_time_sec (plus a few extras). The
server_time_sec is the NT server clock in seconds, the same domain as the recorder's
t_sec (server_time_sec() in orangepi-vision-recorder.py), so recorded frames can be
checked against the windows the robot was really enabled.

Example (laptop, then on the Pi: NT_SERVER=<laptop-ip> NT_PORT=5811 python3 orangepi-vision-recorder.py):
    python coprocessor/sim/fake_robot.py --port 5811 --fast 5 --event-log events.jsonl

Needs only pyntcore (Python 3.9+; written to run on the laptop and the Pi's venv).
"""

import argparse
import json
import sys
import time
from datetime import datetime

import ntcore

CTRL_ENABLED = 1 << 0
CTRL_AUTO = 1 << 1
CTRL_TEST = 1 << 2
CTRL_ESTOP = 1 << 3
CTRL_FMS = 1 << 4
CTRL_DS = 1 << 5

TICK_SEC = 0.02
CLOCK_PERIOD_SEC = 1.0

FMS_CONTROL_TOPIC = "/FMSInfo/FMSControlData"
WALL_CLOCK_TOPIC = "/RobotTime/WallClockMs"


def server_time_sec():
    """NT server clock in seconds. On the server instance this is just the local
    ntcore time; the recorder computes the same domain as (now + offset)."""
    return ntcore._now() / 1_000_000.0


class FakeRobot:
    def __init__(self, args):
        self.args = args
        self.start_mono = time.monotonic()
        self.event_file = open(args.event_log, "w", encoding="utf-8") if args.event_log else None
        self.inst = None
        self.control_pub = None
        self.clock_pub = None
        self.control_word = 0
        self.next_clock = 0.0
        self.drop_end_mono = None  # not None while the server is down
        self.phase = "init"
        self.match = 0

    # ---- server lifecycle -------------------------------------------------

    def start_server(self):
        a = self.args
        if self.inst is None:
            self.inst = ntcore.NetworkTableInstance.create()
        # port3 (NT3) is disabled with 0; only NT4 is needed. Empty persist file = no persistence.
        self.inst.startServer("", a.listen, 0, a.port)
        if self.control_pub is None:
            self.control_pub = self.inst.getIntegerTopic(FMS_CONTROL_TOPIC).publish()
            if not a.no_clock:
                self.clock_pub = self.inst.getIntegerTopic(WALL_CLOCK_TOPIC).publish()
        # (re)assert current values so a restarted server serves them immediately
        self.control_pub.set(self.control_word)
        self.next_clock = 0.0
        self.tick()

    def stop_server(self):
        self.inst.stopServer()

    # ---- output -----------------------------------------------------------

    def wall_ms(self):
        return int(time.time() * 1000)

    def robot_wall_ms(self):
        return self.wall_ms() + int(self.args.clock_offset_sec * 1000)

    def event(self, kind, **extra):
        mono = time.monotonic() - self.start_mono
        wall = self.wall_ms()
        rec = {
            "phase": kind,
            "control_word": self.control_word,
            "wall_ms": wall,
            "server_time_sec": server_time_sec(),
            "mono_sec": round(mono, 3),
            "match": self.match,
        }
        rec.update(extra)
        stamp = datetime.fromtimestamp(wall / 1000.0).strftime("%H:%M:%S.%f")[:-3]
        print(f"[{stamp} wall | +{mono:8.3f}s mono] {kind:<12} control_word={self.control_word:<3} "
              f"match={self.match} server_t={rec['server_time_sec']:.3f}", flush=True)
        if self.event_file:
            self.event_file.write(json.dumps(rec) + "\n")
            self.event_file.flush()

    # ---- timeline ---------------------------------------------------------

    def tick(self):
        """Housekeeping that must keep happening while we wait: clock topic, server restart."""
        now = time.monotonic()
        if self.drop_end_mono is not None and now >= self.drop_end_mono:
            self.drop_end_mono = None
            self.start_server_after_drop()
        if self.drop_end_mono is None and self.clock_pub is not None and now >= self.next_clock:
            self.clock_pub.set(self.robot_wall_ms())
            self.next_clock = now + CLOCK_PERIOD_SEC

    def start_server_after_drop(self):
        self.start_server()
        self.event("drop_end")

    def set_word(self, word):
        self.control_word = word
        self.control_pub.set(word)  # queued locally if the server is down; re-asserted on restart

    def wait_until(self, deadline_mono, drop_at_mono=None):
        """Sleep until deadline, ticking. Fires the comms-loss drop at drop_at_mono if given."""
        dropped = drop_at_mono is None
        while True:
            now = time.monotonic()
            if not dropped and now >= drop_at_mono:
                dropped = True
                self.event("drop_start", drop_for_sec=self.args.drop_for_sec)
                self.stop_server()
                self.drop_end_mono = now + self.args.drop_for_sec
            self.tick()
            if now >= deadline_mono:
                return
            nxt = deadline_mono if dropped else min(deadline_mono, drop_at_mono)
            time.sleep(max(0.0, min(TICK_SEC, nxt - now)))

    def run_phase(self, name, duration, word, drop_after=None):
        self.phase = name
        self.set_word(word)
        self.event(name)
        start = time.monotonic()
        drop_at = start + drop_after if drop_after is not None and drop_after < duration else None
        if drop_after is not None and drop_at is None:
            print(f"WARNING: --drop-at-sec {drop_after} is beyond this {name} phase ({duration:.2f}s); no drop", flush=True)
        self.wait_until(start + duration, drop_at)

    def wait_for_clients(self):
        a = self.args
        deadline = time.monotonic() + a.wait_timeout_sec
        print(f"Waiting for {a.wait_for_clients} NT client(s) (up to {a.wait_timeout_sec:.0f}s)...", flush=True)
        while len(self.inst.getConnections()) < a.wait_for_clients:
            if time.monotonic() > deadline:
                print("WARNING: timed out waiting for clients; starting the match anyway", flush=True)
                return
            self.tick()
            time.sleep(0.05)
        self.event("clients_connected", clients=len(self.inst.getConnections()))

    def run(self):
        a = self.args
        fast = a.fast
        base = CTRL_DS | (CTRL_FMS if a.fms else 0)
        phases = [
            ("pre_match", a.pre_sec / fast, base),
            ("auto", a.auto_sec / fast, base | CTRL_ENABLED | CTRL_AUTO),
            ("pause", a.pause_sec / fast, base),
            ("teleop", a.teleop_sec / fast, base | CTRL_ENABLED),
            ("post_match", a.post_sec / fast, base),
        ]
        self.start_server()
        where = f"{a.listen or '0.0.0.0'}:{a.port}"
        clock = "not published" if a.no_clock else f"offset {a.clock_offset_sec:+.0f}s"
        print(f"Fake roboRIO NT4 server listening on {where} (clock {clock}, fast x{fast:g})", flush=True)
        if a.wait_for_clients:
            self.wait_for_clients()
        for m in range(1, a.loops + 1):
            self.match = m
            for name, duration, word in phases:
                drop_after = a.drop_at_sec if (name == "teleop" and a.drop_at_sec is not None) else None
                self.run_phase(name, duration, word, drop_after)
            if m < a.loops and a.between_matches_sec > 0:
                self.run_phase("between", a.between_matches_sec / fast, base)
        self.phase = "done"
        self.event("done")
        if a.stay_up:
            print("Match over; --stay-up set, serving until Ctrl+C.", flush=True)
            while True:
                self.tick()
                time.sleep(TICK_SEC)

    def close(self):
        if self.event_file:
            self.event_file.close()
        if self.inst is not None:
            try:
                self.inst.stopServer()
            except Exception:
                pass


def positive(text):
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return value


def non_negative(text):
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return value


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Fake roboRIO NT4 server that plays out a match.")
    p.add_argument("--listen", default="0.0.0.0", help="address to listen on (default 0.0.0.0)")
    p.add_argument("--port", type=int, default=5810, help="NT4 port (default 5810; use another if PhotonVision already holds it)")
    p.add_argument("--pre-sec", type=non_negative, default=5.0, help="pre-match disabled (default 5)")
    p.add_argument("--auto-sec", type=non_negative, default=20.0, help="autonomous, enabled (default 20)")
    p.add_argument("--pause-sec", type=non_negative, default=3.0, help="disabled gap between auto and teleop (default 3)")
    p.add_argument("--teleop-sec", type=non_negative, default=140.0, help="teleop, enabled (default 140)")
    p.add_argument("--post-sec", type=non_negative, default=10.0, help="post-match disabled (default 10)")
    p.add_argument("--fast", type=positive, default=1.0, metavar="N", help="divide every phase duration by N (default 1)")
    p.add_argument("--loops", type=int, default=1, help="play the match N times back to back (default 1)")
    p.add_argument("--between-matches-sec", type=non_negative, default=5.0, help="disabled gap between looped matches, also divided by --fast (default 5)")
    p.add_argument("--fms", action="store_true", help="set the fmsAttached bit (control word + 16)")
    p.add_argument("--clock-offset-sec", type=float, default=0.0, help="skew the published RobotTime/WallClockMs by N seconds")
    p.add_argument("--no-clock", action="store_true", help="never publish RobotTime/WallClockMs")
    p.add_argument("--drop-at-sec", type=non_negative, default=None, metavar="T",
                   help="shut the NT server down T real seconds into teleop (NOT divided by --fast), every match")
    p.add_argument("--drop-for-sec", type=positive, default=2.0, metavar="D", help="restart it D real seconds later (default 2)")
    p.add_argument("--wait-for-clients", type=int, default=0, metavar="N",
                   help="hold the timeline (server up, control word 0) until N NT clients are connected")
    p.add_argument("--wait-timeout-sec", type=positive, default=60.0, help="give up waiting for clients after this long (default 60)")
    p.add_argument("--event-log", metavar="PATH", help="write one JSON object per phase transition to PATH (JSONL)")
    p.add_argument("--stay-up", action="store_true", help="keep serving after the match instead of exiting")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    robot = FakeRobot(args)
    try:
        robot.run()
    except KeyboardInterrupt:
        print("Interrupted.", flush=True)
    finally:
        robot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
