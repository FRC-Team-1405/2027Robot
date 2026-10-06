"""pi_discovery.py: finding the Orange Pis from NetworkTables. ntcore is replaced by a small
fake, so nothing here needs a robot, a network, or pyntcore's real client."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: sys.path bridges)

import pi_discovery
import remote_config
from pi_discovery import DiscoveredPi, DiscoveryError, discover_via_nt, merge_pis, resolve_pis
from remote_config import DiscoveryConfig, HostConfig, RemoteConfig


# ── a stand-in for ntcore ───────────────────────────────────────────────────────────

class _Sub:
    def __init__(self, tree, path):
        self._tree, self._path = tree, path

    def get(self):
        return self._tree.get(self._path, '')


class _Topic:
    def __init__(self, tree, path):
        self._tree, self._path = tree, path

    def subscribe(self, default):
        return _Sub(self._tree, self._path)


class _Table:
    def __init__(self, tree):
        self._tree = tree

    def getSubTables(self):
        return sorted({p.split('/')[2] for p in self._tree if p.startswith('/OrangePi/') and p.count('/') >= 3})


class _Inst:
    def __init__(self, tree, connected):
        self.tree, self.connected, self.server, self.stopped = tree, connected, None, False

    def startClient4(self, name):
        self.client = name

    def setServerTeam(self, team):
        self.server = ('team', team)

    def setServer(self, host):
        self.server = ('host', host)

    def isConnected(self):
        return self.connected

    def getTable(self, name):
        return _Table(self.tree)

    def getStringTopic(self, path):
        return _Topic(self.tree, path)

    def stopClient(self):
        self.stopped = True


class _FakeNt:
    """tree maps '/OrangePi/<board>/<field>' -> value."""
    def __init__(self, tree, connected=True):
        self.instance = _Inst(tree, connected)
        self.destroyed = False
        fake = self

        class NetworkTableInstance:
            @staticmethod
            def create():
                return fake.instance

            @staticmethod
            def destroy(inst):
                fake.destroyed = True

        class MultiSubscriber:
            def __init__(self, inst, prefixes):
                fake.prefixes = prefixes

            def close(self):
                pass

        self.NetworkTableInstance, self.MultiSubscriber = NetworkTableInstance, MultiSubscriber


def _two_boards():
    return {
        '/OrangePi/LeftPi/CPU_Pct': 11.0,
        '/OrangePi/LeftPi/IP': '10.14.5.21', '/OrangePi/LeftPi/Host': 'photonvision.local',
        '/OrangePi/RightPi/IP': '10.14.5.22', '/OrangePi/RightPi/Host': 'photonvision.local',
    }


def _discover(tree, connected=True, **kw):
    nt = _FakeNt(tree, connected)
    kw = {'timeout': 1.0, 'settle': 0.05, 'poll': 0.01, **kw}
    return nt, discover_via_nt('roborio-1405-frc.local', _ntcore=nt, **kw)


# ── discover_via_nt ─────────────────────────────────────────────────────────────────

def test_finds_every_board_with_its_name_and_address():
    nt, found = _discover(_two_boards())
    assert [(d.name, d.ip, d.host) for d in found] == [
        ('LeftPi', '10.14.5.21', 'photonvision.local'), ('RightPi', '10.14.5.22', 'photonvision.local')]
    assert nt.prefixes == ['/OrangePi/']


def test_names_are_whatever_the_boards_publish_not_left_and_right():
    _, found = _discover({'/OrangePi/Front/IP': '10.0.0.5', '/OrangePi/rear/IP': '10.0.0.6'})
    assert [d.name for d in found] == ['Front', 'rear']


def test_a_board_that_publishes_no_address_is_still_reported():
    _, found = _discover({'/OrangePi/OldPi/CPU_Pct': 3.0})
    assert [(d.name, d.address) for d in found] == [('OldPi', '')]


def test_ip_is_preferred_over_the_hostname():
    assert DiscoveredPi('A', ip='10.0.0.5', host='photonvision.local').address == '10.0.0.5'
    assert DiscoveredPi('A', host='photonvision.local').address == 'photonvision.local'


def test_nothing_published_means_an_empty_result_not_an_error():
    _, found = _discover({})
    assert found == []


def test_server_that_never_answers_is_an_error_naming_the_server():
    with pytest.raises(DiscoveryError, match='roborio-1405-frc.local'):
        _discover(_two_boards(), connected=False, timeout=0.1)


def test_a_team_number_is_treated_as_a_team_not_a_host():
    nt = _FakeNt({})
    discover_via_nt('1405', timeout=0.2, settle=0.05, poll=0.01, _ntcore=nt)
    assert nt.instance.server == ('team', 1405)


def test_the_throwaway_client_is_always_shut_down():
    nt, _ = _discover(_two_boards())
    assert nt.instance.stopped and nt.destroyed


# ── merge_pis ───────────────────────────────────────────────────────────────────────

_DEFAULTS = DiscoveryConfig(user='pi', recordings_path='/home/pi/vision-recordings')


def _host(name, host, path='/custom'):
    return HostConfig(host=host, user='me', path=path, name=name)


def test_discovered_pis_use_the_discovery_defaults():
    pis, notes = merge_pis([], [DiscoveredPi('LeftPi', ip='10.14.5.21')], _DEFAULTS)
    [pi] = pis
    assert (pi.name, pi.host, pi.user, pi.path) == ('LeftPi', '10.14.5.21', 'pi', '/home/pi/vision-recordings')
    assert 'LeftPi (10.14.5.21)' in notes[0]


def test_a_hand_listed_pi_wins_over_a_discovered_one_of_the_same_name_ignoring_case():
    pis, _ = merge_pis([_host('leftpi', 'pinned.local')], [DiscoveredPi('LeftPi', ip='10.14.5.21')], _DEFAULTS)
    assert [(p.name, p.host, p.path) for p in pis] == [('leftpi', 'pinned.local', '/custom')]


def test_a_hand_listed_pi_at_the_same_address_is_the_same_pi_and_takes_the_discovered_name():
    legacy = _host('', 'photonvision.local')  # the old single "pi" entry has no name
    pis, _ = merge_pis([legacy], [DiscoveredPi('LeftPi', host='photonvision.local')], _DEFAULTS)
    assert [(p.name, p.host) for p in pis] == [('LeftPi', 'photonvision.local')]


def test_a_discovered_pi_without_an_address_is_skipped_with_a_note_saying_why():
    pis, notes = merge_pis([], [DiscoveredPi('OldPi')], _DEFAULTS)
    assert pis == []
    assert 'OldPi' in notes[0] and 'orangepi-nt-publisher.py' in notes[0]


# ── resolve_pis ─────────────────────────────────────────────────────────────────────

def _cfg(pis=(), enabled=True):
    return RemoteConfig(
        rio=HostConfig(host='rio.local', user='lvuser', path='/logs'), pis=list(pis),
        source_path=pathlib.Path('remote_config.json'), discovery=DiscoveryConfig(enabled=enabled))


def test_discovery_off_returns_only_the_listed_pis_and_never_touches_nt(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('NetworkTables must not be queried')
    monkeypatch.setattr(pi_discovery, 'discover_via_nt', boom)
    res = resolve_pis(_cfg([_host('A', 'a.local')], enabled=False))
    assert [p.name for p in res.pis] == ['A'] and res.notes == []


def test_discovery_failure_falls_back_to_the_listed_pis_and_says_so(monkeypatch):
    def fail(*a, **k):
        raise DiscoveryError('timed out')
    monkeypatch.setattr(pi_discovery, 'discover_via_nt', fail)
    res = resolve_pis(_cfg([_host('A', 'a.local')]))
    assert [p.name for p in res.pis] == ['A']
    assert 'timed out' in res.notes[0] and 'remote_config.json' in res.notes[0]


def test_discovery_failure_with_nothing_listed_gives_no_pis_and_an_explanation(monkeypatch):
    def fail(*a, **k):
        raise DiscoveryError('no route')
    monkeypatch.setattr(pi_discovery, 'discover_via_nt', fail)
    res = resolve_pis(_cfg())
    assert res.pis == []
    assert 'no vision recordings can be fetched' in res.notes[0]


def test_download_time_reuses_the_listing_time_answer(monkeypatch):
    calls = []

    def fake(server, timeout):
        calls.append(server)
        return [DiscoveredPi('LeftPi', ip='10.14.5.21')]
    monkeypatch.setattr(pi_discovery, 'discover_via_nt', fake)

    listed = resolve_pis(_cfg(), refresh=True)
    fetched = resolve_pis(_cfg(), refresh=False)
    assert calls == ['rio.local']          # queried once, not again for the download
    assert fetched.pis == listed.pis
