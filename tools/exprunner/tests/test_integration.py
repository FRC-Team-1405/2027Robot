"""The real NetworkTables and web socket code, against in-process servers that behave like the Pi publisher
and PhotonVision."""
import textwrap
import threading
import time

import msgpack
import ntcore
import pytest
from websockets.sync.server import serve

from exprunner.pv import PvClient, PvError, find_modes
from exprunner.robotlink import LinkError, NtLink

PORT = 5877


@pytest.fixture
def nt_server():
    """An NT4 server holding what the Pi publisher and the Driver Station publish."""
    inst = ntcore.NetworkTableInstance.create()
    inst.startServer("", "127.0.0.1", PORT - 1, PORT)
    base = "/OrangePi/LeftPi/"
    pubs = {
        "dec": inst.getIntegerTopic(base + "PhotonVision/LeftCam/Decimate").publish(),
        "thr": inst.getIntegerTopic(base + "PhotonVision/LeftCam/Threads").publish(),
        "ll": inst.getBooleanTopic(base + "PhotonVision/LeftCam/LowLatencyMode").publish(),
        "exp": inst.getDoubleTopic(base + "PhotonVision/LeftCam/Exposure").publish(),
        "uid": inst.getStringTopic(base + "PhotonVision/LeftCam/UniqueName").publish(),
        "mode": inst.getStringTopic(base + "Video/video0/Mode").publish(),
        "word": inst.getIntegerTopic("/FMSInfo/FMSControlData").publish(),
    }
    pubs["dec"].set(2)
    pubs["thr"].set(8)
    pubs["ll"].set(False)
    pubs["exp"].set(80.0)
    pubs["uid"].set("uid-left")
    pubs["mode"].set("800x600 MJPG @100")
    pubs["word"].set(0x20)                     # DS attached, disabled
    inst.flush()
    yield inst, pubs
    inst.stopServer()


def test_ntlink_reads_settings_and_robot_state(nt_server):
    inst, pubs = nt_server
    link = NtLink(host="127.0.0.1", port=PORT, connect_timeout=5)
    try:
        time.sleep(0.3)
        rb = link.readback("LeftPi", "LeftCam")
        assert rb["decimate"] == 2 and rb["threads"] == 8 and rb["low_latency"] is False
        assert rb["exposure"] == 80.0 and rb["camera_mode"] == "800x600 MJPG @100" and rb["_unique_name"] == "uid-left"
        assert link.robot_state() == (False, False)
        pubs["word"].set(0x20 | 0x01 | 0x02)   # enabled, autonomous
        inst.flush()
        time.sleep(0.3)
        assert link.robot_state() == (True, True)
        pubs["mode"].set("1280x800 MJPG @100")
        inst.flush()
        time.sleep(0.3)
        assert link.readback("LeftPi", "LeftCam")["camera_mode"] == "1280x800 MJPG @100"
        assert isinstance(link.now(), float)
    finally:
        link.close()


def test_ntlink_says_what_to_do_when_the_robot_isnt_there():
    with pytest.raises(LinkError, match="NetworkTables"):
        NtLink(host="127.0.0.1", port=5899, connect_timeout=0.5)


# ------------------------------------------------------------------ PhotonVision's web socket

SETTINGS = {"cameraSettings": [{
    "uniqueName": "uid-left", "nickname": "LeftCam",
    "videoFormatList": {
        "0": {"width": 640, "height": 480, "fps": 30, "pixelFormat": "kMJPEG"},
        "4": {"width": 800, "height": 600, "fps": 100, "pixelFormat": "kMJPEG"},
        "7": {"width": 1280, "height": 800, "fps": 100, "pixelFormat": "kMJPEG"},
        "8": {"width": 1280, "height": 800, "fps": 120, "pixelFormat": "kMJPEG"},
    }}]}


