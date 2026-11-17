"""Post-match fetch, verified trim, archive download and import round trip."""
import io
import json
import pathlib
import sys
import time
import zipfile
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'wpilog-utils' / 'tests'))
import paths  # noqa: F401
import wpilog_builder as wb
from wpilog_utils.decode import parse_wpilog_bytes
import match_bundle


def sample():
    return wb.ds_log([('disabled', 10), ('auto', 3), ('disabled', 10),
                      ('teleop', 3), ('disabled', 10)])[0]


def test_archive_keeps_original_and_only_selected_sessions_and_preserves_timestamps(tmp_path):
    source = tmp_path / 'match.wpilog'
    original = sample()
    source.write_bytes(original)
    selected = tmp_path / 'match.vision' / 'RightCam' / 'boot0001'
    selected.mkdir(parents=True)
    (selected / 'recorder.log').write_text('stream error\n')
    (selected / 'recorder.log.1').write_text('startup\n')
    (selected / 'frame_12.jpg').write_bytes(b'jpeg')
    (selected / 'manifest.jsonl').write_text('{"frame":"frame_12.jpg","t_sec":12}\n')
    stale = selected.parent / 'boot-old'
    stale.mkdir()
    (stale / 'stale.jpg').write_bytes(b'stale')
    result = match_bundle.prepare(source, [selected], tmp_path / 'out')
    assert source.read_bytes() == original
    with zipfile.ZipFile(tmp_path / 'out' / result['archive']) as zf:
        assert zf.read('match.wpilog') == original
        trimmed = zf.read('match.trimmed.wpilog')
        before = dict(parse_wpilog_bytes(original)['Sensor/X'])
        after = parse_wpilog_bytes(trimmed)['Sensor/X']
        assert 0 < len(after) < len(before)
        assert all(before[t] == v for t, v in after)
        assert all(9 <= t <= 16 or 22 <= t <= 29 for t, _ in after)
        assert 'match.vision/RightCam/boot0001/recorder.log.1' in zf.namelist()
        assert not any('boot-old' in name for name in zf.namelist())
        assert json.loads(zf.read('match.trim.json'))['timestamps'] == 'preserved'


def test_out_of_order_log_is_fixed_only_in_working_copy(tmp_path):
    raw, info = wb.ds_log([('disabled', 10), ('auto', 3), ('disabled', 10)],
                          extra_entries=[('/Late', 'double')])
    raw += wb.record(info['ids']['/Late'], 11_000_000, wb.double(7))
    source = tmp_path / 'match.wpilog'
    source.write_bytes(raw)
    match_bundle.prepare(source, [], tmp_path / 'out')
    assert source.read_bytes() == raw
    report = json.loads((tmp_path / 'out' / 'match.trim.json').read_text())
    assert report['reordered_working_copy']


def test_no_enabled_periods_keeps_full_copy_and_reports_warning(tmp_path):
    source = tmp_path / 'disabled.wpilog'
    raw = wb.ds_log([('disabled', 10)])[0]
    source.write_bytes(raw)
    result = match_bundle.prepare(source, [], tmp_path / 'out')
    assert result['warnings']
    assert (tmp_path / 'out' / result['trimmed_log']).read_bytes() == raw


@pytest.mark.parametrize('failure', ['index-overflow', 'order-check', 'trim-check'])
def test_processing_failure_archives_original_without_unverified_copy(tmp_path, monkeypatch, failure):
    raw = sample()
    if failure == 'index-overflow':
        def overflow(_raw):
            raise OverflowError('int too big to convert')
        monkeypatch.setattr(match_bundle, 'build_index', overflow)
    elif failure == 'order-check':
        raw += wb.record(4, 1_000_000, wb.double(1))
        monkeypatch.setattr(match_bundle, 'verify_reorder', lambda *a: SimpleNamespace(ok=False))
    else:
        monkeypatch.setattr(match_bundle, 'verify_trim', lambda *a: SimpleNamespace(ok=False))
    source = tmp_path / 'match.wpilog'
    source.write_bytes(raw)
    out = tmp_path / 'out'
    result = match_bundle.prepare(source, [], out)
    assert source.read_bytes() == raw
    assert 'trimmed_log' not in result
    assert not list(out.glob('*.trimmed.wpilog'))
    with zipfile.ZipFile(out / result['archive']) as archive:
        assert set(archive.namelist()) == {'match.wpilog', 'match.trim.json'}
        assert archive.read('match.wpilog') == raw
        report = json.loads(archive.read('match.trim.json'))
        assert report['trim_status'] == 'failed' and report['trim_error']
        assert report['stats'] is None and report['trimmed'] is None
        assert report['warnings'] == result['warnings']


