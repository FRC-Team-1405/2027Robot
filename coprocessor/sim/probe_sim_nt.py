#!/usr/bin/env python3
"""Connects to a running robot simulation's NetworkTables server as the Pi recorder would, and
reports the two things the recorder needs: the control word on /FMSInfo/FMSControlData (every
change, with the decoded mode) and /RobotTime/WallClockMs (and how far it is from this machine's
clock). Use it to confirm a Run-SimRobotMatch.ps1 setup would work before involving the Pi:

    python coprocessor/sim/probe_sim_nt.py --server 127.0.0.1 --seconds 40

Exit 0 if both topics were seen and the control word reached enabled; 1 otherwise.
"""
import argparse
import sys
import time

import ntcore


def describe(word: int) -> str:
    if not word & 1:
        return "disabled"
    return "auto" if word & 2 else "teleop"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--server", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5810)
    ap.add_argument("--seconds", type=float, default=40.0)
    args = ap.parse_args()

    inst = ntcore.NetworkTableInstance.getDefault()
    inst.startClient4("sim-probe")
    inst.setServer(args.server, args.port)
    control = inst.getTable("FMSInfo").getIntegerTopic("FMSControlData").getEntry(-1)
    clock = inst.getTable("RobotTime").getIntegerTopic("WallClockMs").getEntry(0)

    seen_modes, last_word, clock_seen, skew = [], None, False, None
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        if inst.isConnected():
            word = control.get(-1)
            if word != last_word and word != -1:
                last_word = word
                mode = describe(word)
                seen_modes.append(mode)
                print("control word %3d (0b%s) -> %s" % (word, format(word, "06b"), mode), flush=True)
            ms = clock.get(0)
            if ms and not clock_seen:
                clock_seen = True
                skew = ms / 1000.0 - time.time()
                print("RobotTime/WallClockMs present; robot clock - this machine = %+.3f s" % skew, flush=True)
        time.sleep(0.05)
    print("modes seen: %s; wall clock seen: %s" % (seen_modes, clock_seen))
    ok = clock_seen and "disabled" in seen_modes and any(m in seen_modes for m in ("auto", "teleop"))
    print("PROBE " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
