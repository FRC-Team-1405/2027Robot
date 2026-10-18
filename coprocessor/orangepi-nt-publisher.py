#!/usr/bin/env python3
"""Publishes Orange Pi system metrics to NetworkTables 4.

Run this on the Orange Pi co-processor alongside PhotonVision.
It connects to the roboRIO as an NT4 client and publishes CPU, RAM,
disk usage, and temperature once per second under /OrangePi/. Set
ORANGEPI_METRICS_NAME to give each board its own subtable when more than one
Orange Pi is installed (for example, /OrangePi/LeftPi/).

Install dependency and service (creates a shared venv with pyntcore):
    bash setup-orangepi.sh

Run:
    ~/.venv-ntpublisher/bin/python3 orangepi-nt-publisher.py

To run on boot, add a systemd service (see orangepi-nt-publisher.service).
"""

import glob
import time
import os
import socket
import subprocess

TEAM_NUMBER = 1405
PUBLISH_INTERVAL_S = 1.0
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


def read_cpu_pct():
    """Sample CPU usage over a short interval via /proc/stat."""
    def stat():
        with open("/proc/stat") as f:
            parts = f.readline().split()
        vals = list(map(int, parts[1:]))
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return idle, sum(vals)

    i0, t0 = stat()
    time.sleep(0.1)
    i1, t1 = stat()
    dt = t1 - t0
    return round((1.0 - (i1 - i0) / dt) * 100, 1) if dt > 0 else 0.0


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
    """Returns (used_gb, total_gb, pct) for the root filesystem."""
    r = subprocess.run(["df", "-m", "/"], capture_output=True, text=True, timeout=5)
    parts = r.stdout.splitlines()[1].split()
    total_mb, used_mb = int(parts[1]), int(parts[2])
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
    cpu_pub       = table.getDoubleTopic("CPU_Pct").publish()
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

    topic_root = f"/OrangePi/{METRICS_NAME}" if METRICS_NAME else "/OrangePi"
    print(f"Connecting to roboRIO (team {TEAM_NUMBER}); publishing under {topic_root}/…")

    while True:
        try:
            cpu        = read_cpu_pct()
            ram_u, ram_t, ram_p  = read_ram()
            disk_u, disk_t, disk_p = read_disk()
            temp       = read_temp_c()

            cpu_pub.set(cpu)
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
            video_pub.set(system["video_devices"])
            usbcam_pub.set(system["usb_cameras"])

        except Exception as e:
            print(f"Metrics error: {e}")

        time.sleep(PUBLISH_INTERVAL_S)


if __name__ == "__main__":
    main()