def test_cancel_during_packaging_never_publishes_a_partial_zip(tmp_path):
    source = tmp_path / 'match.wpilog'
    source.write_bytes(sample())
    cancelled = False

    def phase(text):
        nonlocal cancelled
        if text == 'Creating downloadable ZIP':
            cancelled = True

    with pytest.raises(RuntimeError, match='cancelled'):
        match_bundle.prepare(source, [], tmp_path / 'out', phase, lambda: cancelled)
    assert not list((tmp_path / 'out').glob('*.zip*'))


@pytest.mark.parametrize('include_battery', [False, True])
@pytest.mark.parametrize('bad_timestamp', [None, 2**63, 2**80])
def test_one_job_fetches_trims_downloads_and_imports(tmp_path, monkeypatch, include_battery, bad_timestamp):
    from fastapi.testclient import TestClient
    import main
    import remote_config
    import remote_fetch
    raw = sample()
    if bad_timestamp is not None:
        raw += wb.record(4, bad_timestamp, wb.double(123))
    cfg = remote_config.RemoteConfig(
        rio=remote_config.HostConfig(host='rio', user='lvuser', path='/logs'),
        pis=[], source_path=pathlib.Path('config.json'))
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    monkeypatch.setattr(remote_config, 'load_remote_config', lambda: cfg)
    monkeypatch.setattr(main, '_pi_for', lambda cfg, ref: cfg.rio)
    monkeypatch.setattr(remote_fetch, 'rio_log_size', lambda *a: len(raw))
    monkeypatch.setattr(remote_fetch, 'pi_session_files', lambda *a: [{'name': 'recorder.log', 'size': 8}])

    def fetch_log(cfg, name, dest, **kwargs):
        path = dest / name
        path.write_bytes(raw)
        return path

    def fetch_session(cfg, camera, name, dest, **kwargs):
        path = dest / camera / name
        path.mkdir(parents=True)
        (path / 'recorder.log').write_text('captured')
        return path

    monkeypatch.setattr(remote_fetch, 'fetch_rio_log', fetch_log)
    monkeypatch.setattr(remote_fetch, 'fetch_pi_session', fetch_session)
    client = TestClient(main.app)
    response = client.post('/api/remote/bundle/jobs', json={
        'rio_log': 'match.wpilog', 'prepare_download': True, 'include_battery': include_battery,
        'pi_sessions': [{'camera': 'RightCam', 'name': 'boot0001', 'pi': 'RightPi'}]})
    assert response.status_code == 202
    job_id = response.json()['job_id']
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f'/api/remote/jobs/{job_id}').json()
        if job['status'] in ('complete', 'error'):
            break
        time.sleep(.01)
    assert job['status'] == 'complete', job
    download = client.get(job['result']['download_url'])
    assert download.status_code == 200
    assert [row['path'] for row in client.get('/api/logs').json()['logs']] == ['match.wpilog']
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        expected = {'match.wpilog', 'match.trim.json',
                    'match.vision/RightCam/boot0001/recorder.log'}
        assert archive.read('match.wpilog') == raw
        report = json.loads(archive.read('match.trim.json'))
        if bad_timestamp is None:
            expected.add('match.trimmed.wpilog')
            assert report['trim_status'] == 'trimmed'
        else:
            assert report['trim_status'] == 'failed'
            assert report['trimmed'] is None and report['trimmed_bytes'] is None
            assert 'byte ' in report['trim_error']
            assert 'trimmed_log' not in job['result']
            assert job['result']['warnings'] == report['warnings']
            assert any('no trimmed copy' in warning for warning in report['warnings'])
            assert not list((tmp_path / '.bundles' / job_id).glob('*.trimmed.wpilog'))
            if include_battery:
                assert any('Battery analysis was skipped' in warning for warning in report['warnings'])
        if include_battery and bad_timestamp is None:
            expected.update({'match.battery.html', 'match.battery.json'})
            report = json.loads(archive.read('match.battery.json'))
            assert report['analysis_scope'] == 'full-original-log'
            assert report['log'] == 'match.wpilog'
            assert b'Battery Insights' in archive.read('match.battery.html')
        assert set(archive.namelist()) == expected
    imported = tmp_path / 'imported'
    imported.mkdir()
    monkeypatch.setattr(main, 'LOG_ROOT', imported)
    response = client.post('/api/import/zip', files={'file': ('match.zip', download.content, 'application/zip')})
    assert response.status_code == 200, response.text
    assert response.json()['log'] == 'match.wpilog'
    assert (imported / 'match.trimmed.wpilog').is_file() == (bad_timestamp is None)
    assert (imported / 'match.wpilog').read_bytes() == raw
    assert (imported / 'match.vision' / 'RightCam' / 'boot0001' / 'recorder.log').read_text() == 'captured'
    if bad_timestamp is None:
        assert main.bundles.vision_dir_for(imported / 'match.trimmed.wpilog') == imported / 'match.vision'


