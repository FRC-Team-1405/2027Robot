"""The janitor HTTP API, against synthetic logs in a temp directory."""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

import wpilog_builder as wb
from janitor.server import main as server
from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.index import build_index

SPANS = [('disabled', 1.0), ('auto', 1.0), ('disabled', 5.0), ('auto', 1.0), ('disabled', 2.0), ('teleop', 1.0)]


@pytest.fixture
def root(tmp_path):
    raw, _ = wb.ds_log(SPANS, extra_entries=[('/Vision/L/A', 'double')],
                       extra_records=[('/Vision/L/A', c, wb.double(c)) for c in range(0, 400, 2)])
    (tmp_path / 'match.wpilog').write_bytes(raw)
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'other.wpilog').write_bytes(raw)
    return tmp_path


@pytest.fixture
def client(root):
    return TestClient(server.create_app(root, dist=None))


def plan(**over):
    body = {'log': 'match.wpilog', 'segments': [{'start': 1.0, 'end': 2.0, 'label': 'auto'}, {'start': 7.0, 'end': 8.0, 'label': 'auto'}]}
    body.update(over)
    return body


# ── listing / index ─────────────────────────────────────────────────────────────────────────────

def test_lists_logs_recursively_with_sizes(client):
    r = client.get('/api/logs').json()
    assert {l['path'] for l in r['logs']} == {'match.wpilog', 'sub/other.wpilog'}
    assert all(l['size'] > 0 for l in r['logs'])


def test_index_describes_the_log(client, root):
    r = client.get('/api/index', params={'log': 'match.wpilog'}).json()
    assert r['name'] == 'match.wpilog' and r['size'] == (root / 'match.wpilog').stat().st_size
    assert [s['mode'] for s in r['spans']] == ['disabled', 'auto', 'disabled', 'auto', 'disabled', 'teleop']
    assert r['spans'][1]['bytes'] > 0 and sum(s['bytes'] for s in r['spans']) == r['data_bytes']
    assert r['n_cycles'] == 550 and r['cycle_period_ms'] == 20.0 and r['header'] == 'AdvantageKit'
    assert sum(r['byte_hist']) == r['data_bytes'] and r['time_mirrors'] == ['/Timestamp']
    assert r['warnings'] == []


def test_index_warns_when_there_are_no_mode_bands(client, root):
    b = wb.LogBuilder(); b.entry('/A', 'double')
    for k in range(50):
        b.data('/A', 1_000_000 + k * 20_000, wb.double(k))
    (root / 'plain.wpilog').write_bytes(b.build())
    r = client.get('/api/index', params={'log': 'plain.wpilog'}).json()
    assert r['spans'] == [] and any('no DriverStation' in w for w in r['warnings']) and any('/Timestamp' in w for w in r['warnings'])


def test_index_is_cached_until_the_file_changes(client, root, monkeypatch):
    calls = []
    real = server.build_index
    monkeypatch.setattr(server, 'build_index', lambda raw: calls.append(1) or real(raw))
    for _ in range(3):
        client.get('/api/index', params={'log': 'match.wpilog'})
    assert len(calls) == 1
    import os
    p = root / 'match.wpilog'
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 10))
    client.get('/api/index', params={'log': 'match.wpilog'})
    assert len(calls) == 2


# ── path safety / bad input ─────────────────────────────────────────────────────────────────────

def test_refuses_paths_outside_the_log_root(client):
    assert client.get('/api/index', params={'log': '../secret.wpilog'}).status_code in (400, 404)
    assert client.get('/api/index', params={'log': '..\\..\\Windows\\win.ini'}).status_code in (400, 404)


def test_unknown_and_unreadable_logs(client, root):
    assert client.get('/api/index', params={'log': 'nope.wpilog'}).status_code == 404
    (root / 'junk.wpilog').write_bytes(b'not a wpilog at all')
    r = client.get('/api/index', params={'log': 'junk.wpilog'})
    assert r.status_code == 422 and 'not a readable' in r.json()['detail']


def test_bad_plans_get_a_message_not_a_500(client):
    r = client.post('/api/preview', json=plan(segments=[]))
    assert r.status_code == 400 and 'no segments' in r.json()['detail']
    r = client.post('/api/preview', json=plan(segments=[{'start': 5, 'end': 1}]))
    assert r.status_code == 400 and 'after start' in r.json()['detail']
    r = client.post('/api/preview', json=plan(segments=[{'start': 500, 'end': 600}]))
    assert r.status_code == 400 and 'any data' in r.json()['detail']
    assert client.post('/api/preview', json={'log': 'match.wpilog'}).status_code == 422


# ── preview ─────────────────────────────────────────────────────────────────────────────────────

def test_preview_is_an_estimate_with_per_segment_detail(client):
    r = client.post('/api/preview', json=plan()).json()
    assert r['exact'] is False and 0 < r['output_bytes'] < r['source_bytes']
    assert r['saved_bytes'] == r['source_bytes'] - r['output_bytes']
    assert [s['label'] for s in r['segments']] == ['auto', 'auto'] and all(s['bytes'] > 0 for s in r['segments'])
    assert len(r['ranges']) == 2 and len(r['seams']) == 1 and r['gap_cycles'] == 10
    assert r['n_cycles_out'] == 110 and r['n_cycles_source'] == 550


