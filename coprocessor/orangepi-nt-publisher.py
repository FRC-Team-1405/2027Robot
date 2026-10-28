#!/usr/bin/env python3
"""Publishes Orange Pi system metrics to NetworkTables 4.

Run this on the Orange Pi co-processor alongside PhotonVision.
It connects to the roboRIO as an NT4 client and publishes CPU, RAM,
disk usage, and temperature twice a second under /OrangePi/. Set
ORANGEPI_METRICS_NAME to give each board its own subtable when more than one
Orange Pi is installed (for example, /OrangePi/LeftPi/).

It also publishes what's needed to judge vision throughput headroom: per-core CPU use, each CPU
cluster's clock and its current cap (a cap below the hardware maximum = thermal throttling), every
thermal zone by name with its throttle and critical trip temperatures, and PhotonVision's busiest
threads (CPU use and the core each last ran on). See PerformanceSampler. All of it is read from
/proc and /sys (no subprocesses) and costs a few milliseconds of CPU per sample; the publisher
reports its own cost as PublisherCpuPct.

Install dependency and service (creates a shared venv with pyntcore):
    bash setup-orangepi.sh

Run:
    ~/.venv-ntpublisher/bin/python3 orangepi-nt-publisher.py

To run on boot, add a systemd service (see orangepi-nt-publisher.service).
"""

import glob
import time
import os
import shutil
import socket

TEAM_NUMBER = 1405


def _env_interval(name, default):
    """A positive interval (seconds) from the environment, or the default if unset or invalid."""
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw) if raw else default
        return value if 0 < value < 3600 else default
    except ValueError:
        return default


# Twice a second: enough to see a load spike or a throttle step, cheap enough not to matter.
PUBLISH_INTERVAL_S = _env_interval("ORANGEPI_METRICS_INTERVAL_SEC", 0.5)
DISK_INTERVAL_S = 10.0          # disk usage changes slowly
PV_SEARCH_INTERVAL_S = 5.0      # how often to look for the PhotonVision process when it isn't found
TOP_THREADS = 8                 # PhotonVision threads published, busiest first
METRICS_NAME = os.environ.get("ORANGEPI_METRICS_NAME", "").strip()
# Which network interface to report link health for. Default: the one carrying the default route.
NET_IFACE = os.environ.get("ORANGEPI_NET_IFACE", "").strip()


def read_ip():
    """This board's IPv4 address on the network that reaches the roboRIO (10.TE.AM.2).

    No packets are sent: connecting a UDP socket only makes the OS pick the outgoing
    interface. Returns "" if there is no route yet, and is retried every publish.
    """
    roborio = f"10.{TEAM_NUMBER // 100}.{TEAM_NUMBER % 100}.2"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((roborio, 1))
            return sock.getsockname()[0]
    except OSError:
        return ""


def read_host():
    """mDNS-style name other machines can try (hostname.local); "" if unknown."""
    name = socket.gethostname().strip()
    return f"{name}.local" if name else ""


def read_temp_c():
    for zone in range(5):
        try:
            with open(f"/sys/class/thermal/thermal_zone{zone}/temp") as f:
                raw = int(f.read().strip())
            return round(raw / 1000 if raw > 1000 else float(raw), 1)
        except OSError:
            continue
    return 0.0


def read_cpu_times(root=""):
    """{"cpu": (idle, total), "cpu0": (...), ...} jiffies from /proc/stat; {} if unreadable."""
    out = {}
    try:
        with open(f"{root}/proc/stat") as f:
            for line in f:
                if not line.startswith("cpu"):
                    break
                parts = line.split()
                vals = [int(v) for v in parts[1:]]
                if len(vals) < 4:
                    continue
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)   # idle + iowait
                out[parts[0]] = (idle, sum(vals[:8]))                 # guest time is already in user
    except (OSError, ValueError):
        pass
    return out


def cpu_usage(prev, cur):
    """(overall %, [per-core %]) between two read_cpu_times() samples, cores in number order.
    Never blocks: the interval is just the time between the two samples."""
    def pct(name):
        if name not in prev or name not in cur:
            return 0.0
        d_idle = cur[name][0] - prev[name][0]
        d_total = cur[name][1] - prev[name][1]
        return round(max(0.0, min(100.0, (1.0 - d_idle / d_total) * 100)), 1) if d_total > 0 else 0.0
    cores = sorted((k for k in cur if k != "cpu"), key=lambda k: int(k[3:]))
    return pct("cpu"), [pct(k) for k in cores]


