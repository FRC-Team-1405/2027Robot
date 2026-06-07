#!/usr/bin/env python3
"""Publishes Orange Pi system metrics to NetworkTables 4.

Run this on the Orange Pi co-processor alongside PhotonVision.
It connects to the roboRIO as an NT4 client and publishes CPU, RAM,
disk usage, and temperature once per second under /OrangePi/.

Install dependency:
    pip install robotpy-ntcore

Run:
    python3 orangepi-nt-publisher.py

To run on boot, add a systemd service (see orangepi-nt-publisher.service).
"""

import time
import os
import subprocess

TEAM_NUMBER = 1405
PUBLISH_INTERVAL_S = 1.0


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


def main():
    import ntcore

    inst = ntcore.NetworkTableInstance.getDefault()
    inst.startClient4("OrangePiMetrics")
    inst.setServerTeam(TEAM_NUMBER)

    table = inst.getTable("OrangePi")

    # Declare all publishers up front so NT knows the types
    cpu_pub       = table.getDoubleTopic("CPU_Pct").publish()
    ram_used_pub  = table.getDoubleTopic("RAM_Used_MB").publish()
    ram_total_pub = table.getDoubleTopic("RAM_Total_MB").publish()
    ram_pct_pub   = table.getDoubleTopic("RAM_Pct").publish()
    disk_used_pub = table.getDoubleTopic("Disk_Used_GB").publish()
    disk_total_pub= table.getDoubleTopic("Disk_Total_GB").publish()
    disk_pct_pub  = table.getDoubleTopic("Disk_Pct").publish()
    temp_pub      = table.getDoubleTopic("Temp_C").publish()

    print(f"Connecting to roboRIO (team {TEAM_NUMBER})…")

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

        except Exception as e:
            print(f"Metrics error: {e}")

        time.sleep(PUBLISH_INTERVAL_S)


if __name__ == "__main__":
    main()
