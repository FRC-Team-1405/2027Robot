"""The Pi metrics publisher's PhotonVision settings and camera modes.

The settings tests build a real SQLite file with PhotonVision's schema (DatabaseSchema.java,
v2026.1.1) and rows shaped like the ones it saves; the camera-mode tests pass a fake ioctl that
fills in the V4L2 structs. Nothing here needs PhotonVision, a camera or Linux.
"""
import json
import os
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from test_nt_identities import load_script


def apriltag_pipeline(index, nickname, **overrides):
    settings = {"pipelineIndex": index, "pipelineType": "AprilTag", "pipelineNickname": nickname,
                "decimate": 3, "threads": 4, "refineEdges": True, "blur": 0.0, "decisionMargin": 35,
                "numIterations": 40, "hammingDist": 0, "tagFamily": "kTag36h11", "doMultiTarget": True,
                "blockForFrames": True, "cameraAutoExposure": False, "cameraExposureRaw": 86.0,
                "cameraBrightness": 0, "cameraGain": 25, "cameraVideoModeIndex": 4,
                "streamingFrameDivisor": "NONE", "inputShouldShow": False, "outputShouldShow": True}
    settings.update(overrides)
    # Jackson's WRAPPER_ARRAY form, one JSON string per pipeline
    return json.dumps(["AprilTagPipelineSettings", settings])


def camera_config(nickname, pipeline_index=0, deactivated=False, resolutions=((1280, 800), (800, 600))):
    return json.dumps({"uniqueName": f"usb-{nickname}", "nickname": nickname, "deactivated": deactivated,
                       "currentPipelineIndex": pipeline_index, "FOV": 70.0,
                       "calibrations": [{"resolution": {"width": float(w), "height": float(h)}}
                                        for w, h in resolutions]})


def make_db(path, cameras):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE global (filename TINYTEXT PRIMARY KEY, contents mediumtext NOT NULL)")
    con.execute("CREATE TABLE cameras (unique_name TINYTEXT PRIMARY KEY, config_json text NOT NULL, "
                "drivermode_json text NOT NULL, pipeline_jsons mediumtext NOT NULL, "
                "otherpaths_json TEXT NOT NULL DEFAULT '[]')")
    for unique_name, config, pipelines in cameras:
        con.execute("INSERT INTO cameras (unique_name, config_json, drivermode_json, pipeline_jsons) "
                    "VALUES (?, ?, '{}', ?)", (unique_name, config, json.dumps(pipelines)))
    con.commit()
    con.close()


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


class PvSettingsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-nt-publisher.py", "LeftPi")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "photon.sqlite")

    def test_the_active_pipelines_settings_are_read_per_camera(self):
        make_db(self.db, [("usb-left", camera_config("LeftCam", 1),
                           [apriltag_pipeline(0, "dec 3"), apriltag_pipeline(1, "dec 2", decimate=2,
                                                                              blockForFrames=False)])])
        cam = self.module.read_pv_settings(self.db)["LeftCam"]
        self.assertEqual(cam["PipelineIndex"], ("Integer", 1))
        self.assertEqual(cam["PipelineName"], ("String", "dec 2"))
        self.assertEqual(cam["PipelineType"], ("String", "AprilTagPipelineSettings"))
        self.assertEqual(cam["Decimate"], ("Integer", 2))
        self.assertEqual(cam["LowLatencyMode"], ("Boolean", False))
        self.assertEqual(cam["Exposure"], ("Double", 86.0))
        self.assertEqual(cam["StreamDivisor"], ("String", "NONE"))
        self.assertEqual(cam["CalibratedResolutions"], ("StringArray", ["1280x800", "800x600"]))
        self.assertEqual(json.loads(cam["PipelineJson"][1])["pipelineNickname"], "dec 2")

    def test_driver_mode_and_deactivated_cameras(self):
        make_db(self.db, [("usb-left", camera_config("LeftCam", -1), [apriltag_pipeline(0, "a")]),
                          ("usb-old", camera_config("OldCam", deactivated=True), [apriltag_pipeline(0, "a")])])
        cameras = self.module.read_pv_settings(self.db)
        self.assertEqual(list(cameras), ["LeftCam"])
        self.assertEqual(cameras["LeftCam"]["PipelineType"], ("String", "DriverMode"))
        self.assertNotIn("Decimate", cameras["LeftCam"])

    def test_fields_a_pipeline_type_lacks_are_left_out(self):
        shape = json.dumps(["ColoredShapePipelineSettings", {"pipelineNickname": "shapes", "cameraGain": 10}])
        make_db(self.db, [("usb-left", camera_config("Left/Cam"), [shape])])
        cam = self.module.read_pv_settings(self.db)["Left_Cam"]
        self.assertEqual(cam["Gain"], ("Integer", 10))
        self.assertNotIn("Decimate", cam)

    def reader(self, wall, clock):
        return self.module.PvSettingsReader(self.db, interval_s=5.0, settle_s=2.0, clock=clock, wall=wall,
                                            read_modes=lambda: {})

    def test_only_changes_are_returned_and_the_file_is_reread_when_it_changes(self):
        make_db(self.db, [("usb-left", camera_config("LeftCam"), [apriltag_pipeline(0, "a")])])
        mtime = os.stat(self.db).st_mtime
        clock, wall = Clock(), Clock(mtime + 60)
        reader = self.reader(wall, clock)
        first = reader.poll()
        self.assertEqual(first["PvSettingsOk"], ("Boolean", True))
        self.assertEqual(first["PvCameras"], ("StringArray", ["LeftCam"]))
        self.assertEqual(first["PhotonVision/LeftCam/Decimate"], ("Integer", 3))
        clock.t = 1.0
        self.assertEqual(reader.poll(), {})          # not time to check yet
        clock.t = 10.0
        self.assertEqual(reader.poll(), {})          # file unchanged

        os.remove(self.db)
        make_db(self.db, [("usb-left", camera_config("LeftCam"), [apriltag_pipeline(0, "a", decimate=2)])])
        new_mtime = mtime + 100
        os.utime(self.db, (new_mtime, new_mtime))
        clock.t, wall.t = 20.0, new_mtime + 1        # changed, but PhotonVision may still be writing
        self.assertEqual(reader.poll(), {})
        clock.t, wall.t = 30.0, new_mtime + 5
        changed = reader.poll()      # the decimate, and the full pipeline JSON that contains it
        self.assertEqual(set(changed), {"PhotonVision/LeftCam/Decimate", "PhotonVision/LeftCam/PipelineJson"})
        self.assertEqual(changed["PhotonVision/LeftCam/Decimate"], ("Integer", 2))

    def test_a_missing_or_unreadable_file_is_reported_not_raised(self):
        reader = self.reader(Clock(1e9), Clock())
        out = reader.poll()
        self.assertEqual(out["PvSettingsOk"], ("Boolean", False))
        self.assertIn("no PhotonVision settings file", out["PvSettingsError"][1])
        Path(self.db).write_text("not a database")
        os.utime(self.db, (1e9 - 60, 1e9 - 60))
        reader._checked_at = None
        out = reader.poll()          # still not OK, so only the error text changes
        self.assertNotIn("PvSettingsOk", out)
        self.assertIn("DatabaseError", out["PvSettingsError"][1])

    def test_camera_modes_are_published_under_video(self):
        make_db(self.db, [])
        mtime = os.stat(self.db).st_mtime
        modes = {"video0": {"Fps": ("Double", 100.0)}}
        reader = self.module.PvSettingsReader(self.db, clock=Clock(), wall=Clock(mtime + 60),
                                              read_modes=lambda: modes)
        self.assertEqual(reader.poll()["Video/video0/Fps"], ("Double", 100.0))