@pytest.fixture
def pv_server():
    received = []

    def handler(ws):
        ws.send(msgpack.packb({"fullsettings": SETTINGS}, use_bin_type=True))
        try:
            for raw in ws:
                received.append(msgpack.unpackb(raw, raw=False))
        except Exception:
            pass

    server = serve(handler, "127.0.0.1", 0)
    port = server.socket.getsockname()[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port, received
    server.shutdown()


def test_pv_client_finds_the_mode_index_and_sends_changes(pv_server):
    port, received = pv_server
    with PvClient("127.0.0.1", port) as pv:
        pv.drain(0.5)
        assert pv.mode_index("uid-left", "1280x800 MJPG @100") == 7
        assert pv.mode_index("uid-left", "800x600 MJPG @100") == 4
        with pytest.raises(PvError, match="has no mode"):
            pv.mode_index("uid-left", "1920x1080 MJPG @60")
        with pytest.raises(PvError, match="mode list"):
            pv.mode_index("uid-other", "800x600 MJPG @100")
        pv.apply("uid-left", {"decimate": 3, "low_latency": True, "camera_mode": "1280x800 MJPG @100"}, mode_index=7)
        time.sleep(0.3)
    assert {"changePipelineSetting": {"cameraUniqueName": "uid-left", "decimate": 3}} in received
    assert {"changePipelineSetting": {"cameraUniqueName": "uid-left", "blockForFrames": True}} in received
    assert {"changePipelineSetting": {"cameraUniqueName": "uid-left", "cameraVideoModeIndex": 7}} in received


def test_pv_client_unreachable_is_explained():
    with pytest.raises(PvError, match="can't reach PhotonVision"):
        with PvClient("127.0.0.1", 9, connect_timeout=1):
            pass


def test_find_modes_tolerates_nesting_and_lists():
    msgs = [{"x": {"y": [{"uniqueName": "u1", "videoFormatList": [{"width": 1, "height": 2, "fps": 3}]}]}}]
    assert find_modes(msgs, "u1") == {0: {"width": 1, "height": 2, "fps": 3, "format": ""}}
    assert find_modes(msgs, "nope") == {}


# ------------------------------------------------------------------ the whole thing through the CLI

def test_cli_run_end_to_end(tmp_path, monkeypatch, capsys):
    """`python -m exprunner run PLAN` against an NT server (Pi publisher + Driver Station), a PhotonVision
    web socket that changes what the 'publisher' reports, and LogBench. A thread plays the person who
    enables and disables the robot."""
    from exprunner import boards, cli
    from exprunner.boards import Board
    from tests.fakes import FakeLogBench

    inst = ntcore.NetworkTableInstance.create()
    inst.startServer("", "127.0.0.1", PORT + 1, PORT + 2)
    base = "/OrangePi/LeftPi/"
    top = {"mode": inst.getStringTopic(base + "Video/video0/Mode").publish(),
           "dec": inst.getIntegerTopic(base + "PhotonVision/LeftCam/Decimate").publish(),
           "uid": inst.getStringTopic(base + "PhotonVision/LeftCam/UniqueName").publish(),
           "word": inst.getIntegerTopic("/FMSInfo/FMSControlData").publish()}
    top["mode"].set("800x600 MJPG @100")
    top["dec"].set(2)
    top["uid"].set("uid-left")
    top["word"].set(0x20)
    inst.flush()

    changes = []

    def pv_handler(ws):
        ws.send(msgpack.packb({"fullSettings": SETTINGS}, use_bin_type=True))
        for raw in ws:
            msg = msgpack.unpackb(raw, raw=False)["changePipelineSetting"]
            changes.append(msg)
            # PhotonVision saves, the Pi publisher notices a couple of seconds later
            def publish(msg=msg):
                time.sleep(0.4)
                if "cameraVideoModeIndex" in msg:
                    top["mode"].set({4: "800x600 MJPG @100", 7: "1280x800 MJPG @100"}[msg["cameraVideoModeIndex"]])
                if "decimate" in msg:
                    top["dec"].set(msg["decimate"])
                inst.flush()
            threading.Thread(target=publish, daemon=True).start()

    pv = serve(pv_handler, "127.0.0.1", 0)
    pv_port = pv.socket.getsockname()[1]
    threading.Thread(target=pv.serve_forever, daemon=True).start()
    lb = FakeLogBench()

    def the_person():
        while not changes:                 # wait for the runner to set the camera
            time.sleep(0.05)
        time.sleep(1.5)
        top["word"].set(0x20 | 0x01 | 0x02)    # enable the auto
        inst.flush()
        time.sleep(0.6)
        top["word"].set(0x20)                   # disable
        inst.flush()

    threading.Thread(target=the_person, daemon=True).start()

    plan = tmp_path / "runs.toml"
    plan.write_text(textwrap.dedent('''
        experiment = "E2E"
        kind = "robot"
        routine = "TestAuto"
        cameras = ["LeftPi/LeftCam"]
        [defaults]
        decimate = 2
        [settings.A]
        camera_mode = "800x600 MJPG @100"
        [settings.B]
        camera_mode = "1280x800 MJPG @100"
        [[runs]]
        id = "R1"
        use = { LeftCam = "B" }
    '''))
    monkeypatch.setattr(boards, "load", lambda robot=None: {
        "LeftPi": Board("LeftPi", (f"127.0.0.1:{pv_port}",), ("LeftCam",))})
    try:
        code = cli.main(["run", str(plan), "--nt", f"127.0.0.1:{PORT + 2}", "--logbench", lb.url])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "settings confirmed from the Pi publisher" in out and "fetched akit_26-11-14_19-11-27.wpilog" in out
        assert changes == [{"cameraUniqueName": "uid-left", "cameraVideoModeIndex": 7}]
        import json as _json
        e = _json.loads((tmp_path / "manifest.json").read_text())["runs"]["R1"]["robot"]
        assert e["status"] == "ok" and e["read_back"]["LeftCam"]["camera_mode"] == "1280x800 MJPG @100"
        assert e["enable_window"]["t_disable"] > e["enable_window"]["t_enable"]
        # finish puts the camera back
        assert cli.main(["finish", str(plan), "--nt", f"127.0.0.1:{PORT + 2}"]) == 0
        assert changes[-1] == {"cameraUniqueName": "uid-left", "cameraVideoModeIndex": 4}
    finally:
        lb.close()
        pv.shutdown()
        inst.stopServer()