def _cpu_list(text):
    """'0 1 2 3' -> '0-3'; '4 5' -> '4-5'; anything else is returned stripped."""
    try:
        nums = sorted(int(n) for n in text.replace(",", " ").split())
    except ValueError:
        return text.strip()
    if len(nums) > 1 and nums == list(range(nums[0], nums[-1] + 1)):
        return f"{nums[0]}-{nums[-1]}"
    return " ".join(str(n) for n in nums)


def read_cpufreq(root=""):
    """One entry per cpufreq policy (a cluster of cores sharing a clock). On the RK3588S: the four
    A55 cores and two pairs of A76 cores. MHz values are -1 if unreadable.
      cpus     which cores, e.g. '4-5'
      cur_mhz  current clock (also drops at idle: that's the governor, not throttling)
      max_mhz  the hardware maximum (cpuinfo_max_freq)
      cap_mhz  the current upper limit (scaling_max_freq); thermal throttling pulls it below max_mhz
    """
    out = []
    policies = glob.glob(f"{root}/sys/devices/system/cpu/cpufreq/policy[0-9]*")
    for path in sorted(policies, key=lambda p: int(os.path.basename(p)[6:])):
        def mhz(name):
            khz = _read_int(f"{path}/{name}")
            return round(khz / 1000.0) if khz > 0 else -1
        cpus = _read_text(f"{path}/related_cpus") or _read_text(f"{path}/affected_cpus") or ""
        out.append({"cpus": _cpu_list(cpus), "cur_mhz": mhz("scaling_cur_freq"),
                    "max_mhz": mhz("cpuinfo_max_freq"), "cap_mhz": mhz("scaling_max_freq")})
    return out


def _millideg(text):
    try:
        raw = int(text)
    except (TypeError, ValueError):
        return -1.0
    return round(raw / 1000 if abs(raw) > 1000 else float(raw), 1)


def read_thermal_zones(root=""):
    """Every thermal zone the kernel exposes, in zone order: name (the zone's `type`, e.g.
    'soc-thermal', 'bigcore0-thermal', 'littlecore-thermal', 'gpu-thermal'), current temperature,
    and the lowest 'passive' trip (where the kernel starts throttling) and 'critical' trip (where it
    shuts down). Trips are -1 when the zone has none. Temperatures are deg C."""
    zones = []
    paths = glob.glob(f"{root}/sys/class/thermal/thermal_zone[0-9]*")
    for path in sorted(paths, key=lambda p: int(os.path.basename(p)[12:])):
        passive, critical = [], []
        for trip_type_path in glob.glob(f"{path}/trip_point_*_type"):
            kind = _read_text(trip_type_path)
            temp = _millideg(_read_text(trip_type_path[:-len("type")] + "temp"))
            if temp <= 0:
                continue
            if kind == "passive":
                passive.append(temp)
            elif kind == "critical":
                critical.append(temp)
        zones.append({"path": path, "name": _read_text(f"{path}/type") or os.path.basename(path),
                      "temp_c": _millideg(_read_text(f"{path}/temp")),
                      "passive_c": min(passive) if passive else -1.0,
                      "critical_c": min(critical) if critical else -1.0})
    return zones


def find_photonvision_pid(root="", own_pid=None):
    """PID of the PhotonVision (java) process, found by 'photonvision' in its command line; None if
    it isn't running."""
    own = str(own_pid if own_pid is not None else os.getpid())
    for cmdline in glob.glob(f"{root}/proc/[0-9]*/cmdline"):
        pid = os.path.basename(os.path.dirname(cmdline))
        if pid == own:
            continue
        try:
            with open(cmdline, "rb") as f:
                cmd = f.read().lower()
        except OSError:
            continue
        if b"photonvision" in cmd and b"java" in cmd:
            return int(pid)
    return None


def read_threads(pid, root=""):
    """{tid: (name, cpu ticks, last core)} for every thread of a process; {} if it has gone.
    From /proc/<pid>/task/<tid>/stat: the name is in parentheses and may itself contain spaces or
    parentheses, so split on the LAST ')'; utime+stime are fields 14-15, processor is field 39."""
    out = {}
    for stat in glob.glob(f"{root}/proc/{pid}/task/[0-9]*/stat"):
        try:
            with open(stat) as f:
                text = f.read()
            name = text[text.index("(") + 1:text.rindex(")")]
            rest = text[text.rindex(")") + 2:].split()
            out[int(os.path.basename(os.path.dirname(stat)))] = (name, int(rest[11]) + int(rest[12]), int(rest[36]))
        except (OSError, ValueError, IndexError):
            continue
    return out


