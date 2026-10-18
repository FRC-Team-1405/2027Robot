#!/usr/bin/env python3
"""Fake camera: a stdlib-only MJPEG server for exercising orangepi-vision-recorder.py
without a camera or PhotonVision. For LAPTOP / pytest use; the Pi uses the real camera.

Serves multipart/x-mixed-replace JPEG frames at /stream.mjpg (what the recorder's
MjpegFrameReader expects). Every frame is a real, decodable baseline JPEG (320x240
grayscale) that shows a frame counter and a millisecond wall-clock as big black-on-white
digits, AND carries the same two numbers in a JPEG COM (comment) segment so a test can
read them back exactly with decode_frame_info():

    from fake_mjpeg import decode_frame_info
    decode_frame_info(open("frame_123.456.jpg", "rb").read())   # {"n": 812, "ms": 1792341703538}

No JPEG library is needed: each 8x8 block of the image is flat black or white, so a
block is just a DC coefficient (the glyph font is drawn one font-pixel per 8x8 block).

Slow consumers behave realistically: frames are produced at --fps and written with a
blocking send, so when a client reads slower than the stream (the recorder samples at
~3 Hz from a 30 fps stream), the data piles up in socket buffers, the server's writes
block, and the frames the client eventually reads are OLD -- the frame's embedded ms is
when it was generated, not when it was read. Use --pad-bytes to make frames camera-sized
(real raw frames are tens of KB; the tiny default fills socket buffers very slowly) and
--sndbuf to shrink the server-side send buffer.

    python coprocessor/sim/fake_mjpeg.py --port 1181 --fps 30 --pad-bytes 40000
"""

import argparse
import json
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WIDTH, HEIGHT = 320, 240
BLOCK = 8
COLS, ROWS = WIDTH // BLOCK, HEIGHT // BLOCK  # 40 x 30 blocks

BOUNDARY = "fakeframe"
COM_PREFIX = b"FAKEMJPEG "

# 3x5 digit font, one font pixel per 8x8 image block.
FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}

# ---- baseline JPEG, DC-only ------------------------------------------------

# Standard luminance DC Huffman table (JPEG Annex K); AC table has only EOB.
DC_BITS = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
DC_VALS = list(range(12))
AC_BITS = [1] + [0] * 15
AC_VALS = [0x00]
QUANT_DC = 8  # DC step: a flat block's quantized DC is (pixel - 128), so +-128 covers 0..255


def _canonical_codes(bits, vals):
    codes, code, k = {}, 0, 0
    for length in range(1, 17):
        for _ in range(bits[length - 1]):
            codes[vals[k]] = (code, length)
            code += 1
            k += 1
        code <<= 1
    return codes


DC_CODES = _canonical_codes(DC_BITS, DC_VALS)
AC_CODES = _canonical_codes(AC_BITS, AC_VALS)


def _segment(marker, payload):
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload


def _jpeg_header(width, height):
    dqt = _segment(0xDB, bytes([0]) + bytes([QUANT_DC] * 64))
    sof = _segment(0xC0, struct.pack(">BHHB", 8, height, width, 1) + bytes([1, 0x11, 0]))
    dht_dc = _segment(0xC4, bytes([0x00]) + bytes(DC_BITS) + bytes(DC_VALS))
    dht_ac = _segment(0xC4, bytes([0x10]) + bytes(AC_BITS) + bytes(AC_VALS))
    sos = _segment(0xDA, bytes([1, 1, 0x00, 0, 63, 0]))
    return dqt + sof + dht_dc + dht_ac + sos


_HEADER = _jpeg_header(WIDTH, HEIGHT)


def _scan_data(grid):
    """Entropy-code a ROWS x COLS grid of block levels (0 black / 1 white)."""
    out = bytearray()
    acc = nbits = 0
    prev_dc = 0
    eob_code, eob_len = AC_CODES[0]
    for row in grid:
        for level in row:
            dc = 127 if level else -128
            diff = dc - prev_dc
            prev_dc = dc
            cat = abs(diff).bit_length()
            code, length = DC_CODES[cat]
            acc = (acc << length) | code
            nbits += length
            if cat:
                acc = (acc << cat) | (diff if diff > 0 else diff + (1 << cat) - 1)
                nbits += cat
            acc = (acc << eob_len) | eob_code
            nbits += eob_len
            while nbits >= 8:
                nbits -= 8
                byte = (acc >> nbits) & 0xFF
                out.append(byte)
                if byte == 0xFF:
                    out.append(0x00)  # byte stuffing
            acc &= (1 << nbits) - 1
    if nbits:
        byte = ((acc << (8 - nbits)) | ((1 << (8 - nbits)) - 1)) & 0xFF  # pad with 1s
        out.append(byte)
        if byte == 0xFF:
            out.append(0x00)
    return bytes(out)


