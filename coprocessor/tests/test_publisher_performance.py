"""The Pi metrics publisher's throughput-headroom values: per-core CPU, cluster clocks and caps,
every thermal zone with its trips, and PhotonVision's busiest threads.

Read from a fake /proc and /sys root (same approach as test_publisher_system); nothing here touches
the real system.
"""
import shutil
import tempfile
import unittest

from test_nt_identities import load_script
from test_publisher_system import write


def stat_line(name, user, idle):
    # user nice system idle iowait irq softirq steal
    return f"{name} {user} 0 0 {idle} 0 0 0 0 0 0\n"


def thread_stat(tid, name, ticks, core):
    """A /proc/<pid>/task/<tid>/stat line: utime is field 14, stime 15, processor 39."""
    rest = ["S"] + ["0"] * 49
    rest[11] = str(ticks)      # utime
    rest[12] = "0"             # stime
    rest[36] = str(core)       # processor
    return f"{tid} ({name}) " + " ".join(rest) + "\n"


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-nt-publisher.py", "LeftPi")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def proc_stat(self, cpu0_busy, cpu1_busy, total_per_core):
        write(self.root, "proc/stat",
              stat_line("cpu", cpu0_busy + cpu1_busy, 2 * total_per_core - cpu0_busy - cpu1_busy)
              + stat_line("cpu0", cpu0_busy, total_per_core - cpu0_busy)
              + stat_line("cpu1", cpu1_busy, total_per_core - cpu1_busy)
              + "intr 12345\n")

    def rk3588_like(self):
        for policy, cpus, cur, cap in (("policy0", "0 1 2 3", 1800000, 1800000),
                                       ("policy4", "4 5", 2208000, 2400000)):
            write(self.root, f"sys/devices/system/cpu/cpufreq/{policy}/related_cpus", cpus)
            write(self.root, f"sys/devices/system/cpu/cpufreq/{policy}/scaling_cur_freq", str(cur))
            write(self.root, f"sys/devices/system/cpu/cpufreq/{policy}/scaling_max_freq", str(cap))
            write(self.root, f"sys/devices/system/cpu/cpufreq/{policy}/cpuinfo_max_freq",
                  "1800000" if policy == "policy0" else "2400000")
        for zone, name, temp in ((0, "soc-thermal", 52300), (1, "bigcore0-thermal", 61800), (2, "gpu-thermal", 48000)):
            base = f"sys/class/thermal/thermal_zone{zone}"
            write(self.root, f"{base}/type", name)
            write(self.root, f"{base}/temp", str(temp))
            if zone < 2:
                write(self.root, f"{base}/trip_point_0_type", "active")
                write(self.root, f"{base}/trip_point_0_temp", "75000")
                write(self.root, f"{base}/trip_point_1_type", "passive")
                write(self.root, f"{base}/trip_point_1_temp", "85000")
                write(self.root, f"{base}/trip_point_2_type", "critical")
                write(self.root, f"{base}/trip_point_2_temp", "115000")

    def photonvision(self, threads):
        write(self.root, "proc/4242/cmdline", "java\0-Xmx512m\0-jar\0/opt/photonvision/photonvision.jar\0")
        write(self.root, "proc/77/cmdline", "/usr/bin/python3\0orangepi-nt-publisher.py\0")
        for tid, name, ticks, core in threads:
            write(self.root, f"proc/4242/task/{tid}/stat", thread_stat(tid, name, ticks, core))

    # ---- readers ----
    def test_per_core_usage_is_the_delta_between_samples(self):
        self.proc_stat(0, 0, 0)
        before = self.module.read_cpu_times(self.root)
        self.proc_stat(cpu0_busy=90, cpu1_busy=10, total_per_core=100)
        overall, cores = self.module.cpu_usage(before, self.module.read_cpu_times(self.root))
        self.assertEqual(cores, [90.0, 10.0])
        self.assertEqual(overall, 50.0)   # the average hides that core 0 is nearly saturated

    def test_clusters_report_clock_max_and_cap(self):
        self.rk3588_like()
        self.assertEqual(self.module.read_cpufreq(self.root), [
            {"cpus": "0-3", "cur_mhz": 1800, "max_mhz": 1800, "cap_mhz": 1800},
            {"cpus": "4-5", "cur_mhz": 2208, "max_mhz": 2400, "cap_mhz": 2400},
        ])

    def test_every_thermal_zone_is_named_with_its_passive_and_critical_trips(self):
        self.rk3588_like()
        zones = self.module.read_thermal_zones(self.root)
        self.assertEqual([(z["name"], z["temp_c"], z["passive_c"], z["critical_c"]) for z in zones], [
            ("soc-thermal", 52.3, 85.0, 115.0),
            ("bigcore0-thermal", 61.8, 85.0, 115.0),
            ("gpu-thermal", 48.0, -1.0, -1.0),
        ])

    def test_photonvision_is_found_by_its_command_line(self):
        self.photonvision([])
        self.assertEqual(self.module.find_photonvision_pid(self.root, own_pid=77), 4242)

    def test_no_photonvision_is_none(self):
        write(self.root, "proc/77/cmdline", "/usr/bin/python3\0x.py\0")
        self.assertIsNone(self.module.find_photonvision_pid(self.root, own_pid=77))

    def test_thread_names_with_spaces_and_parentheses_parse(self):
        self.photonvision([(4300, "VisionRunner (1)", 500, 6)])
        self.assertEqual(self.module.read_threads(4242, self.root), {4300: ("VisionRunner (1)", 500, 6)})

    # ---- the sampler ----
    def test_sampler_reports_cores_throttling_hottest_zone_and_busiest_threads(self):
        self.rk3588_like()
        self.proc_stat(0, 0, 0)
        self.photonvision([(4300, "VisionRunner", 1000, 6), (4301, "apriltag-worker", 1000, 5),
                           (4302, "NT", 1000, 1)])
        clock = Clock()
        cpu_time = [0.0]
        sampler = self.module.PerformanceSampler(self.root, clock=clock, process_time=lambda: cpu_time[0],
                                                 ticks_per_sec=100)
        first = sampler.sample()
        self.assertEqual(first["CpuCorePct"], [0.0, 0.0])
        self.assertEqual(first["PvTopThreadPct"], [0.0, 0.0, 0.0])   # no previous sample yet

        # 0.5 s later: VisionRunner used 45 ticks (90% of a core), the worker 20 (40%), NT 1 (2%);
        # the A76 pair's clock cap has dropped below its maximum.
        clock.now += 0.5
        cpu_time[0] += 0.005
        self.proc_stat(cpu0_busy=45, cpu1_busy=20, total_per_core=50)
        self.photonvision([(4300, "VisionRunner", 1045, 6), (4301, "apriltag-worker", 1020, 5),
                           (4302, "NT", 1001, 1)])
        write(self.root, "sys/devices/system/cpu/cpufreq/policy4/scaling_max_freq", "1608000")
        write(self.root, "sys/class/thermal/thermal_zone1/temp", "86200")
        s = sampler.sample()

        self.assertEqual(s["CpuCorePct"], [90.0, 40.0])
        self.assertEqual(s["CpuCoreMaxPct"], 90.0)
        self.assertEqual(s["CpuFreqCpus"], ["0-3", "4-5"])
        self.assertEqual(s["CpuFreqCapMHz"], [1800.0, 1608.0])
        self.assertTrue(s["CpuThrottled"])
        self.assertEqual(s["ThermalZones"], ["soc-thermal", "bigcore0-thermal", "gpu-thermal"])
        self.assertEqual(s["ThermalTempC"], [52.3, 86.2, 48.0])
        self.assertEqual((s["TempMaxC"], s["TempMaxZone"]), (86.2, "bigcore0-thermal"))
        self.assertEqual(s["ThermalPassiveTripC"], [85.0, 85.0, -1.0])
        self.assertEqual(s["PvPid"], 4242)
        self.assertEqual(s["PvThreadCount"], 3)
        self.assertEqual(s["PvTopThreads"], ["VisionRunner/4300", "apriltag-worker/4301", "NT/4302"])
        self.assertEqual(s["PvTopThreadPct"], [90.0, 40.0, 2.0])
        self.assertEqual(s["PvTopThreadCore"], [6, 5, 1])
        self.assertEqual(s["PvCpuPct"], 132.0)            # in cores' worth: more than one core busy
        self.assertEqual(s["PublisherCpuPct"], 1.0)        # 5 ms of CPU in 0.5 s
        self.assertEqual(set(s), set(self.module.PERFORMANCE_TOPICS))

    def test_sampler_copes_with_nothing_readable(self):
        sampler = self.module.PerformanceSampler(self.root, ticks_per_sec=100)
        for _ in range(2):
            s = sampler.sample()
        self.assertEqual((s["CpuCorePct"], s["ThermalZones"], s["CpuFreqCpus"]), ([], [], []))
        self.assertEqual((s["PvPid"], s["TempMaxC"], s["CpuThrottled"]), (-1, -1.0, False))

    def test_a_restarted_photonvision_is_found_again(self):
        self.photonvision([(4300, "VisionRunner", 10, 6)])
        clock = Clock()
        sampler = self.module.PerformanceSampler(self.root, clock=clock, ticks_per_sec=100)
        self.assertEqual(sampler.sample()["PvPid"], 4242)
        shutil.rmtree(f"{self.root}/proc/4242")
        write(self.root, "proc/5151/cmdline", "java\0-jar\0photonvision.jar\0")
        write(self.root, "proc/5151/task/5200/stat", thread_stat(5200, "VisionRunner", 3, 4))
        clock.now += self.module.PV_SEARCH_INTERVAL_S
        self.assertEqual(sampler.sample()["PvPid"], 5151)


if __name__ == "__main__":
    unittest.main()