def test_exact_preview_equals_what_export_writes(client, root):
    ex = client.post('/api/preview/exact', json=plan()).json()
    est = client.post('/api/preview', json=plan()).json()
    saved = client.post('/api/export', json={**plan(), 'mode': 'save'}).json()
    assert ex['exact'] is True and ex['output_bytes'] == saved['bytes'] == (root / saved['path']).stat().st_size
    assert abs(est['output_bytes'] - ex['output_bytes']) <= max(0.04 * ex['output_bytes'], 400)


def test_gap_and_policy_flow_through(client):
    a = client.post('/api/preview', json=plan(gap_ms=0)).json()
    b = client.post('/api/preview', json=plan(gap_ms=500)).json()
    assert a['n_cycles_out'] == 100 and b['n_cycles_out'] == 125
    c = client.post('/api/preview', json=plan(gap_policy='preserve')).json()
    first = c['segments'][0]['orig_first']            # in preserve mode 'new' is measured from the output's first cycle
    assert all(s['new_first'] == pytest.approx(s['orig_first'] - first) for s in c['segments'])


def test_exclusions_reduce_the_size_and_are_reported(client):
    base = client.post('/api/preview/exact', json=plan()).json()
    ex = client.post('/api/preview/exact', json=plan(exclude_prefixes=['/Vision'])).json()
    assert ex['output_bytes'] < base['output_bytes'] and ex['n_excluded_entries'] == 1 and ex['n_excluded_records'] > 0


# ── export ──────────────────────────────────────────────────────────────────────────────────────

def test_export_saves_next_to_the_source_and_verifies(client, root):
    r = client.post('/api/export', json={**plan(), 'mode': 'save'}).json()
    assert r['name'] == 'match_trimmed.wpilog' and r['verify']['ok'] is True and r['saved_pct'] > 50
    assert pathlib.Path(r['abs_path']) == (root / 'match_trimmed.wpilog').resolve() and pathlib.Path(r['abs_path']).is_file()
    out = (root / r['path']).read_bytes()
    assert [m for *_, m in build_index(out).mode_spans()] == ['auto', 'disabled', 'auto']


def test_export_never_overwrites(client, root):
    names = [client.post('/api/export', json={**plan(), 'mode': 'save'}).json()['name'] for _ in range(3)]
    assert names == ['match_trimmed.wpilog', 'match_trimmed_2.wpilog', 'match_trimmed_3.wpilog']
    assert (root / 'match.wpilog').exists()


def test_export_in_a_subfolder_stays_in_that_folder(client, root):
    r = client.post('/api/export', json={**plan(log='sub/other.wpilog'), 'mode': 'save'}).json()
    assert r['path'] == 'sub/other_trimmed.wpilog' and (root / 'sub' / 'other_trimmed.wpilog').exists()


@pytest.mark.parametrize('given,expected', [
    ('mine', 'mine.wpilog'), ('mine.wpilog', 'mine.wpilog'), ('../../evil', 'evil.wpilog'),
    ('a b/c:d*.wpilog', 'c_d_.wpilog'),
])
def test_export_file_names_are_sanitised(client, root, given, expected):
    r = client.post('/api/export', json={**plan(), 'mode': 'save', 'filename': given}).json()
    assert r['name'] == expected and (root / r['name']).exists()


def test_export_rejects_an_empty_name(client):
    assert client.post('/api/export', json={**plan(), 'filename': '  ..  '}).status_code == 400


def test_download_returns_the_bytes_and_writes_nothing(client, root):
    before = sorted(p.name for p in root.iterdir())
    r = client.post('/api/export', json={**plan(), 'mode': 'download'})
    assert r.status_code == 200 and 'attachment' in r.headers['content-disposition']
    assert 'match_trimmed.wpilog' in r.headers['content-disposition']
    assert sorted(p.name for p in root.iterdir()) == before
    assert 'Janitor/SegmentMap' in parse_wpilog_bytes(r.content)


def test_the_segment_map_records_the_plan(client, root):
    r = client.post('/api/export', json={**plan(gap_ms=300, exclude=['/Sensor/X']), 'mode': 'save'}).json()
    note = json.loads(parse_wpilog_bytes((root / r['path']).read_bytes())['Janitor/SegmentMap'][0][1])
    assert note['gap_ms'] == 300 and note['excluded_entries'] == ['/Sensor/X'] and note['source_file'] == 'match.wpilog'


def test_front_end_placeholder_when_not_built(client):
    r = client.get('/')
    assert r.status_code == 503 and 'npm run build' in r.text


def test_serves_the_built_front_end(root, tmp_path):
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<h1>hello</h1>')
    c = TestClient(server.create_app(root, dist=dist))
    assert c.get('/').text == '<h1>hello</h1>' and c.get('/api/logs').status_code == 200
