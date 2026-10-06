"""remote_config.py: the per-machine SSH config, including several Orange Pis."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: sys.path bridges)

from remote_config import load_remote_config

_RIO = {'host': 'roborio-1405-frc.local', 'user': 'lvuser', 'logs_path': '/home/lvuser/logs'}


def _pi(name=None, host='photonvision.local'):
    entry = {'host': host, 'user': 'pi', 'recordings_path': '/home/pi/vision-recordings'}
    if name is not None:
        entry['name'] = name
    return entry


def _load(tmp_path, body):
    path = tmp_path / 'remote.json'
    path.write_text(json.dumps(body), encoding='utf-8')
    return load_remote_config(path)


def test_missing_file_means_remote_fetch_is_not_configured(tmp_path):
    assert load_remote_config(tmp_path / 'nope.json') is None


def test_two_pis_each_keep_their_own_host_and_name(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO, 'pis': [_pi('LeftPi', 'leftpi.local'), _pi('RightPi', 'rightpi.local')]})
    assert [p.name for p in cfg.pis] == ['LeftPi', 'RightPi']
    assert cfg.pi_by_name('RightPi').host == 'rightpi.local'


def test_original_single_pi_form_still_loads(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO, 'pi': _pi()})
    assert len(cfg.pis) == 1
    assert cfg.pi_by_name('') is cfg.pis[0]  # a client with no Pi name still resolves it


def test_empty_pi_name_is_ambiguous_with_several_pis(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO, 'pis': [_pi('A'), _pi('B')]})
    with pytest.raises(KeyError, match='no Orange Pi named'):
        cfg.pi_by_name('')


def test_unknown_pi_name_lists_the_configured_ones(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO, 'pis': [_pi('A'), _pi('B')]})
    with pytest.raises(KeyError, match='A, B'):
        cfg.pi_by_name('C')


@pytest.mark.parametrize('body, message', [
    ({'rio': _RIO, 'pi': _pi(), 'pis': [_pi('A')]}, 'both "pi" and "pis"'),
    ({'rio': _RIO, 'pis': 'LeftPi'}, 'must be a list'),
    ({'rio': _RIO, 'pis': [_pi()]}, 'needs a "name"'),
    ({'rio': _RIO, 'pis': [_pi('A'), _pi('A')]}, 'unique'),
    ({'rio': _RIO, 'pis': [_pi('a|b')]}, 'may not contain'),
    ({'rio': _RIO, 'pi_discovery': {'enabled': False}}, 'nothing to fetch'),
    ({'rio': _RIO, 'pis': [], 'pi_discovery': {'enabled': False}}, 'nothing to fetch'),
    ({'rio': _RIO, 'pi_discovery': {'timeout_seconds': 0}}, 'greater than zero'),
    ({'pis': [_pi('A')]}, '"rio"'),
])
def test_bad_configs_are_rejected_with_a_clear_message(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        _load(tmp_path, body)


def test_no_pis_listed_is_fine_because_discovery_is_on_by_default(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO})
    assert cfg.pis == []
    assert cfg.discovery.enabled
    assert (cfg.discovery.user, cfg.discovery.recordings_path) == ('pi', '/home/pi/vision-recordings')


def test_discovery_defaults_can_be_overridden(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO, 'pi_discovery': {
        'user': 'orangepi', 'recordings_path': '/mnt/usb/rec', 'timeout_seconds': 3}})
    assert (cfg.discovery.user, cfg.discovery.recordings_path, cfg.discovery.timeout_seconds) ==         ('orangepi', '/mnt/usb/rec', 3.0)


def test_discovery_can_be_turned_off_when_pis_are_listed(tmp_path):
    cfg = _load(tmp_path, {'rio': _RIO, 'pis': [_pi('A')], 'pi_discovery': {'enabled': False}})
    assert not cfg.discovery.enabled and [p.name for p in cfg.pis] == ['A']
