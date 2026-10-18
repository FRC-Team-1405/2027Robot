"""Synthetic camera frames with the sync information burned in.

A frame is a real, decodable JPEG (built by coprocessor/sim/fake_mjpeg.py's stdlib encoder)
showing its LOG time in milliseconds as big digits, a mode code and a frame number, and
carrying the same facts in a JPEG comment segment. A person watching the dashboard video can
therefore read off which log instant a frame claims to be, and a test can read it exactly with
`decode_frame_info()` and compare it with the playhead.

Mode code on the picture: 0 = disabled, 1 = auto, 2 = teleop (plus a bar that many blocks wide).
The lower half shows the CAMERA NUMBER (1 = first logged camera, 2 = second, ...) with a bar of 8
blocks per camera, so two feeds are told apart at a glance when switching between them.
"""
import json
import pathlib
import sys

_SIM = pathlib.Path(__file__).resolve().parents[3] / 'coprocessor' / 'sim'
if str(_SIM) not in sys.path:
    sys.path.insert(0, str(_SIM))

import fake_mjpeg as _fm  # noqa: E402  (stdlib only)

COM_PREFIX = b'LBTESTKIT '
MODE_CODE = {'disabled': 0, 'auto': 1, 'teleop': 2}


def make_frame(t_sec: float, mode: str, seq: int, camera: str = '', camera_index: int = 0) -> bytes:
    grid = [[1] * _fm.COLS for _ in range(_fm.ROWS)]
    _fm._draw(grid, f'{int(round(t_sec * 1000)):010d}', 1, 0)   # log time, ms
    _fm._draw(grid, str(MODE_CODE.get(mode, 9)), 8, 0)           # mode code
    for dx in range(4 * (MODE_CODE.get(mode, 3) + 1)):           # ...and a bar, wider for later modes
        for dy in (14, 15):
            grid[dy][dx] = 0
    _fm._draw(grid, f'{seq % 10**6:06d}', 18, 0)                 # frame number
    if camera_index:
        _fm._draw(grid, str(camera_index % 10), 24, 0)           # camera number
        for dx in range(min(_fm.COLS - 6, 8 * camera_index)):
            for dy in (25, 26, 27):
                grid[dy][6 + dx] = 0
    comment = COM_PREFIX + json.dumps(
        {'t_sec': round(t_sec, 6), 'mode': mode, 'seq': seq, 'camera': camera, 'camera_index': camera_index}, separators=(',', ':')).encode()
    return b'\xff\xd8' + _fm._segment(0xFE, comment) + _fm._HEADER + _fm._scan_data(grid) + b'\xff\xd9'


def decode_frame_info(jpeg: bytes):
    """{'t_sec', 'mode', 'seq', 'camera'} from a frame made by make_frame(), else None."""
    if jpeg[:2] != b'\xff\xd8':
        return None
    pos = 2
    while pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF:
        marker = jpeg[pos + 1]
        if marker == 0xDA:
            break
        length = int.from_bytes(jpeg[pos + 2:pos + 4], 'big')
        body = jpeg[pos + 4:pos + 2 + length]
        if marker == 0xFE and body.startswith(COM_PREFIX):
            return json.loads(body[len(COM_PREFIX):].decode())
        pos += 2 + length
    return None
