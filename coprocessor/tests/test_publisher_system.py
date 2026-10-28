"""The Pi metrics publisher's system diagnostics: uptime, boot id, link health and USB cameras.

They read /proc and /sys, so the tests build a fake root directory with the same layout and pass
it as `root`; nothing here touches the real system.
"""
import os
import tempfile
import unittest
from pathlib import Path

from test_nt_identities import load_script


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class SystemDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-nt-publisher.py", "LeftPi")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    # ---- uptime and boot id ----
    def test_uptime_is_the_first_field_of_proc_uptime(self):
        write(self.root, "proc/uptime", "12345.67 98765.43\n")
        self.assertEqual(self.module.read_uptime_sec(self.root), 12345.7)

    def test_unreadable_or_garbled_uptime_is_minus_one(self):
        self.assertEqual(self.module.read_uptime_sec(self.root), -1.0)
        write(self.root, "proc/uptime", "not a number")
        self.assertEqual(self.module.read_uptime_sec(self.root), -1.0)
        write(self.root, "proc/uptime", "")
        self.assertEqual(self.module.read_uptime_sec(self.root), -1.0)

    def test_boot_id_is_the_kernels_id_and_empty_when_unreadable(self):
        self.assertEqual(self.module.read_boot_id(self.root), "")
        write(self.root, "proc/sys/kernel/random/boot_id", "3f2a-91bc\n")
        self.assertEqual(self.module.read_boot_id(self.root), "3f2a-91bc")

    # ---- which interface ----
    def test_the_default_route_interface_is_chosen(self):
        write(self.root, "proc/net/route",
              "Iface\tDestination\tGateway\tFlags\n"
              "wlan0\t0010A8C0\t00000000\t0001\n"
              "eth0\t00000000\t0100A8C0\t0003\n")
        self.assertEqual(self.module.primary_interface(self.root), "eth0")

    def test_an_explicit_override_wins(self):
        write(self.root, "proc/net/route", "Iface\tDestination\neth0\t00000000\n")
        self.assertEqual(self.module.primary_interface(self.root, "enx001122"), "enx001122")

    def test_without_a_default_route_the_first_hardware_interface_is_used(self):
        for name, hardware in (("lo", False), ("docker0", False), ("veth9", False), ("eth0", True), ("eth1", True)):
            (Path(self.root) / "sys/class/net" / name).mkdir(parents=True)
            if hardware:
                (Path(self.root) / "sys/class/net" / name / "device").mkdir()
        self.assertEqual(self.module.primary_interface(self.root), "eth0")

    def test_no_interface_at_all_is_empty(self):
        self.assertEqual(self.module.primary_interface(self.root), "")

    # ---- link health ----
    def test_link_values_are_read_from_sysfs(self):
        base = "sys/class/net/eth0"
        write(self.root, f"{base}/carrier_changes", "7\n")
        write(self.root, f"{base}/operstate", "up\n")
        write(self.root, f"{base}/speed", "1000\n")
        self.assertEqual(self.module.read_link("eth0", self.root),
                         {"iface": "eth0", "carrier_changes": 7, "operstate": "up", "speed_mbps": 1000})

    def test_a_down_link_has_no_speed_and_missing_files_are_minus_one(self):
        base = "sys/class/net/eth0"
        write(self.root, f"{base}/operstate", "down\n")
        write(self.root, f"{base}/speed", "Invalid argument")    # what a down link can leave behind
        link = self.module.read_link("eth0", self.root)
        self.assertEqual((link["operstate"], link["speed_mbps"], link["carrier_changes"]), ("down", -1, -1))
        self.assertEqual(self.module.read_link("", self.root)["carrier_changes"], -1)

    # ---- USB cameras ----
    def make_camera(self, node, usb_device, interface="1.0"):
        """A /dev/videoN node whose sysfs `device` link points into a USB device's interface dir."""
        usb_dir = Path(self.root) / "sys/devices/platform/usb1" / usb_device
        iface_dir = usb_dir / f"{usb_device}_iface{interface}"     # real names contain ':', which Windows cannot create
        iface_dir.mkdir(parents=True, exist_ok=True)
        (iface_dir / "bInterfaceNumber").write_text(interface)
        write(self.root, f"dev/{node}", "")
        class_dir = Path(self.root) / "sys/class/video4linux" / node
        class_dir.mkdir(parents=True, exist_ok=True)
        link = class_dir / "device"
        try:
            os.symlink(iface_dir, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")

    def test_nodes_are_counted_and_usb_cameras_are_counted_by_physical_device(self):
        # one camera exposes a capture and a metadata node; a second camera exposes two more
        self.make_camera("video0", "1-1")
        self.make_camera("video1", "1-1", "1.1")
        self.make_camera("video2", "1-2")
        self.make_camera("video3", "1-2", "1.1")
        self.assertEqual(self.module.read_video(self.root), (4, 2))

    def test_a_camera_that_left_the_usb_bus_lowers_the_counts(self):
        self.make_camera("video0", "1-1")
        self.make_camera("video2", "1-2")
        self.assertEqual(self.module.read_video(self.root), (2, 2))
        (Path(self.root) / "dev/video2").unlink()
        import shutil
        shutil.rmtree(Path(self.root) / "sys/class/video4linux/video2")
        self.assertEqual(self.module.read_video(self.root), (1, 1))

    def test_hardware_codec_nodes_are_not_counted_as_cameras(self):
        self.make_camera("video0", "1-1")
        write(self.root, "dev/video-dec0", "")
        write(self.root, "dev/video-enc0", "")
        self.assertEqual(self.module.read_video(self.root), (1, 1))

    def test_no_cameras(self):
        self.assertEqual(self.module.read_video(self.root), (0, 0))

    # ---- all together ----
    def test_read_system_never_raises_and_reports_what_it_can(self):
        write(self.root, "proc/uptime", "50.0 1.0")
        write(self.root, "proc/sys/kernel/random/boot_id", "abc")
        write(self.root, "proc/net/route", "Iface\tDestination\neth0\t00000000\n")
        write(self.root, "sys/class/net/eth0/carrier_changes", "2")
        system = self.module.read_system(self.root)
        self.assertEqual((system["uptime_sec"], system["boot_id"], system["iface"], system["carrier_changes"]),
                         (50.0, "abc", "eth0", 2))
        self.assertEqual((system["operstate"], system["speed_mbps"], system["video_devices"], system["usb_cameras"]),
                         ("", -1, 0, 0))
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        bare = self.module.read_system(empty.name)
        self.assertEqual((bare["uptime_sec"], bare["boot_id"], bare["iface"]), (-1.0, "", ""))

    # ---- network traffic ----
    def _counters(self, iface, rx, tx, dropped=0, rx_err=0, tx_err=0):
        base = f"sys/class/net/{iface}/statistics"
        for name, value in (("rx_bytes", rx), ("tx_bytes", tx), ("rx_dropped", dropped),
                            ("rx_errors", rx_err), ("tx_errors", tx_err)):
            write(self.root, f"{base}/{name}", f"{value}\n")

    def test_traffic_is_the_byte_delta_in_megabits_per_second(self):
        clock = [100.0]
        net = self.module.NetTrafficSampler(self.root, clock=lambda: clock[0])
        self._counters("end1", 1_000_000, 5_000_000)
        first = net.sample("end1")
        self.assertEqual((first["NetRxMbps"], first["NetTxMbps"]), (0.0, 0.0))
        clock[0] = 100.5
        self._counters("end1", 1_250_000, 5_625_000, dropped=3, rx_err=1, tx_err=2)
        second = net.sample("end1")
        # 250 kB in 0.5 s = 4 Mbit/s; 625 kB in 0.5 s = 10 Mbit/s
        self.assertEqual(second, {"NetRxMbps": 4.0, "NetTxMbps": 10.0, "NetRxDropped": 3,
                                  "NetRxErrors": 1, "NetTxErrors": 2})

    def test_counter_reset_or_interface_change_reports_zero_not_a_spike(self):
        clock = [0.0]
        net = self.module.NetTrafficSampler(self.root, clock=lambda: clock[0])
        self._counters("end1", 9_000_000, 9_000_000)
        net.sample("end1")
        clock[0] = 1.0
        self._counters("end1", 100, 100)                 # driver reload resets the counters
        self.assertEqual(net.sample("end1")["NetRxMbps"], 0.0)
        clock[0] = 2.0
        self._counters("eth0", 50_000_000, 50_000_000)
        self.assertEqual(net.sample("eth0")["NetTxMbps"], 0.0)

    def test_missing_counters_are_minus_one_and_no_interface_is_safe(self):
        net = self.module.NetTrafficSampler(self.root)
        self.assertEqual(net.sample("end1")["NetRxErrors"], -1)
        self.assertEqual(net.sample("")["NetRxMbps"], 0.0)


if __name__ == "__main__":
    unittest.main()
