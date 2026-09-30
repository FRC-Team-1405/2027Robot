"""remote_fetch.py: SFTP to the RIO/Pi over paramiko. No real network -- paramiko's
SSHClient/SFTPClient are mocked (paramiko itself is a real dependency of this tool, but
actually connecting to a host has no place in this suite)."""
import io
import pathlib
import stat
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: sys.path bridges)

from remote_config import HostConfig
import remote_fetch


def _cfg(**overrides):
    defaults = dict(host='roborio-1405-frc.local', user='lvuser', path='/home/lvuser/logs')
    defaults.update(overrides)
    return HostConfig(**defaults)


class _FakeAttr:
    def __init__(self, filename, size=1234, mtime=1700000000.0, is_dir=False):
        self.filename = filename
        self.st_size = size
        self.st_mtime = mtime
        self.st_mode = (stat.S_IFDIR if is_dir else stat.S_IFREG) | 0o755


def _mock_paramiko(sftp_mock):
    """Patches the `paramiko` module remote_fetch imports lazily inside _connect()."""
    fake_paramiko = MagicMock()
    fake_client = MagicMock()
    fake_client.open_sftp.return_value = sftp_mock
    fake_paramiko.SSHClient.return_value = fake_client
    fake_paramiko.AutoAddPolicy = MagicMock
    return patch.dict(sys.modules, {'paramiko': fake_paramiko}), fake_client


# ── list_rio_logs ───────────────────────────────────────────────────────────────────

def test_list_rio_logs_parses_a_ds_renamed_wall_clock():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _FakeAttr('FRC_20260115_143022.wpilog', size=555, mtime=1700000001.0),
    ]
    patcher, client = _mock_paramiko(sftp)
    with patcher:
        logs = remote_fetch.list_rio_logs(_cfg())

    assert len(logs) == 1
    assert logs[0]['name'] == 'FRC_20260115_143022.wpilog'
    assert logs[0]['size'] == 555
    assert logs[0]['wall_clock'] is not None
    assert logs[0]['wall_clock'].isoformat() == '2026-01-15T14:30:22'
    sftp.close.assert_called_once()
    client.close.assert_called_once()


def test_list_rio_logs_flags_an_unrenamed_log_as_wall_clock_none():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [_FakeAttr('FRC_TBD_143022.wpilog')]
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        logs = remote_fetch.list_rio_logs(_cfg())

    assert logs[0]['wall_clock'] is None


def test_list_rio_logs_ignores_non_wpilog_entries_and_directories():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _FakeAttr('FRC_20260115_143022.wpilog'),
        _FakeAttr('notes.txt'),
        _FakeAttr('somedir', is_dir=True),
    ]
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        logs = remote_fetch.list_rio_logs(_cfg())

    assert [l['name'] for l in logs] == ['FRC_20260115_143022.wpilog']


def test_list_rio_logs_sorts_newest_first():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _FakeAttr('old.wpilog', mtime=100.0),
        _FakeAttr('new.wpilog', mtime=200.0),
    ]
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        logs = remote_fetch.list_rio_logs(_cfg())

    assert [l['name'] for l in logs] == ['new.wpilog', 'old.wpilog']


def test_list_rio_logs_wraps_a_listing_failure_in_remote_fetch_error():
    sftp = MagicMock()
    sftp.listdir_attr.side_effect = OSError('permission denied')
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        with pytest.raises(remote_fetch.RemoteFetchError):
            remote_fetch.list_rio_logs(_cfg())


def test_connect_failure_is_wrapped_in_remote_fetch_error():
    fake_paramiko = MagicMock()
    fake_client = MagicMock()
    fake_client.connect.side_effect = OSError('connection refused')
    fake_paramiko.SSHClient.return_value = fake_client
    fake_paramiko.AutoAddPolicy = MagicMock

    with patch.dict(sys.modules, {'paramiko': fake_paramiko}):
        with pytest.raises(remote_fetch.RemoteFetchError):
            remote_fetch.list_rio_logs(_cfg())
    fake_client.close.assert_called_once()


# ── list_pi_sessions ────────────────────────────────────────────────────────────────

