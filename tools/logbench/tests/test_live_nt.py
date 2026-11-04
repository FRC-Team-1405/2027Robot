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

    # Generic access, for the Health Check snapshot.
    def getTopics(self, prefix):
        return [types.SimpleNamespace(getName=lambda n=n: n) for n in sorted(self.generic) if n.startswith(prefix)]

    def getEntry(self, name):
        self.entry_requests = getattr(self, 'entry_requests', 0) + 1
        return FakeEntry(self.generic[name])

    generic = {}


class FakeValue:
    def __init__(self, value, stamp):
        self._value, self._stamp = value, stamp

    def isValid(self):
        return self._value is not None

    def value(self):
        return self._value

    def time(self):
        return self._stamp


class FakeEntry:
    def __init__(self, value):
        self._v = value

    def getValue(self):
        return FakeValue(*self._v)


class FakeMulti:
    closed = False
    made = []

    def __init__(self, inst, prefixes, options=None):
        self.prefixes = list(prefixes)
        self.options = options
        FakeMulti.last = self
        FakeMulti.made.append(self)

    def close(self):
        FakeMulti.closed = True


class FakePoller:
    """Delivers one value event per subscribed topic that has a value, like kImmediate does."""

    def __init__(self, inst):
        self.inst, self.subs = inst, []

    def addListener(self, sub, mask):
        self.subs.append(sub)
        self.sent = False

    def readQueue(self):
        if self.sent:
            return []
        self.sent = True
        out = []
        for name, value in sorted(self.inst.generic.items()):
            if value[0] is not None and any(name.startswith(p) for s in self.subs for p in s.prefixes):
                out.append(types.SimpleNamespace(data=types.SimpleNamespace(
                    topic=types.SimpleNamespace(getName=lambda n=name: n), value=FakeValue(*value))))
        return out

    def close(self):
        pass


def _fake_ntcore(inst: FakeInst):
    return types.SimpleNamespace(
        NetworkTableInstance=types.SimpleNamespace(getDefault=lambda: inst),
        EventFlags=types.SimpleNamespace(kConnected=1, kValueAll=2, kImmediate=4),
        MultiSubscriber=FakeMulti,
        NetworkTableListenerPoller=FakePoller,
        PubSubOptions=lambda **kw: types.SimpleNamespace(**kw),
        _now=lambda: 10_000_000,
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
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=_fake_ntcore(inst))
    _set(inst, 'Left', 'ScorePercent', 87.5)
    snapshot = live_nt.read()
    assert snapshot['nt_connected'] is True
    assert snapshot['cameras']['Left']['health_score'] == 87.5


def test_motion_score_is_computed_from_the_live_factor_percentages():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=_fake_ntcore(inst))
    for suffix in ('AreaPercent', 'AmbiguityPercent', 'FpsPercent',
                   'AcceptanceRateFactorPercent', 'LatencyPercent', 'MultiTagRatioPercent'):
        _set(inst, 'Left', suffix, 100.0)
    # Stillness/jitter are deliberately left at their connect-time defaults (0.0) --
    # motion_score must ignore them entirely.
    snapshot = live_nt.read()
    assert snapshot['cameras']['Left']['motion_score'] == pytest.approx(100.0)


def test_motion_score_is_none_when_a_dependency_is_nan():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=_fake_ntcore(inst))
    _set(inst, 'Left', 'AreaPercent', float('nan'))
    snapshot = live_nt.read()
    assert snapshot['cameras']['Left']['motion_score'] is None


def test_connect_is_a_no_op_with_unchanged_settings():
    inst = FakeInst()
    ntcore = _fake_ntcore(inst)
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=ntcore)
    _set(inst, 'Left', 'ScorePercent', 42.0)
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=ntcore)  # same params -- must not re-subscribe
    assert live_nt.read()['cameras']['Left']['health_score'] == 42.0


def test_disconnect_makes_read_return_empty_again():
    inst = FakeInst()
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=_fake_ntcore(inst))
    live_nt.disconnect()
    assert live_nt.read() == {}


# ---- Health Check snapshot ------------------------------------------------------------------------------

def _snapshot_inst():
    inst = FakeInst()
    inst.generic = {
        '/AdvantageKit/SystemStats/CANBus/Utilization': (0.31, 9_000_000),
        '/AdvantageKit/RealOutputs/Vision/Left/Health/ScorePercent': (80.0, 9_900_000),
        '/AdvantageKit/DriverStation/Enabled': (True, 9_999_000),
        '/AdvantageKit/Alerts/errors': ([], 9_999_000),
        '/OrangePi/LeftPi/CPU_Pct': (12.5, 9_500_000),
        '/OrangePi/LeftPi/Recorders/LeftCam/State': ('idle', 9_900_000),
        '/Other/Thing': (1, 9_900_000),            # outside every prefix: not read
        '/AdvantageKit/Never/Published': (None, 0),  # invalid value: skipped
        '/AdvantageKit/Vision/Left/RawEstimatedPoses': ([1, 2, 3], 9_999_000),  # no check reads it
    }
    return inst


