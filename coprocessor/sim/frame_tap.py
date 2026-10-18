#!/usr/bin/env python3
"""Logs the arrival time and SHA-1 of every frame on an MJPEG stream, as ground truth.

Run on the Orange Pi (in the pyntcore venv) alongside the recorder during a simulated
match. PhotonVision serves byte-identical JPEGs to every client, so verify_recordings.py can
match each recorded frame's hash back to the instant it left PhotonVision and compute the
frame's true age at recording time. Timestamps use ntcore._now(), the same clock the
recorder's t_sec is derived from (the recorder adds the NT server offset, ~0 when the fake
server runs on the same host).

    ~/.venv-ntpublisher/bin/python3 frame_tap.py --url http://localhost:1181/stream.mjpg --out tap.jsonl

Stops on SIGTERM/SIGINT or after --duration seconds. Stdlib + ntcore only.
"""
import argparse
import hashlib
import json
import signal
import sys
import time
import urllib.request

JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"

_stop = False


def _handle(_sig, _frm):
    global _stop
    _stop = True


def now_sec():
    import ntcore

    return ntcore._now() / 1_000_000.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default="http://localhost:1181/stream.mjpg")
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (0 = until signalled)")
    args = ap.parse_args()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    start = time.monotonic()
    count = 0
    buf = b""
    stream = None
    with open(args.out, "w") as out:
        while not _stop and not (args.duration and time.monotonic() - start >= args.duration):
            try:
                if stream is None:
                    stream = urllib.request.urlopen(args.url, timeout=5)
                    buf = b""
                chunk = stream.read(4096)
                if not chunk:
                    raise ConnectionError("stream closed")
                t_chunk = now_sec()
                buf += chunk
                while True:
                    a = buf.find(JPEG_SOI)
                    if a == -1:
                        buf = buf[-16:]
                        break
                    b = buf.find(JPEG_EOI, a)
                    if b == -1:
                        buf = buf[a:]
                        break
                    frame = buf[a:b + 2]
                    buf = buf[b + 2:]
                    count += 1
                    out.write(json.dumps({"n": count, "t": round(t_chunk, 6),
                                          "sha1": hashlib.sha1(frame).hexdigest(), "size": len(frame)}) + "\n")
                if count % 200 == 0:
                    out.flush()
            except Exception as e:  # keep tapping across a PhotonVision restart
                print(f"tap error: {e}", file=sys.stderr)
                stream = None
                time.sleep(1.0)
    print(f"tap done: {count} frames in {time.monotonic() - start:.1f}s")


if __name__ == "__main__":
    main()