class PerformanceSampler:
    """Collects the throughput-headroom metrics each publish. Usage values are deltas between this
    sample and the previous one, so nothing sleeps; the first sample reports zero use.

    Why each value: CpuCorePct because one saturated core shows as only ~12% in the 8-core average;
    the cpufreq cap because a clock capped below its maximum is thermal throttling, whatever the
    temperature reads; every thermal zone because the hottest one (not zone 0) is what throttles;
    PhotonVision's threads because which threads are busy, how many and on which cores answers
    "does PhotonVision use one core or several" directly."""

    def __init__(self, root="", clock=time.monotonic, process_time=time.process_time, ticks_per_sec=None):
        self._root = root
        self._clock = clock
        self._process_time = process_time
        try:
            self._hz = ticks_per_sec or os.sysconf("SC_CLK_TCK")
        except (AttributeError, ValueError, OSError):
            self._hz = 100
        self._prev_cpu = None
        self._prev_time = None
        self._prev_proc = None
        self._zones = None          # zone names and trips are static: read once
        self._pv_pid = None
        self._pv_searched = None
        self._prev_threads = {}

    def _pv_threads(self, now, elapsed):
        if self._pv_pid is not None and not os.path.isdir(f"{self._root}/proc/{self._pv_pid}"):
            self._pv_pid, self._prev_threads = None, {}      # PhotonVision restarted or stopped
        if self._pv_pid is None and (self._pv_searched is None or now - self._pv_searched >= PV_SEARCH_INTERVAL_S):
            self._pv_searched = now
            self._pv_pid = find_photonvision_pid(self._root)
        if self._pv_pid is None:
            return -1, 0.0, 0, [], [], []
        threads = read_threads(self._pv_pid, self._root)
        busy = []
        for tid, (name, ticks, core) in threads.items():
            before = self._prev_threads.get(tid)
            used = ticks - before[1] if before else 0
            pct = round(100.0 * used / self._hz / elapsed, 1) if elapsed > 0 else 0.0
            busy.append((pct, tid, name, core))
        self._prev_threads = threads
        busy.sort(key=lambda b: (-b[0], b[1]))
        top = busy[:TOP_THREADS]
        return (self._pv_pid, round(sum(b[0] for b in busy), 1), len(busy),
                [f"{name}/{tid}" for _, tid, name, _ in top], [b[0] for b in top], [b[3] for b in top])

    def sample(self):
        now = self._clock()
        proc = self._process_time()
        elapsed = (now - self._prev_time) if self._prev_time is not None else 0.0
        cpu = read_cpu_times(self._root)
        if self._prev_cpu:
            overall, cores = cpu_usage(self._prev_cpu, cpu)
        else:
            overall, cores = 0.0, [0.0] * sum(1 for k in cpu if k != "cpu")
        if self._zones is None:
            self._zones = read_thermal_zones(self._root)
            temps = [z["temp_c"] for z in self._zones]
        else:
            temps = [_millideg(_read_text(f"{z['path']}/temp")) for z in self._zones]
        freq = read_cpufreq(self._root)
        pid, pv_total, pv_count, names, pcts, last_cores = self._pv_threads(now, elapsed)
        publisher_pct = round(100.0 * (proc - self._prev_proc) / elapsed, 2) if elapsed > 0 else 0.0
        self._prev_cpu, self._prev_time, self._prev_proc = cpu, now, proc
        hottest = max(range(len(temps)), key=lambda i: temps[i]) if temps else None
        return {
            "CPU_Pct": overall,
            "CpuCorePct": cores,
            "CpuCoreMaxPct": max(cores) if cores else 0.0,
            "CpuFreqCpus": [f["cpus"] for f in freq],
            "CpuFreqMHz": [float(f["cur_mhz"]) for f in freq],
            "CpuFreqMaxMHz": [float(f["max_mhz"]) for f in freq],
            "CpuFreqCapMHz": [float(f["cap_mhz"]) for f in freq],
            "CpuThrottled": any(0 < f["cap_mhz"] < f["max_mhz"] for f in freq),
            "ThermalZones": [z["name"] for z in self._zones],
            "ThermalTempC": temps,
            "ThermalPassiveTripC": [z["passive_c"] for z in self._zones],
            "ThermalCriticalTripC": [z["critical_c"] for z in self._zones],
            "TempMaxC": temps[hottest] if hottest is not None else -1.0,
            "TempMaxZone": self._zones[hottest]["name"] if hottest is not None else "",
            "PvPid": pid,
            "PvCpuPct": pv_total,
            "PvThreadCount": pv_count,
            "PvTopThreads": names,
            "PvTopThreadPct": pcts,
            "PvTopThreadCore": last_cores,
            "PublisherCpuPct": publisher_pct,
        }