def _draw(grid, text, row, col):
    for ch in text:
        for dy, line in enumerate(FONT[ch]):
            for dx, bit in enumerate(line):
                if bit == "1":
                    grid[row + dy][col + dx] = 0
        col += 4


def make_frame(counter, wall_ms, pad_bytes=0):
    """Build one JPEG showing `counter` and `wall_ms` (drawn and in a COM segment)."""
    grid = [[1] * COLS for _ in range(ROWS)]
    ms = f"{wall_ms:013d}"
    _draw(grid, f"{counter % 10**10:010d}", 1, 0)
    _draw(grid, ms[:7], 8, 0)
    _draw(grid, ms[7:], 15, 0)
    comment = COM_PREFIX + json.dumps({"n": counter, "ms": wall_ms}, separators=(",", ":")).encode()
    jpeg = bytearray(b"\xff\xd8" + _segment(0xFE, comment))
    remaining = max(0, pad_bytes)
    while remaining > 0:  # filler COM segments (ASCII, so never contains an EOI marker)
        n = min(remaining, 60000)
        jpeg += _segment(0xFE, b"." * n)
        remaining -= n
    jpeg += _HEADER + _scan_data(grid) + b"\xff\xd9"
    return bytes(jpeg)


def decode_frame_info(jpeg):
    """Return {"n": frame counter, "ms": wall-clock ms at generation} from a frame made
    by make_frame(), or None if the bytes carry no such comment."""
    if jpeg[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF:
        marker = jpeg[pos + 1]
        if marker == 0xDA:  # start of scan: no more header segments
            break
        length = struct.unpack(">H", jpeg[pos + 2:pos + 4])[0]
        body = jpeg[pos + 4:pos + 2 + length]
        if marker == 0xFE and body.startswith(COM_PREFIX):
            return json.loads(body[len(COM_PREFIX):].decode())
        pos += 2 + length
    return None


# ---- server ------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep test/CLI output quiet
        pass

    def do_GET(self):
        if self.path.split("?")[0] != "/stream.mjpg":
            self.send_error(404)
            return
        srv = self.server
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # else Nagle + delayed ACK stalls small frames
        if srv.sndbuf:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, srv.sndbuf)
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        period = 1.0 / srv.fps
        deadline = time.monotonic()
        try:
            while not srv.stopping.is_set():
                deadline = max(deadline + period, time.monotonic() - period)  # don't burst to catch up
                delay = deadline - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                # Content is stamped here, BEFORE the (possibly blocking) send below, so a
                # slow client receives frames that are already old by the time it reads them.
                now_ms = int(time.time() * 1000)
                counter = int((time.monotonic() - srv.t0) * srv.fps)
                jpeg = make_frame(counter, now_ms, srv.pad_bytes)
                head = (f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(jpeg)}\r\n\r\n").encode()
                self.wfile.write(head + jpeg + b"\r\n")  # blocks when the client isn't reading
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass


class FakeMjpegServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host="127.0.0.1", port=0, fps=30.0, pad_bytes=0, sndbuf=None):
        super().__init__((host, port), _Handler)
        self.fps = float(fps)
        self.pad_bytes = pad_bytes
        self.sndbuf = sndbuf
        self.t0 = time.monotonic()
        self.stopping = threading.Event()
        self._thread = None

    @property
    def port(self):
        return self.server_address[1]

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/stream.mjpg"

    def start(self):
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self.stopping.set()
        self.shutdown()
        self.server_close()


def main():
    p = argparse.ArgumentParser(description="Fake MJPEG camera stream at /stream.mjpg.")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=1181, help="HTTP port (default 1181)")
    p.add_argument("--fps", type=float, default=30.0, help="frames per second (default 30)")
    p.add_argument("--pad-bytes", type=int, default=0, help="inflate each frame by this many bytes of comment filler (real frames are tens of KB)")
    p.add_argument("--sndbuf", type=int, default=None, help="server-side SO_SNDBUF per client, bytes")
    args = p.parse_args()
    server = FakeMjpegServer(args.host, args.port, args.fps, args.pad_bytes, args.sndbuf)
    print(f"Fake MJPEG stream at http://{args.host}:{server.port}/stream.mjpg ({args.fps:g} fps, {WIDTH}x{HEIGHT}, "
          f"~{len(make_frame(0, 0, args.pad_bytes))} bytes/frame)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        server.server_close()


if __name__ == "__main__":
    main()
