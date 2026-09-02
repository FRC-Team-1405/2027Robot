# Setting Up the Orange Pi NT4 Metrics Publisher

Installs `coprocessor/orangepi-nt-publisher.py` as a systemd service on the PhotonVision Orange Pi, so CPU/RAM/disk/temperature metrics show up in NetworkTables under `/OrangePi/`.

**Prerequisite:** the Pi needs internet access once, to install the `pyntcore` Python package (the PyPI package is named `pyntcore`, not `robotpy-ntcore` — that name 404s). The previous install attempt failed because the Pi has no internet route at all (see `notes/6-20/photonVisionSSH.txt`). Follow **`docs/orangepi-internet-access.md`** first, then come back here. Don't skip the "disconnect Wi-Fi when done" step in that doc before the Pi goes back on a robot.

## 1. Get a Python environment with `ntcore`

Ubuntu 24.04 marks the system Python as "externally managed" (PEP 668), so `pip install` at the system level will refuse to run. Use a venv instead — it's robust and doesn't fight the OS package manager.

SSH into the Pi (with internet connected per the prerequisite doc):

```bash
ssh pi@photonvision.local

sudo apt update
sudo apt install -y python3-venv

python3 -m venv /home/pi/.venv-ntpublisher
/home/pi/.venv-ntpublisher/bin/pip install --upgrade pip
/home/pi/.venv-ntpublisher/bin/pip install -U pyntcore
```

Confirm it imports cleanly:

```bash
/home/pi/.venv-ntpublisher/bin/python3 -c "import ntcore; print('ok')"
```

## 2. Copy the script and service file to the Pi

From the laptop, in the repo root (over the normal Ethernet/radio SSH path — no internet needed for this step):

```bash
scp coprocessor/orangepi-nt-publisher.py pi@photonvision.local:/home/pi/
scp coprocessor/orangepi-nt-publisher.service pi@photonvision.local:/tmp/
```

## 3. Point the service at the venv's Python

The checked-in `orangepi-nt-publisher.service` uses `/usr/bin/python3`, which won't have `ntcore` installed. On the Pi, edit the copy in `/tmp` before installing it:

```bash
sudo sed -i 's|/usr/bin/python3|/home/pi/.venv-ntpublisher/bin/python3|' /tmp/orangepi-nt-publisher.service
```

(Alternatively open it with `nano /tmp/orangepi-nt-publisher.service` and change the `ExecStart=` line by hand.)

If team number ever changes from 1405, also update `TEAM_NUMBER` in `/home/pi/orangepi-nt-publisher.py` before installing the service.

## 4. Install and start the service

```bash
sudo cp /tmp/orangepi-nt-publisher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orangepi-nt-publisher.service
sudo systemctl start orangepi-nt-publisher.service
```

## 5. Verify it's working

Check the service is active and not restart-looping:

```bash
sudo systemctl status orangepi-nt-publisher.service
```

You want `Active: active (running)`, not `activating (auto-restart)`. Tail the logs to confirm no exceptions:

```bash
sudo journalctl -u orangepi-nt-publisher.service -f
```

A healthy run prints `Connecting to roboRIO (team 1405)…` once and then stays quiet (errors print per-loop as `Metrics error: ...` but don't crash the service).

Confirm the data is actually reaching NetworkTables:
- With the robot/radio powered and the roboRIO running, open **Glass** or **OutlineViewer** pointed at the roboRIO's NT4 server (or check the Driver Station / AdvantageScope NT tab).
- Look for the `/OrangePi` table with keys: `CPU_Pct`, `RAM_Used_MB`, `RAM_Total_MB`, `RAM_Pct`, `Disk_Used_GB`, `Disk_Total_GB`, `Disk_Pct`, `Temp_C`.
- Values should update roughly once per second and look sane (e.g. `Temp_C` matches what `cat /sys/class/thermal/thermal_zone0/temp` shows on the Pi, divided by 1000).

## 6. Clean up internet access

Before trusting the Pi on a robot again, finish the "disable Wi-Fi" step from `docs/orangepi-internet-access.md` (or revert ICS / unplug the radio's temporary WAN cable, whichever method you used). Re-check `nmcli device status` or equivalent shows no active wireless association.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'ntcore'` | Service's `ExecStart` still points at `/usr/bin/python3` instead of the venv | Re-check step 3, `systemctl daemon-reload`, restart the service |
| Service stuck in `activating (auto-restart)` | Script is crashing on every loop | `journalctl -u orangepi-nt-publisher.service -f` and read the traceback |
| `/OrangePi` table never appears in Glass/OutlineViewer | NT4 client never connected to the roboRIO | Confirm `TEAM_NUMBER` in the script matches 1405, confirm Pi and roboRIO are on the same radio network, confirm roboRIO is powered on |
| `pip install` fails with DNS errors again on a future re-install | Pi lost its temporary internet route | Re-run `docs/orangepi-internet-access.md` |