def capability(card, caps):
    buf = bytearray(104)
    buf[16:16 + len(card)] = card.encode()
    struct.pack_into("<II", buf, 84, caps | 0x80000000, caps)
    return bytes(buf)


class CameraModeTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-nt-publisher.py", "LeftPi")

    def test_structs_are_decoded(self):
        card, capture = self.module.parse_v4l2_capability(capability("Arducam OV9281 USB Camera", 0x1))
        self.assertEqual((card, capture), ("Arducam OV9281 USB Camera", True))
        self.assertFalse(self.module.parse_v4l2_capability(capability("meta", 0x00800000))[1])
        fmt = bytearray(208)
        struct.pack_into("<III", fmt, 8, 1280, 800, struct.unpack("<I", b"MJPG")[0])
        self.assertEqual(self.module.parse_v4l2_format(bytes(fmt)), (1280, 800, "MJPG"))
        parm = bytearray(204)
        struct.pack_into("<II", parm, 12, 1, 100)
        self.assertEqual(self.module.parse_v4l2_fps(bytes(parm)), 100.0)
        self.assertEqual(self.module.parse_v4l2_fps(bytes(204)), 0.0)

    def test_capture_nodes_are_read_and_metadata_nodes_skipped(self):
        m = self.module
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "dev").mkdir()
            for name in ("video0", "video1", "video-dec0"):
                (Path(root) / "dev" / name).write_bytes(b"")
            opened = {}
            real_open = os.open

            def fake_open(path, flags):
                fd = real_open(path, os.O_RDONLY)
                opened[fd] = os.path.basename(path)
                return fd

            def ioctl(fd, request, buf):
                node = opened[fd]
                self.assertIsInstance(buf, bytes)      # so a real fcntl.ioctl returns the result
                if request == m._VIDIOC_QUERYCAP:
                    return capability("cam", 0x1 if node == "video0" else 0x00800000)
                if request == m._VIDIOC_G_FMT:
                    out = bytearray(buf)
                    struct.pack_into("<III", out, 8, 800, 600, struct.unpack("<I", b"MJPG")[0])
                    return bytes(out)
                out = bytearray(buf)
                struct.pack_into("<II", out, 12, 1, 120)
                return bytes(out)

            original = m.os.open
            m.os.open = fake_open
            try:
                modes = m.read_camera_modes(root, ioctl=ioctl)
            finally:
                m.os.open = original
        self.assertEqual(list(modes), ["video0"])
        self.assertEqual(modes["video0"]["Mode"], ("String", "800x600 MJPG @120"))
        self.assertEqual(modes["video0"]["Fps"], ("Double", 120.0))


class DynamicPublisherTests(unittest.TestCase):
    def test_publishers_are_made_once_per_path_under_sub_tables(self):
        from test_nt_identities import SharedTable
        module = load_script("orangepi-nt-publisher.py", "LeftPi")
        values = {}
        pub = module.DynamicPublisher(SharedTable(values, "/OrangePi/LeftPi"))
        pub.set("PhotonVision/LeftCam/Decimate", "Integer", 3)
        pub.set("PhotonVision/LeftCam/Decimate", "Integer", 2)
        pub.set("PvCameras", "StringArray", ["LeftCam"])
        self.assertEqual(values, {"/OrangePi/LeftPi/PhotonVision/LeftCam/Decimate": 2,
                                  "/OrangePi/LeftPi/PvCameras": ["LeftCam"]})


if __name__ == "__main__":
    unittest.main()