# NT type of each PerformanceSampler value.
PERFORMANCE_TOPICS = {
    "CPU_Pct": "Double", "CpuCorePct": "DoubleArray", "CpuCoreMaxPct": "Double",
    "CpuFreqCpus": "StringArray", "CpuFreqMHz": "DoubleArray", "CpuFreqMaxMHz": "DoubleArray",
    "CpuFreqCapMHz": "DoubleArray", "CpuThrottled": "Boolean",
    "ThermalZones": "StringArray", "ThermalTempC": "DoubleArray", "ThermalPassiveTripC": "DoubleArray",
    "ThermalCriticalTripC": "DoubleArray", "TempMaxC": "Double", "TempMaxZone": "String",
    "PvPid": "Integer", "PvCpuPct": "Double", "PvThreadCount": "Integer", "PvTopThreads": "StringArray",
    "PvTopThreadPct": "DoubleArray", "PvTopThreadCore": "IntegerArray", "PublisherCpuPct": "Double",
}


def read_ram():
    """Returns (used_mb, total_mb, pct) from /proc/meminfo."""
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            info[k.strip()] = int(v.split()[0])
    total_kb = info.get("MemTotal", 1)
    avail_kb = info.get("MemAvailable", 0)
    used_kb = total_kb - avail_kb
    return used_kb // 1024, total_kb // 1024, round(used_kb / total_kb * 100, 1)


def read_disk():
    """Returns (used_gb, total_gb, pct) for the root filesystem: the numbers `df -m /` gave, without
    starting a subprocess."""
    usage = shutil.disk_usage("/")
    total_mb, used_mb = usage.total // (1024 * 1024), (usage.total - usage.free) // (1024 * 1024)
    pct = round(used_mb / total_mb * 100, 1) if total_mb > 0 else 0.0
    return round(used_mb / 1024, 2), round(total_mb / 1024, 2), pct


def _read_text(path):
    """First line of a small /proc or /sys file, or None if it cannot be read."""
    try:
        with open(path) as f:
            return f.read().strip()
    except (OSError, ValueError):
        return None


def _read_int(path, default=-1):
    text = _read_text(path)
    try:
        return int(text) if text is not None else default
    except ValueError:
        return default


def read_uptime_sec(root=""):
    """Seconds since this board booted (the OS, not any one process). -1.0 if unreadable."""
    text = _read_text(f"{root}/proc/uptime")
    try:
        return round(float(text.split()[0]), 1) if text else -1.0
    except (ValueError, IndexError):
        return -1.0


def read_boot_id(root=""):
    """The kernel's random id for THIS boot: changes on every reboot, constant across service
    restarts, so a change between two log samples means the board really restarted."""
    return _read_text(f"{root}/proc/sys/kernel/random/boot_id") or ""


def primary_interface(root="", override=None):
    """The network interface to report: ORANGEPI_NET_IFACE if set, else the default route's, else
    the first physical-looking interface that exists. '' if none can be found."""
    if override:
        return override
    try:
        with open(f"{root}/proc/net/route") as f:
            next(f, None)
            for line in f:
                parts = line.split()
                if len(parts) > 1 and parts[1] == "00000000":
                    return parts[0]
    except OSError:
        pass
    for path in sorted(glob.glob(f"{root}/sys/class/net/*")):
        name = os.path.basename(path)
        if name == "lo" or name.startswith(("docker", "veth", "br-", "virbr", "tailscale")):
            continue
        if os.path.exists(f"{path}/device"):   # backed by hardware, not a virtual interface
            return name
    return ""


