"""Small dependency-free MJPEG reader used by the tuning UI."""
from __future__ import annotations

import urllib.request

JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


class MjpegFrameReader:
    def __init__(self, url: str, timeout_sec: float = 5.0):
        self.url = url
        self.timeout_sec = timeout_sec
        self._stream = None
        self._buffer = b""

    def __enter__(self):
        self._stream = urllib.request.urlopen(self.url, timeout=self.timeout_sec)
        return self

    def __exit__(self, *_exc):
        if self._stream is not None:
            self._stream.close()
        self._stream = None

    def read(self) -> bytes:
        if self._stream is None:
            raise RuntimeError("MJPEG reader must be used as a context manager")
        while True:
            chunk = self._stream.read(8192)
            if not chunk:
                raise ConnectionError("MJPEG stream closed")
            self._buffer += chunk
            start = self._buffer.find(JPEG_SOI)
            if start < 0:
                self._buffer = self._buffer[-16:]
                continue
            end = self._buffer.find(JPEG_EOI, start + 2)
            if end < 0:
                self._buffer = self._buffer[start:]
                continue
            frame = self._buffer[start:end + 2]
            self._buffer = self._buffer[end + 2:]
            return frame