def test_list_pi_sessions_discovers_camera_namespaced_layout():
    sftp = MagicMock()

    def listdir_attr(path):
        if path == '/home/photon/vision-recordings':
            return [_FakeAttr('Left', is_dir=True), _FakeAttr('Right', is_dir=True)]
        if path.endswith('/Left'):
            return [_FakeAttr('boot0001-20260115-143010', is_dir=True)]
        if path.endswith('/Right'):
            return [_FakeAttr('boot0001-20260115-143012', is_dir=True)]
        return []

    sftp.listdir_attr.side_effect = listdir_attr
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        sessions = remote_fetch.list_pi_sessions(
            _cfg(host='photonvision.local', user='photon', path='/home/photon/vision-recordings'))

    by_camera = {s['camera']: s['name'] for s in sessions}
    assert by_camera == {'Left': 'boot0001-20260115-143010', 'Right': 'boot0001-20260115-143012'}
    assert all(s['wall_clock'] is not None for s in sessions)


def test_list_pi_sessions_discovers_legacy_layout_when_no_camera_subfolders_exist():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [_FakeAttr('boot0001-20260115-143010', is_dir=True)]
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        sessions = remote_fetch.list_pi_sessions(_cfg(path='/home/photon/vision-recordings'))

    assert len(sessions) == 1
    assert sessions[0]['camera'] == ''
    assert sessions[0]['name'] == 'boot0001-20260115-143010'


def test_list_pi_sessions_flags_an_unparseable_session_name():
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [_FakeAttr('bootWEIRDNAME', is_dir=True)]
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        sessions = remote_fetch.list_pi_sessions(_cfg())

    assert sessions[0]['wall_clock'] is None


# ── fetch_rio_log / fetch_pi_session ────────────────────────────────────────────────

def test_fetch_rio_log_downloads_into_dest_dir(tmp_path):
    sftp = MagicMock()
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        local_path = remote_fetch.fetch_rio_log(_cfg(), 'FRC_20260115_143022.wpilog', tmp_path)

    assert local_path == tmp_path / 'FRC_20260115_143022.wpilog'
    sftp.get.assert_called_once_with(
        '/home/lvuser/logs/FRC_20260115_143022.wpilog', str(local_path))


def test_fetch_rio_log_wraps_a_download_failure(tmp_path):
    sftp = MagicMock()
    sftp.get.side_effect = OSError('no such file')
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        with pytest.raises(remote_fetch.RemoteFetchError):
            remote_fetch.fetch_rio_log(_cfg(), 'missing.wpilog', tmp_path)


def test_fetch_pi_session_downloads_manifest_and_frames_under_camera_and_session(tmp_path):
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _FakeAttr('manifest.jsonl'),
        _FakeAttr('frame_10.000000.jpg'),
        _FakeAttr('frame_10.020000.jpg'),
    ]
    cfg = _cfg(host='photonvision.local', user='photon', path='/home/photon/vision-recordings')
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        session_dir = remote_fetch.fetch_pi_session(cfg, 'Left', 'boot0001-20260115-143010', tmp_path)

    assert session_dir == tmp_path / 'Left' / 'boot0001-20260115-143010'
    assert session_dir.is_dir()
    assert sftp.get.call_count == 3
    get_dest_names = {pathlib.Path(call.args[1]).name for call in sftp.get.call_args_list}
    assert get_dest_names == {'manifest.jsonl', 'frame_10.000000.jpg', 'frame_10.020000.jpg'}


def test_fetch_pi_session_with_empty_camera_downloads_directly_under_dest_dir(tmp_path):
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [_FakeAttr('manifest.jsonl')]
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        session_dir = remote_fetch.fetch_pi_session(_cfg(), '', 'boot0001-20260115-143010', tmp_path)

    assert session_dir == tmp_path / 'boot0001-20260115-143010'


def test_fetch_pi_session_wraps_a_listing_failure(tmp_path):
    sftp = MagicMock()
    sftp.listdir_attr.side_effect = OSError('no such directory')
    patcher, _ = _mock_paramiko(sftp)
    with patcher:
        with pytest.raises(remote_fetch.RemoteFetchError):
            remote_fetch.fetch_pi_session(_cfg(), 'Left', 'boot0001', tmp_path)