def read_link(iface, root=""):
    """Link health of one interface. carrier_changes counts every time the cable/link went up or
    down since boot, so a link that flapped N times shows N more changes afterwards, even if it is
    up now. Unreadable values are -1 / ''."""
    if not iface:
        return {"iface": "", "carrier_changes": -1, "operstate": "", "speed_mbps": -1}
    base = f"{root}/sys/class/net/{iface}"
    return {
        "iface": iface,
        "carrier_changes": _read_int(f"{base}/carrier_changes"),
        "operstate": _read_text(f"{base}/operstate") or "",
        "speed_mbps": _read_int(f"{base}/speed"),    # -1 while the link is down
    }


class NetTrafficSampler:
    """How much this board sends and receives on one interface, in Mbit/s, from the kernel's byte
    counters (deltas between samples, so nothing sleeps; the first sample reports zero). The error
    and drop counters are cumulative since boot, like NetCarrierChanges: a count that climbs during
    a match means packets were lost on this link.

    Why: to tell whether network bandwidth limits vision. The Pi's own link (100 or 1000 Mbit/s,
    NetSpeedMbps) is not the field's 7 Mbit/s radio limit -- Pi-to-roboRIO traffic stays on the
    robot's switch -- but everything a laptop dashboard streams from the Pi does cross the radio."""

    COUNTERS = ("rx_bytes", "tx_bytes", "rx_dropped", "rx_errors", "tx_errors")

    def __init__(self, root="", clock=time.monotonic):
        self._root = root
        self._clock = clock
        self._prev = None       # (iface, time, rx_bytes, tx_bytes)

    def sample(self, iface):
        base = f"{self._root}/sys/class/net/{iface}/statistics"
        c = {name: _read_int(f"{base}/{name}") for name in self.COUNTERS} if iface else \
            {name: -1 for name in self.COUNTERS}
        now = self._clock()
        rx_mbps = tx_mbps = 0.0
        prev = self._prev
        if prev and prev[0] == iface and now > prev[1] and c["rx_bytes"] >= prev[2] >= 0 and c["tx_bytes"] >= prev[3] >= 0:
            rx_mbps = round((c["rx_bytes"] - prev[2]) * 8 / 1e6 / (now - prev[1]), 3)
            tx_mbps = round((c["tx_bytes"] - prev[3]) * 8 / 1e6 / (now - prev[1]), 3)
        self._prev = (iface, now, c["rx_bytes"], c["tx_bytes"])
        return {"NetRxMbps": rx_mbps, "NetTxMbps": tx_mbps, "NetRxDropped": c["rx_dropped"],
                "NetRxErrors": c["rx_errors"], "NetTxErrors": c["tx_errors"]}


# NT type of each NetTrafficSampler value.
NET_TRAFFIC_TOPICS = {
    "NetRxMbps": "Double", "NetTxMbps": "Double",
    "NetRxDropped": "Integer", "NetRxErrors": "Integer", "NetTxErrors": "Integer",
}


def read_video(root=""):
    """(video device nodes, distinct USB cameras). One physical camera exposes several /dev/video
    nodes, so USB cameras are counted by their parent USB device. A camera that fell off the USB
    bus (cable, power glitch) drops this count and does not come back until it re-enumerates."""
    # Only numbered nodes: Rockchip boards also expose /dev/video-dec0 and /dev/video-enc0 (hardware
    # codecs), which are not cameras.
    nodes = glob.glob(f"{root}/dev/video[0-9]*")
    usb_parents = set()
    for entry in glob.glob(f"{root}/sys/class/video4linux/video*"):
        try:
            real = os.path.realpath(os.path.join(entry, "device"))
        except OSError:
            continue
        if "/usb" in real.replace("\\", "/"):
            # The link points at a USB *interface* (it has bInterfaceNumber); the physical camera is
            # its parent device, shared by all of that camera's interfaces and /dev/video nodes.
            usb_parents.add(os.path.dirname(real) if os.path.exists(os.path.join(real, "bInterfaceNumber")) else real)
    return len(nodes), len(usb_parents)


def read_system(root="", iface_override=None):
    """Everything the board can tell us about its own reboots, link and cameras. Never raises."""
    link = read_link(primary_interface(root, iface_override), root)
    try:
        video_nodes, usb_cameras = read_video(root)
    except Exception:
        video_nodes, usb_cameras = -1, -1
    return {"uptime_sec": read_uptime_sec(root), "boot_id": read_boot_id(root), **link,
            "video_devices": video_nodes, "usb_cameras": usb_cameras}


