"""remote_fetch.list_pi_sessions reads each session's clock (epoch, first/last frame t_sec) from the
head and tail of its manifest, over a fake SFTP that serves in-memory files."""
import datetime as dt
import json
import pathlib
import stat
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import remote_fetch
from remote_config import HostConfig

BOOT = dt.datetime(2026, 10, 17, 12, 30, 0, tzinfo=dt.timezone.utc)
SESSION = 'boot0003-20261017-083504'     # US Eastern (EDT, UTC-4) -> 12:35:04 UTC


class _Attr:
    def __init__(self, filename, size=0, is_dir=False):
        self.filename, self.st_size, self.st_mtime = filename, size, 1.0
        self.st_mode = (stat.S_IFDIR if is_dir else stat.S_IFREG) | 0o755


class _File:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def seek(self, n):
        self.pos = n

    def read(self, n):
        out = self.data[self.pos:self.pos + n]
        self.pos += len(out)
        return out


def fake_sftp(manifests):
    """manifests: {remote session dir: bytes}."""
    sftp = MagicMock()

    def listdir_attr(path):
        if path == '/rec':
            return [_Attr('LeftCam', is_dir=True)]
        if path == '/rec/LeftCam':
            return [_Attr(posix.rsplit('/', 1)[1], is_dir=True) for posix in manifests]
        return []

    def stat_(path):
        data = manifests[path.rsplit('/', 1)[0]]
        return _Attr('manifest.jsonl', size=len(data))

    sftp.listdir_attr.side_effect = listdir_attr
    sftp.stat.side_effect = stat_
    sftp.open.side_effect = lambda path, mode='r': _File(manifests[path.rsplit('/', 1)[0]])
    return sftp


def run(manifests, **cfg):
    sftp = fake_sftp(manifests)
    client = MagicMock()
    client.open_sftp.return_value = sftp
    fake_paramiko = MagicMock()
    fake_paramiko.SSHClient.return_value = client
    fake_paramiko.AutoAddPolicy = MagicMock
    remote_fetch._clock_cache.clear()
    with patch.dict(sys.modules, {'paramiko': fake_paramiko}):
        return remote_fetch.list_pi_sessions(HostConfig(host='pi.local', user='pi', path='/rec', **cfg)), sftp


def rows(t0, n, step=0.33, utc=True):
    out = []
    for i in range(n):
        t = t0 + i * step
        row = {'frame': 'frame_%.6f.jpg' % t, 't_sec': t, 'timestamp_utc': None, 'timestamp_status': 'nt_clock_unsynced'}
        if utc:
            wall = BOOT + dt.timedelta(seconds=t)
            row.update(timestamp_utc=wall.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                       timestamp_status='synced')
        out.append(json.dumps(row))
    return ('\n'.join(out) + '\n').encode()


def test_a_session_gets_its_epoch_and_frame_range_from_the_manifest():
    [s], _ = run({'/rec/LeftCam/' + SESSION: rows(304.0, 50)})
    assert abs((s['epoch'] - BOOT).total_seconds()) < 0.01
    assert s['t_first'] == 304.0 and abs(s['t_last'] - (304.0 + 49 * 0.33)) < 1e-6


def test_a_long_session_reads_only_the_ends_and_tolerates_a_torn_last_row():
    body = rows(304.0, 400)                           # ~50 KB, well past the 16 KB peek
    assert len(body) > 2 * remote_fetch._MANIFEST_PEEK_BYTES
    torn = body + b'{"frame": "frame_999.jpg", "t_se'
    [s], _ = run({'/rec/LeftCam/' + SESSION: torn})
    assert s['t_first'] == 304.0
    assert abs(s['t_last'] - (304.0 + 399 * 0.33)) < 1e-6


def test_an_older_recorder_without_robot_timestamps_uses_the_session_name():
    [s], _ = run({'/rec/LeftCam/' + SESSION: rows(304.0, 5, utc=False)})
    name_time = dt.datetime(2026, 10, 17, 12, 35, 4, tzinfo=dt.timezone.utc)
    assert s['epoch'] == name_time - dt.timedelta(seconds=304.0)


def test_an_empty_or_missing_manifest_leaves_the_clock_unknown_and_the_session_listed():
    [s], _ = run({'/rec/LeftCam/' + SESSION: b''})
    assert (s['epoch'], s['t_first'], s['t_last']) == (None, None, None)
    assert s['wall_clock'] is not None