def test_battery_analysis_receives_recovery_current_beyond_trimmed_window(tmp_path, monkeypatch):
    raw, _ = wb.ds_log([('disabled', 10), ('auto', 3), ('disabled', 20)],
                       extra_entries=[('/PowerDistribution/TotalCurrent', 'double'),
                                      ('/SystemStats/BatteryVoltage', 'double')],
                       extra_records=[('/PowerDistribution/TotalCurrent', 0, wb.double(5)),
                                      ('/PowerDistribution/TotalCurrent', 600, wb.double(100)),
                                      ('/PowerDistribution/TotalCurrent', 1500, wb.double(2)),
                                      ('/SystemStats/BatteryVoltage', 0, wb.double(12.8)),
                                      ('/SystemStats/BatteryVoltage', 600, wb.double(9)),
                                      ('/SystemStats/BatteryVoltage', 1500, wb.double(12.5))])
    source = tmp_path / 'recovery.wpilog'
    source.write_bytes(raw)
    original_analyze = match_bundle.battery.analyze
    seen = []

    def analyze(log):
        seen.append(log)
        return original_analyze(log)

    monkeypatch.setattr(match_bundle.battery, 'analyze', analyze)
    match_bundle.prepare(source, [], tmp_path / 'out', include_battery=True)
    assert len(seen) == 1
    assert seen[0].path == source
    assert seen[0].signals['PowerDistribution/TotalCurrent'][-1] == (31, 2)
    trimmed = parse_wpilog_bytes((tmp_path / 'out' / 'recovery.trimmed.wpilog').read_bytes())
    assert trimmed['PowerDistribution/TotalCurrent'][-1][0] < 31
    assert trimmed['SystemStats/BatteryVoltage'][-1] == (31, 12.5)
    report = json.loads((tmp_path / 'out' / 'recovery.battery.json').read_text())
    assert report['window_s'][1] == pytest.approx(seen[0].bounds()[1] - seen[0].bounds()[0])


@pytest.mark.parametrize('bad_name', ['match.vision/../escape.txt', 'other.wpilog'])
def test_import_rejects_unrelated_logs_and_unsafe_paths(tmp_path, monkeypatch, bad_name):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('match.wpilog', sample())
        archive.writestr(bad_name, b'unexpected')
    response = TestClient(main.app).post('/api/import/zip', files={'file': ('x.zip', stream.getvalue())})
    assert response.status_code == 400
    assert not list(tmp_path.iterdir())