# What the snapshot tests' "health_checks.toml" reads; `*` and a lookup's {1} are one segment.
SIGNALS = ['SystemStats/CANBus/Utilization', 'Vision/*/Health/ScorePercent', 'Alerts/errors',
           'OrangePi/*/CPU_Pct', 'OrangePi/{1}/Recorders/*/State', 'Never/Published']


def test_health_snapshot_is_empty_when_not_connected():
    assert live_nt.health_snapshot() == {}


def test_health_snapshot_uses_log_style_keys_and_reports_ages():
    inst = _snapshot_inst()
    ntcore = _fake_ntcore(inst)
    live_nt.set_health_signals(SIGNALS)
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=ntcore)
    snap = live_nt.health_snapshot(_ntcore=ntcore)
    assert set(snap) == {
        'SystemStats/CANBus/Utilization', 'RealOutputs/Vision/Left/Health/ScorePercent',
        'DriverStation/Enabled', 'Alerts/errors', 'OrangePi/LeftPi/CPU_Pct',
        'OrangePi/LeftPi/Recorders/LeftCam/State'}
    assert snap['SystemStats/CANBus/Utilization'][0] == 0.31
    assert snap['SystemStats/CANBus/Utilization'][1] == pytest.approx(1.0)     # (10.0 s - 9.0 s)
    assert snap['OrangePi/LeftPi/CPU_Pct'][1] == pytest.approx(0.5)


def test_names_are_discovered_topics_only_and_only_under_the_checks_prefixes():
    # On 10-27 the old client subscribed to every AdvantageKit value and then once more per topic,
    # and each connect delayed both cameras' results to robot code by 100-280 ms (learning 8).
    inst = _snapshot_inst()
    ntcore = _fake_ntcore(inst)
    FakeMulti.made = []
    live_nt.set_health_signals(SIGNALS)
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=ntcore)
    names_sub = FakeMulti.made[-1]
    assert names_sub.options.topicsOnly is True
    # each check's path up to its first `*`, with and without RealOutputs/, plus the Pis' own table
    assert names_sub.prefixes == [
        '/AdvantageKit/Alerts/errors', '/AdvantageKit/DriverStation/Autonomous',
        '/AdvantageKit/DriverStation/Enabled', '/AdvantageKit/Never/Published', '/AdvantageKit/OrangePi/',
        '/AdvantageKit/RealOutputs/Alerts/errors', '/AdvantageKit/RealOutputs/DriverStation/Autonomous',
        '/AdvantageKit/RealOutputs/DriverStation/Enabled', '/AdvantageKit/RealOutputs/Never/Published',
        '/AdvantageKit/RealOutputs/OrangePi/', '/AdvantageKit/RealOutputs/SystemStats/CANBus/Utilization',
        '/AdvantageKit/RealOutputs/Vision/', '/AdvantageKit/SystemStats/CANBus/Utilization',
        '/AdvantageKit/Vision/', '/OrangePi/']


def test_values_come_from_one_subscription_to_exactly_the_checked_topics():
    inst = _snapshot_inst()
    ntcore = _fake_ntcore(inst)
    live_nt.set_health_signals(SIGNALS)
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=ntcore)
    FakeMulti.made = []
    inst.entry_requests = 0
    snap = live_nt.health_snapshot(_ntcore=ntcore)
    live_nt.health_snapshot(_ntcore=ntcore)
    assert inst.entry_requests == 0                 # no per-topic subscriptions at all
    assert len(FakeMulti.made) == 1                 # one value subscription, not rebuilt every poll
    values_sub = FakeMulti.made[0]
    assert getattr(values_sub.options, "topicsOnly", False) is False
    assert '/AdvantageKit/Vision/Left/RawEstimatedPoses' not in values_sub.prefixes
    assert '/AdvantageKit/RealOutputs/Vision/Left/Health/ScorePercent' in values_sub.prefixes
    assert 'Vision/Left/RawEstimatedPoses' not in snap


def test_mode_signals_are_always_read_and_patterns_are_updated_when_checks_change(monkeypatch):
    monkeypatch.setattr(live_nt, 'REBUILD_MIN_SEC', 0.0)
    inst = _snapshot_inst()
    ntcore = _fake_ntcore(inst)
    live_nt.set_health_signals([])
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=ntcore)
    assert set(live_nt.health_snapshot(_ntcore=ntcore)) == {'DriverStation/Enabled'}
    live_nt.set_health_signals(['RealOutputs/Vision/*/Health/ScorePercent'])
    assert 'RealOutputs/Vision/Left/Health/ScorePercent' in live_nt.health_snapshot(_ntcore=ntcore)


def test_disconnect_closes_the_health_subscriber():
    FakeMulti.closed = False
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=_fake_ntcore(FakeInst()))
    live_nt.disconnect()
    assert FakeMulti.closed


def test_vision_topic_names_match_what_the_robot_logs():
    """AdvantageKit capitalises the field name: Vision/<cam>/Connected, CurrentFps, VisibleTagIds."""
    inst = FakeInst()
    live_nt.connect('10.14.5.2', cameras=('Left',), _ntcore=_fake_ntcore(inst))
    assert '/AdvantageKit/Vision/Left/Connected' in inst.topics
    assert '/AdvantageKit/Vision/Left/CurrentFps' in inst.topics
    assert '/AdvantageKit/Vision/Left/VisibleTagIds' in inst.topics
