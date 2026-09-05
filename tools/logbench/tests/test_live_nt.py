"""server/live_nt.py against a fake ntcore -- there is no real NT4 server in CI or in
this sandbox, so these exercise the same connect()/read()/disconnect() flow a real robot
connection would, with `_ntcore` injected instead of the real package (which may not even
be installed -- see the module docstring's note on why the import is lazy)."""
import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import live_nt


class FakeTopic:
    def __init__(self, path, default):
        self.path = path
        self.value = default

    def subscribe(self, default):
        return FakeSubscriber(self)

    def exists(self):
        return True


class FakeSubscriber:
    def __init__(self, topic):
        self.topic = topic

    def get(self):
        return self.topic.value

    def getLastChange(self):
        return 1


class FakeInst:
    def __init__(self):
        self.topics = {}
        self.connected = True

    def isConnected(self):
        return self.connected

    def addConnectionListener(self, immediate, cb):
        return 'handle'

    def startClient4(self, name):
        pass

    def setServerTeam(self, n):
        pass

    def setServer(self, s):
        pass

    def removeListener(self, h):
        pass

    def stopClient(self):
        pass

    def _topic(self, path, default):
        if path not in self.topics:
            self.topics[path] = FakeTopic(path, default)
        return self.topics[path]

    def getBooleanTopic(self, path):
        return self._topic(path, False)

    def getDoubleTopic(self, path):
        return self._topic(path, 0.0)

    def getStringTopic(self, path):
        return self._topic(path, '')

    def getIntegerArrayTopic(self, path):
        return self._topic(path, [])


def _fake_ntcore(inst: FakeInst):
    return types.SimpleNamespace(
        NetworkTableInstance=types.SimpleNamespace(getDefault=lambda: inst),
        EventFlags=types.SimpleNamespace(kConnected=1),
        _now=lambda: 2,
    )


@pytest.fixture(autouse=True)
def _disconnect_after():
    yield
    live_nt.disconnect()


def _set(inst: FakeInst, camera: str, suffix: str, value):
    inst.topics[f'/AdvantageKit/RealOutputs/Vision/{camera}/Health/{suffix}'].value = value


def test_read_returns_empty_before_connecting():
    assert live_nt.read() == {}


def test_connect_then_read_relays_the_robots_own_score():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', _ntcore=_fake_ntcore(inst))
    _set(inst, 'Left', 'ScorePercent', 87.5)
    snapshot = live_nt.read()
    assert snapshot['nt_connected'] is True
    assert snapshot['cameras']['Left']['health_score'] == 87.5


def test_motion_score_is_computed_from_the_live_factor_percentages():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', _ntcore=_fake_ntcore(inst))
    for suffix in ('AreaPercent', 'AmbiguityPercent', 'FpsPercent',
                   'AcceptanceRateFactorPercent', 'LatencyPercent', 'MultiTagRatioPercent'):
        _set(inst, 'Left', suffix, 100.0)
    # Stillness/jitter are deliberately left at their connect-time defaults (0.0) --
    # motion_score must ignore them entirely.
    snapshot = live_nt.read()
    assert snapshot['cameras']['Left']['motion_score'] == pytest.approx(100.0)


def test_motion_score_is_none_when_a_dependency_is_nan():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', _ntcore=_fake_ntcore(inst))
    _set(inst, 'Left', 'AreaPercent', float('nan'))
    snapshot = live_nt.read()
    assert snapshot['cameras']['Left']['motion_score'] is None


def test_connect_is_a_no_op_with_unchanged_settings():
    inst = FakeInst()
    ntcore = _fake_ntcore(inst)
    live_nt.connect('10.14.5.2', _ntcore=ntcore)
    _set(inst, 'Left', 'ScorePercent', 42.0)
    live_nt.connect('10.14.5.2', _ntcore=ntcore)  # same params -- must not re-subscribe
    assert live_nt.read()['cameras']['Left']['health_score'] == 42.0


def test_disconnect_makes_read_return_empty_again():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', _ntcore=_fake_ntcore(inst))
    live_nt.disconnect()
    assert live_nt.read() == {}
