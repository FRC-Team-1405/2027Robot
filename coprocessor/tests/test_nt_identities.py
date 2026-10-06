"""Check topic/client separation without requiring a roboRIO or pyntcore."""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[1]


class StopLoop(BaseException):
    pass


def load_script(filename, board, camera=""):
    spec = importlib.util.spec_from_file_location("test_coprocessor", SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {"ORANGEPI_METRICS_NAME": board, "CAMERA_NAME": camera}):
        spec.loader.exec_module(module)
    return module


class SharedTable:
    def __init__(self, values, path):
        self.values, self.path = values, path

    def getSubTable(self, name):
        return SharedTable(self.values, f"{self.path}/{name}")

    def getDoubleTopic(self, name):
        path = f"{self.path}/{name}"
        return SimpleNamespace(publish=lambda: SimpleNamespace(set=lambda value: self.values.__setitem__(path, value)))

    getStringTopic = getDoubleTopic


class NetworkTablesIdentityTests(unittest.TestCase):
    def test_two_boards_publish_independent_values_to_the_same_server(self):
        values = {}
        clients = []
        for board, cpu, ip in (("LeftPi", 11.0, "10.14.5.21"), ("RightPi", 29.0, "10.14.5.22")):
            module = load_script("orangepi-nt-publisher.py", board)
            instance = MagicMock()
            instance.getTable.side_effect = lambda name: SharedTable(values, f"/{name}")
            ntcore = SimpleNamespace(NetworkTableInstance=SimpleNamespace(getDefault=lambda: instance))
            with patch.dict(sys.modules, ntcore=ntcore), \
                 patch.object(module, "read_cpu_pct", return_value=cpu), \
                 patch.object(module, "read_ram", return_value=(100, 200, 50)), \
                 patch.object(module, "read_disk", return_value=(1, 10, 10)), \
                 patch.object(module, "read_temp_c", return_value=40),                  patch.object(module, "read_ip", return_value=ip),                  patch.object(module, "read_host", return_value=f"{board.lower()}.local"), \
                 patch.object(module.time, "sleep", side_effect=StopLoop), patch("builtins.print"):
                with self.assertRaises(StopLoop):
                    module.main()
            instance.setServerTeam.assert_called_once_with(1405)
            clients.append(instance.startClient4.call_args.args[0])
        self.assertEqual(values["/OrangePi/LeftPi/CPU_Pct"], 11.0)
        self.assertEqual(values["/OrangePi/RightPi/CPU_Pct"], 29.0)
        # How to reach each board, for tools/logbench's Pi discovery.
        self.assertEqual(values["/OrangePi/LeftPi/IP"], "10.14.5.21")
        self.assertEqual(values["/OrangePi/RightPi/Host"], "rightpi.local")
        self.assertEqual(len(values), 20)  # eight metrics plus IP and Host per board
        self.assertNotIn("/OrangePi/CPU_Pct", values)
        self.assertEqual(clients, ["OrangePiMetrics-LeftPi", "OrangePiMetrics-RightPi"])

    def test_recorder_names_include_board_and_instance_while_reading_shared_robot_topics(self):
        clients = []
        for board, camera in (("LeftPi", "left"), ("RightPi", "right"),
                              ("PracticeVision", "front"), ("PracticeVision", "rear")):
            module = load_script("orangepi-vision-recorder.py", board, camera)
            instance = MagicMock()
            ntcore = SimpleNamespace(NetworkTableInstance=SimpleNamespace(getDefault=lambda: instance))
            with patch.dict(sys.modules, ntcore=ntcore), \
                 patch.object(module, "next_boot_id", return_value=1), \
                 patch.object(module, "MjpegFrameReader", side_effect=StopLoop), patch("builtins.print"):
                with self.assertRaises(StopLoop):
                    module.main()
            clients.append(instance.startClient4.call_args.args[0])
            self.assertEqual([call.args[0] for call in instance.getTable.call_args_list],
                             ["FMSInfo", "RobotTime"])
            instance.getTable.return_value.getIntegerTopic.return_value.getEntry.return_value.set.assert_not_called()
        self.assertEqual(clients, ["OrangePiVisionRecorder-LeftPi-left", "OrangePiVisionRecorder-RightPi-right",
                                   "OrangePiVisionRecorder-PracticeVision-front", "OrangePiVisionRecorder-PracticeVision-rear"])
        self.assertEqual(len(set(clients)), 4)


if __name__ == "__main__":
    unittest.main()