def main():
    import ntcore

    inst = ntcore.NetworkTableInstance.getDefault()
    client_name = "OrangePiMetrics" + (f"-{METRICS_NAME}" if METRICS_NAME else "")
    inst.startClient4(client_name)
    inst.setServerTeam(TEAM_NUMBER)

    table = inst.getTable("OrangePi")
    if METRICS_NAME:
        table = table.getSubTable(METRICS_NAME)

    # Declare all publishers up front so NT knows the types
    ram_used_pub  = table.getDoubleTopic("RAM_Used_MB").publish()
    ram_total_pub = table.getDoubleTopic("RAM_Total_MB").publish()
    ram_pct_pub   = table.getDoubleTopic("RAM_Pct").publish()
    disk_used_pub = table.getDoubleTopic("Disk_Used_GB").publish()
    disk_total_pub= table.getDoubleTopic("Disk_Total_GB").publish()
    disk_pct_pub  = table.getDoubleTopic("Disk_Pct").publish()
    temp_pub      = table.getDoubleTopic("Temp_C").publish()
    # Where to reach this board. tools/logbench reads these to find the Pis on its own
    # (server/pi_discovery.py); IP is preferred because two PhotonVision boards often
    # share the default hostname.
    ip_pub        = table.getStringTopic("IP").publish()
    host_pub      = table.getStringTopic("Host").publish()
    # Did the board reboot, did its network link flap, did a USB camera disappear? Together these
    # tell a reboot (uptime resets, BootId changes) from a service restart (neither) from a link
    # flap (NetCarrierChanges climbs, uptime keeps counting) from one camera dropping off USB.
    uptime_pub    = table.getDoubleTopic("SystemUptimeSec").publish()
    boot_pub      = table.getStringTopic("BootId").publish()
    iface_pub     = table.getStringTopic("NetIface").publish()
    carrier_pub   = table.getIntegerTopic("NetCarrierChanges").publish()
    operstate_pub = table.getStringTopic("NetOperState").publish()
    speed_pub     = table.getIntegerTopic("NetSpeedMbps").publish()
    video_pub     = table.getIntegerTopic("VideoDevices").publish()
    usbcam_pub    = table.getIntegerTopic("UsbCameras").publish()
    # Throughput headroom (CPU_Pct is one of these): see PerformanceSampler.
    perf_pubs = {name: getattr(table, f"get{kind}Topic")(name).publish()
                 for name, kind in PERFORMANCE_TOPICS.items()}
    perf = PerformanceSampler()
    net_pubs = {name: getattr(table, f"get{kind}Topic")(name).publish()
                for name, kind in NET_TRAFFIC_TOPICS.items()}
    net = NetTrafficSampler()
    disk = None
    disk_read_at = None

    topic_root = f"/OrangePi/{METRICS_NAME}" if METRICS_NAME else "/OrangePi"
    print(f"Connecting to roboRIO (team {TEAM_NUMBER}); publishing under {topic_root}/…")

    while True:
        loop_start = time.monotonic()
        try:
            for name, value in perf.sample().items():
                perf_pubs[name].set(value)
            ram_u, ram_t, ram_p  = read_ram()
            if disk is None or loop_start - disk_read_at >= DISK_INTERVAL_S:
                disk, disk_read_at = read_disk(), loop_start
            disk_u, disk_t, disk_p = disk
            temp       = read_temp_c()

            ram_used_pub.set(float(ram_u))
            ram_total_pub.set(float(ram_t))
            ram_pct_pub.set(ram_p)
            disk_used_pub.set(disk_u)
            disk_total_pub.set(disk_t)
            disk_pct_pub.set(disk_p)
            temp_pub.set(temp)
            ip_pub.set(read_ip())
            host_pub.set(read_host())

            system = read_system(iface_override=NET_IFACE or None)
            uptime_pub.set(system["uptime_sec"])
            boot_pub.set(system["boot_id"])
            iface_pub.set(system["iface"])
            carrier_pub.set(system["carrier_changes"])
            operstate_pub.set(system["operstate"])
            speed_pub.set(system["speed_mbps"])
            for name, value in net.sample(system["iface"]).items():
                net_pubs[name].set(value)
            video_pub.set(system["video_devices"])
            usbcam_pub.set(system["usb_cameras"])

        except Exception as e:
            print(f"Metrics error: {e}")

        # Sleep the rest of the interval so samples stay PUBLISH_INTERVAL_S apart.
        time.sleep(max(0.05, PUBLISH_INTERVAL_S - (time.monotonic() - loop_start)))


if __name__ == "__main__":
    main()
