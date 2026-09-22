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


# ── /api/content ────────────────────────────────────────────────────────────────────────────────

def _wave(k, f=0.37):
    return round(((k * f) % 7) - 3, 3)


@pytest.fixture
def content_root(tmp_path):
    """A log with: two identical series (input + its RealOutputs copy), a constant, an unrelated series, and
    a same-name pair whose data differs. 300 cycles = 6 s."""
    b = wb.LogBuilder()
    names = ['/Timestamp', '/Pickup/Velocity', '/RealOutputs/Pickup/Velocity', '/Cfg/Zero', '/Other/Wave',
             '/Twin/Thing', '/RealOutputs/Twin/Thing']
    for n in names:
        b.entry(n, 'int64' if n == '/Timestamp' else 'double', 1_000_000)
    for k in range(300):
        t = 1_000_000 + k * 20_000
        b.data('/Timestamp', t, wb.int64(t))
        b.data('/Pickup/Velocity', t, wb.double(_wave(k)))
        b.data('/Cfg/Zero', t, wb.double(0.0))
        b.data('/Other/Wave', t, wb.double(_wave(k, 0.11)))
        b.data('/Twin/Thing', t, wb.double(_wave(k, 0.5)))
        b.data('/RealOutputs/Twin/Thing', t, wb.double(_wave(k, 0.5) if k % 3 else 99.0))
        b.data('/RealOutputs/Pickup/Velocity', t + 3_000, wb.double(_wave(k)))     # same data, 3 ms later: last in the cycle to stay time-ordered
    (tmp_path / 'c.wpilog').write_bytes(b.build())
    return tmp_path


@pytest.fixture
def cclient(content_root):
    return TestClient(server.create_app(content_root, dist=None))


def _by_name(r):
    return {e['name']: e for e in r['entries']}


def test_content_describes_every_entry(cclient):
    r = cclient.post('/api/content', json={'log': 'c.wpilog'}).json()
    e = _by_name(r)
    assert len(r['entries']) == 7 and r['window']['whole_log'] is True
    assert sum(x['bytes'] for x in r['entries']) == r['window']['bytes']
    assert e['/Cfg/Zero']['constant'] is True and e['/Other/Wave']['constant'] is False
    assert e['/Other/Wave']['records'] == 300 and e['/Other/Wave']['hz'] == pytest.approx(300 / 5.98, rel=0.02)
    assert e['/Other/Wave']['num']['min'] == pytest.approx(-3) and e['/Cfg/Zero']['sample'] == '0'
    assert e['/Timestamp']['cls'] == 'structural' and e['/RealOutputs/Pickup/Velocity']['cls'] == 'output'
    assert r['constants'] == {'count': 1, 'bytes': e['/Cfg/Zero']['bytes']}


def test_content_finds_the_duplicate_and_the_twin_with_different_data(cclient):
    r = cclient.post('/api/content', json={'log': 'c.wpilog'}).json()
    e = {x['id']: x for x in r['entries']}
    (g,) = r['groups']
    assert g['kind'] == 'values' and g['weak'] is False and e[g['keeper']]['name'] == '/Pickup/Velocity'
    assert [e[i]['name'] for i in g['members'] if i != g['keeper']] == ['/RealOutputs/Pickup/Velocity']
    assert g['recoverable_bytes'] == e[[i for i in g['members'] if i != g['keeper']][0]]['bytes']
    (t,) = r['twins']
    assert t['key'] == 'Twin/Thing' and t['relation'] == 'different' and '66.' in t['note']


def test_protection_changes_labels_but_not_the_cached_analysis(cclient, monkeypatch):
    calls = []
    real = server.ct.analyze_content
    monkeypatch.setattr(server.ct, 'analyze_content', lambda *a, **k: calls.append(1) or real(*a, **k))
    both = cclient.post('/api/content', json={'log': 'c.wpilog', 'protect': ['replay', 'logbench']}).json()
    none = cclient.post('/api/content', json={'log': 'c.wpilog', 'protect': []}).json()
    only_replay = cclient.post('/api/content', json={'log': 'c.wpilog', 'protect': ['replay', 'nonsense']}).json()
    assert len(calls) == 1
    pick = lambda r: {x['name']: x['protected'] for x in r['entries']}
    assert pick(both)['/Pickup/Velocity'] and pick(none)['/Pickup/Velocity'] is None
    assert pick(both)['/Timestamp'] and pick(none)['/Timestamp']                    # structural: always
    assert pick(both)['/RealOutputs/Pickup/Velocity'] is None                        # regenerated by replay
    assert only_replay['protect'] == ['replay']                                      # unknown profiles are ignored


def test_protected_duplicates_are_blocked_only_under_the_profiles_that_cover_them(tmp_path):
    b = wb.LogBuilder()
    for n in ['/Timestamp', '/Vision/A/Raw', '/Vision/A/Copy']:
        b.entry(n, 'int64' if n == '/Timestamp' else 'double', 1_000_000)
    for k in range(120):
        t = 1_000_000 + k * 20_000
        b.data('/Timestamp', t, wb.int64(t))
        b.data('/Vision/A/Raw', t, wb.double(_wave(k)))
        b.data('/Vision/A/Copy', t, wb.double(_wave(k)))
    (tmp_path / 'v.wpilog').write_bytes(b.build())
    c = TestClient(server.create_app(tmp_path, dist=None))
    guarded = c.post('/api/content', json={'log': 'v.wpilog'}).json()
    open_ = c.post('/api/content', json={'log': 'v.wpilog', 'protect': []}).json()
    assert len(guarded['groups'][0]['blocked']) == 1 and guarded['groups'][0]['kind'] == 'identical'
    assert open_['groups'][0]['blocked'] == []


def test_content_window_covers_only_the_chosen_periods(cclient):
    whole = cclient.post('/api/content', json={'log': 'c.wpilog'}).json()
    part = cclient.post('/api/content', json={'log': 'c.wpilog', 'segments': [{'start': 1.0, 'end': 3.0}]}).json()
    assert part['window']['whole_log'] is False and part['window']['cycles'] == 100
    assert part['window']['seconds'] == pytest.approx(2.0, abs=0.05) and part['window']['bytes'] < whole['window']['bytes'] / 2
    assert _by_name(part)['/Other/Wave']['records'] == 100
    two = cclient.post('/api/content', json={'log': 'c.wpilog', 'segments': [{'start': 0.5, 'end': 1.5}, {'start': 4.0, 'end': 5.0}]}).json()
    assert two['window']['cycles'] == 50 + 5 + 5 + 50                                 # two 50-cycle periods + 5 real cycles kept each side of the cut
    assert _by_name(two)['/Other/Wave']['records'] == two['window']['cycles']


def test_content_bad_requests(cclient):
    assert cclient.post('/api/content', json={'log': 'nope.wpilog'}).status_code == 404
    r = cclient.post('/api/content', json={'log': 'c.wpilog', 'segments': [{'start': 500, 'end': 600}]})
    assert r.status_code == 400 and 'any data' in r.json()['detail']
    assert cclient.post('/api/content', json={}).status_code == 422
