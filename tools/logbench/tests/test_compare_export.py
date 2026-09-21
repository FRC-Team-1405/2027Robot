"""compare_export.py and /api/compare/export: the HTML report and the LLM-facing JSON are
both rendered from one report dict built from core.compare's output, so these tests pin the
things a reader relies on: file names only (no paths), verdicts/values matching compare(),
every registered metric documented, and the two endpoints agreeing with /api/compare."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import compare_export
import main
from core.compare import WindowSelector, compare, make_run
from core.composites import COMPOSITES
from core.log import Log
from core.metrics import METRICS
from fastapi.testclient import TestClient

DS = {
    'DriverStation/Enabled': [(0.0, True), (10.0, True)],
    'DriverStation/Autonomous': [(0.0, True)],
}


def _log(name: str, still: float, left_only: bool = False) -> Log:
    signals = dict(DS)
    signals['Vision/Left/Health/FpsPercent'] = [(1.0, still)]
    if not left_only:
        signals['Vision/Right/Health/FpsPercent'] = [(1.0, still)]
    return Log(path=pathlib.Path(name), signals=signals)


def _report(a_label='offseason/6-13/a.wpilog', b_label='C:\\logs\\b.wpilog', **kw):
    run_a = make_run(_log('a.wpilog', 50.0), WindowSelector(mode='auto'), label=a_label)
    run_b = make_run(_log('b.wpilog', 90.0, left_only=True), WindowSelector(mode='auto'), label=b_label)
    cameras = ['Left', 'Right']
    metrics = ['fps_pct', 'motion_score']
    deltas = compare(run_a, run_b, metrics, cameras)
    return compare_export.build_report(
        run_a, run_b, deltas, cameras, metrics,
        mode='auto', manual_a=False, manual_b=kw.get('manual_b', False))


def test_every_registered_metric_and_composite_has_a_description():
    missing = [i for i in list(METRICS) + list(COMPOSITES) if not compare_export.DESCRIPTIONS.get(i)]
    assert missing == []


def test_report_records_file_names_only_for_both_logs():
    r = _report()
    assert r['logs']['a']['file'] == 'a.wpilog'
    assert r['logs']['b']['file'] == 'b.wpilog'
    dumped = compare_export.render_json(r)
    assert 'offseason' not in dumped and 'C:' not in dumped and '\\\\' not in dumped


def test_comparisons_match_core_compare_and_add_pct_change():
    r = _report()
    row = next(c for c in r['comparisons'] if c['metric'] == 'fps_pct' and c['camera'] == 'Left')
    assert (row['a'], row['b'], row['delta'], row['pct_change'], row['verdict']) == \
        (50.0, 90.0, 40.0, 80.0, 'improved')


def test_missing_camera_data_is_null_and_na_not_zero():
    r = _report()
    row = next(c for c in r['comparisons'] if c['metric'] == 'fps_pct' and c['camera'] == 'Right')
    assert row['a'] == 50.0 and row['b'] is None
    assert row['delta'] is None and row['pct_change'] is None and row['verdict'] == 'n/a'


def test_summary_tallies_add_up():
    r = _report()
    total = len(r['comparisons'])
    assert sum(r['summary']['overall'].values()) == total
    assert sum(sum(v.values()) for v in r['summary']['by_camera'].values()) == total


def test_window_selection_is_recorded_for_reproducibility():
    r = _report(manual_b=True)
    assert r['logs']['a']['window']['selection'] == 'mode:auto'
    assert r['logs']['b']['window']['selection'] == 'manual'


def test_composites_list_their_dependencies_and_metrics_carry_direction():
    r = _report()
    by_id = {m['id']: m for m in r['metrics']}
    assert by_id['motion_score']['kind'] == 'composite'
    assert 'area_pct' in by_id['motion_score']['depends_on']
    assert by_id['fps_pct']['lower_is_better'] is False


def test_json_is_valid_and_carries_schema_and_reading_guide():
    payload = json.loads(compare_export.render_json(_report()))
    assert payload['schema'] == compare_export.SCHEMA
    assert payload['how_to_read'] and payload['verdict_rule']['threshold_ratio'] == 0.10


def test_html_shows_what_the_page_shows_and_escapes_log_names():
    r = _report(a_label='<img src=x onerror=alert(1)>.wpilog')
    page = compare_export.render_html(r)
    assert '<script' not in page and '<img' not in page  # no scripts, and the name is escaped
    assert '&lt;img src=x onerror=alert(1)&gt;.wpilog' in page
    assert '50.0 %' in page and '90.0 %' in page and '40.0 %' in page  # same fmt() as the page
    assert 'verdict--improved' in page and 'verdict--na' in page
    assert 'window [' in page


# ─── endpoint ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch, tmp_path):
    (tmp_path / 'a.wpilog').write_bytes(b'')
    (tmp_path / 'b.wpilog').write_bytes(b'')
    fixtures = {'a.wpilog': _log('a.wpilog', 50.0), 'b.wpilog': _log('b.wpilog', 90.0)}
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    monkeypatch.setattr(main, '_load_log', lambda path: fixtures[path.name])
    return TestClient(main.app)


PARAMS = {'log_a': 'a.wpilog', 'log_b': 'b.wpilog', 'mode': 'auto',
          'metric': ['fps_pct'], 'camera': ['Left']}


def test_export_json_endpoint_agrees_with_the_compare_endpoint(client):
    shown = client.get('/api/compare', params=PARAMS).json()['deltas']
    r = client.get('/api/compare/export', params={**PARAMS, 'format': 'json'})
    assert r.status_code == 200
    assert 'attachment' in r.headers['content-disposition'] and r.headers['content-disposition'].endswith('.json"')
    exported = r.json()['comparisons']
    assert [(d['id'], d['camera'], d['verdict']) for d in shown] == \
        [(c['metric'], c['camera'], c['verdict']) for c in exported]


def test_export_html_endpoint_returns_a_downloadable_page(client):
    r = client.get('/api/compare/export', params={**PARAMS, 'format': 'html'})
    assert r.status_code == 200 and r.headers['content-type'].startswith('text/html')
    assert 'compare-a-vs-b.html' in r.headers['content-disposition']
    assert 'a.wpilog' in r.text and 'b.wpilog' in r.text


def test_export_rejects_unknown_format_and_unknown_metric(client):
    assert client.get('/api/compare/export', params={**PARAMS, 'format': 'csv'}).status_code == 422
    bad = client.get('/api/compare/export', params={**PARAMS, 'metric': ['nope']})
    assert bad.status_code == 400 and 'nope' in bad.json()['detail']


# ─── categories (docs/adr/0001, D1) ────────────────────────────────────────────────────

def _category_report():
    def log(name, rng):
        signals = dict(DS)
        signals['Vision/Left/Health/FpsPercent'] = [(1.0, 80.0)]
        signals['Vision/Left/RawAvgDistancesMeters'] = [(1.0, [rng, rng])]
        signals['Drivetrain/Speeds/vxMetersPerSecond'] = [(1.0, 1.0)]
        return Log(path=pathlib.Path(name), signals=signals)

    run_a = make_run(log('a.wpilog', 3.0), WindowSelector(mode='auto'), label='a.wpilog')
    run_b = make_run(log('b.wpilog', 1.0), WindowSelector(mode='auto'), label='b.wpilog')
    metrics = ['fps_pct', 'range_median_m', 'speed_mean_mps', 'motion_score']
    deltas = compare(run_a, run_b, metrics, ['Left'])
    return compare_export.build_report(run_a, run_b, deltas, ['Left'], metrics,
                                       mode='auto', manual_a=False, manual_b=False)


def test_report_is_schema_v2_and_carries_the_category_definitions():
    r = _category_report()
    assert r['schema'] == 'logbench.compare/v2'
    ids = [c['id'] for c in r['categories']]
    assert ids == ['availability', 'quality', 'context']
    context = next(c for c in r['categories'] if c['id'] == 'context')
    assert context['scored'] is False and context['question'] and context['low_means']


def test_every_metric_in_the_report_names_its_category():
    r = _category_report()
    by_id = {m['id']: m['category'] for m in r['metrics']}
    assert by_id == {'fps_pct': 'availability', 'range_median_m': 'context',
                     'speed_mean_mps': 'context', 'motion_score': 'legacy'}


def test_context_rows_are_not_judged_and_are_tallied_separately():
    r = _category_report()
    rows = {c['metric']: c for c in r['comparisons']}
    assert rows['range_median_m']['verdict'] == 'context'
    assert rows['speed_mean_mps']['camera'] == 'All'
    assert r['summary']['overall']['context'] == 2
    assert r['summary']['by_category']['context']['context'] == 2
    assert r['summary']['by_category']['availability']['context'] == 0
    assert sum(r['summary']['overall'].values()) == len(r['comparisons'])


def test_html_groups_rows_by_category_and_marks_context_as_not_scored():
    page = compare_export.render_html(_category_report())
    section = lambda cid: page.index('<section class="cat cat--%s">' % cid)
    assert section('availability') < section('context') < section('legacy')
    assert 'not scored' in page and 'verdict--context' in page
    assert 'Legacy composites' in page


def test_metric_catalog_endpoint_exposes_categories_and_descriptions():
    catalog = TestClient(main.app).get('/api/metric-catalog').json()
    assert [c['id'] for c in catalog['categories']] == ['availability', 'quality', 'context']
    by_id = {m['id']: m for m in catalog['metrics']}
    assert by_id['tag_in_view_pct']['category'] == 'availability'
    assert by_id['speed_mean_mps']['perCamera'] is False
    assert all(m['category'] and m['description'] for m in by_id.values())
    assert set(catalog['defaults']) <= set(by_id)
