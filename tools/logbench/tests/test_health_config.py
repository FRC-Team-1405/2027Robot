"""health/config.py: the TOML vocabulary is strict, errors are per check, and the shipped file is valid."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from health import config

SHIPPED = pathlib.Path(__file__).resolve().parents[1] / 'server' / 'health_checks.toml'


def test_a_minimal_check_gets_the_defaults():
    specs, errors = config.parse('''
[[check]]
id = "a"
section = "S"
label = "A"
signal = "X/Y"
''')
    assert errors == []
    [c] = specs
    assert (c.measure, c.window, c.scale, c.mode, c.missing, c.severity) == ('last', 'all', 1.0, 'both', 'nodata', 'fail')
    assert not c.has_rules and not c.has_expect


def test_every_documented_field_parses():
    specs, errors = config.parse('''
[[check]]
id = "a"
section = "S"
group = "G {1}"
subject = "{name}"
label = "L"
signal = "P/*/Q"
lookup = { name = "P/{1}/Name" }
unit = "%"
scale = 100
measure = "seconds_above"
above = 5
window = "enabled"
warn_above = 1
fail_above = 2
warn_below = -1
fail_below = -2
expect_in = ["a", "b"]
severity = "warn"
stale_after = 3
missing = "ok"
expect_items = ["x"]
mode = "log"
help = "h"
decimals = 1
''')
    assert errors == []
    [c] = specs
    assert dict(c.lookup) == {'name': 'P/{1}/Name'} and c.expect_in == ('a', 'b') and c.expect_items == ('x',)
    assert c.has_rules


def test_expect_false_is_a_rule_not_an_absent_one():
    [c], errors = config.parse('[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nexpect = false\n')
    assert errors == [] and c.has_expect and c.expect is False and c.has_rules


def test_defaults_apply_to_every_check_and_a_check_can_override_them():
    specs, errors = config.parse('''
[defaults]
missing = "fail"
window = "enabled"
[[check]]
id = "a"
section = "S"
label = "A"
signal = "X"
[[check]]
id = "b"
section = "S"
label = "B"
signal = "Y"
window = "all"
''')
    assert errors == []
    assert [(s.missing, s.window) for s in specs] == [('fail', 'enabled'), ('fail', 'all')]


def test_a_misspelled_field_is_reported_not_ignored():
    specs, errors = config.parse('[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nwarn_abve = 70\n')
    assert specs == []
    assert len(errors) == 1 and 'warn_abve' in errors[0] and 'a:' in errors[0]


def test_each_kind_of_mistake_has_a_message_naming_the_check():
    bad = [
        ('missing required', '[[check]]\nid="a"\nsection="S"\nlabel="L"\n', "signal"),
        ('bad measure', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nmeasure="avg"\n', 'measure'),
        ('bad window', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nwindow="match"\n', 'window'),
        ('wrong type', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nwarn_above="high"\n', 'wrong type'),
        ('bool as number', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nscale=true\n', 'true/false'),
        ('seconds_above needs above', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nmeasure="seconds_above"\n', 'above'),
        ('equals needed', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nmeasure="fraction_equals"\n', 'equals'),
        ('both expects', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nexpect=1\nexpect_in=["a"]\n', 'either expect'),
        ('zero scale', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nscale=0\n', 'scale'),
        ('items need star', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nexpect_items=["a"]\n', '`*`'),
        ('bad lookup', '[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\nlookup={ "bad name" = "Y" }\n', 'lookup'),
    ]
    for what, text, needle in bad:
        specs, errors = config.parse(text)
        assert specs == [] and len(errors) == 1, what
        assert needle in errors[0] and errors[0].startswith('a'), (what, errors)


def test_one_bad_check_does_not_stop_the_others_and_duplicates_are_caught():
    specs, errors = config.parse('''
[[check]]
id = "good"
section = "S"
label = "G"
signal = "X"
[[check]]
id = "bad"
section = "S"
label = "B"
signal = "Y"
measure = "nope"
[[check]]
id = "good"
section = "S"
label = "again"
signal = "Z"
''')
    assert [s.id for s in specs] == ['good']
    assert len(errors) == 2 and any('duplicate' in e for e in errors)


def test_unknown_top_level_entries_and_bad_toml_are_reported():
    _, errors = config.parse('[checks]\nx = 1\n')
    assert any('checks' in e for e in errors)
    specs, errors = config.parse('this is = = not toml')
    assert specs == [] and 'not valid TOML' in errors[0]


def test_load_rereads_the_file_when_it_changes(tmp_path):
    f = tmp_path / 'h.toml'
    f.write_text('[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\n')
    assert [s.id for s in config.load(f)[0]] == ['a']
    f.write_text('[[check]]\nid="a"\nsection="S"\nlabel="L"\nsignal="X"\n[[check]]\nid="b"\nsection="S"\nlabel="L"\nsignal="Y"\n')
    import os
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))      # a filesystem with coarse mtimes
    assert [s.id for s in config.load(f)[0]] == ['a', 'b']


def test_load_reports_a_missing_file(tmp_path):
    specs, errors = config.load(tmp_path / 'nope.toml')
    assert specs == [] and 'cannot read' in errors[0]


def test_the_shipped_configuration_is_valid():
    specs, errors = config.parse(SHIPPED.read_text(encoding='utf-8'))
    assert errors == []
    assert len(specs) >= 40
    sections = {s.section for s in specs}
    assert {'Vision', 'Orange Pis', 'roboRIO', 'Robot'} <= sections
    assert len({s.id for s in specs}) == len(specs)
