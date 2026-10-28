# Setting Up the Orange Pi NT4 Metrics Publisher

Installs `coprocessor/orangepi-nt-publisher.py` as a systemd service on the PhotonVision Orange Pi, so CPU/RAM/disk/temperature metrics show up in NetworkTables under `/OrangePi/`.

## Recommended: guided installer

Copy the entire `coprocessor` folder to the Pi, SSH in as its normal account, and run
`cd ~/coprocessor && bash setup-orangepi.sh` after using `sync-to-orangepi.bat`.
Alternatively, run `sync-to-orangepi.bat pi@photonvision.local --setup` on Windows
to copy the folder with SCP and open the installer over SSH. Choose metrics, recorders,
or both. Do not launch the installer with sudo; it requests sudo only where needed.
It uses your actual home
path, preserves existing environment files, and renders the service interpreter to
use the shared venv. See `coprocessor/README.md` for details.

Run `bash setup-orangepi.sh --status` or `--logs` for diagnostics without reinstalling.
The manual procedure below remains available. The correct SSH account is `pi`, and
the installer requires that login.

Every board needs its own namespace when sharing a roboRIO. The installer asks for a
unique board name and writes `/etc/default/orangepi-nt-publisher` automatically,
regardless of how many boards or cameras you use. Reruns default to the previous name.
Setup cannot detect a duplicate name chosen on another board; keep the names distinct.

For manual installation, create that file with your chosen name. Example for the current
robot's Left camera board:

```text
ORANGEPI_METRICS_NAME=LeftPi
```

Use `ORANGEPI_METRICS_NAME=RightPi` on the other board. The topics will then be under
`/OrangePi/LeftPi/` and `/OrangePi/RightPi/` instead of colliding at `/OrangePi/`. The systemd
service reads this optional file; a manually installed publisher with no file retains
the legacy paths. Multiple unnamed publishers would write the same topics.

Each board also publishes `IP` (its address on the robot network) and `Host`
(`<hostname>.local`) next to its metrics. `tools/logbench` reads them to find the Pis for
the Fetch Bundle page without a hand-written list (see its README). A board that was
installed before this was added publishes no `IP`/`Host` until you re-run
`sync-to-orangepi.bat` and restart `orangepi-nt-publisher.service`.

Client identities are `OrangePiMetrics-<board-name>`. The topic namespace is what
separates values; different client names alone do not prevent topic collisions.

**Prerequisite:** the Pi needs internet access once, to install the `pyntcore` Python package (the PyPI package is named `pyntcore`, not `robotpy-ntcore` — that name 404s). The previous install attempt failed because the Pi has no internet route at all (see `notes/6-20/photonVisionSSH.txt`). Follow **`docs/orangepi-internet-access.md`** first, then come back here. Don't skip the "disconnect Wi-Fi when done" step in that doc before the Pi goes back on a robot.

## 1. Get a Python environment with `ntcore`

Ubuntu 24.04 marks the system Python as "externally managed" (PEP 668), so `pip install` at the system level will refuse to run. Use a venv instead — it's robust and doesn't fight the OS package manager.

SSH into the Pi (with internet connected per the prerequisite doc):

```bash
ssh pi@photonvision.local

sudo apt update
sudo apt install -y python3-venv

python3 -m venv "$HOME/.venv-ntpublisher"
"$HOME/.venv-ntpublisher/bin/python3" -m pip install --upgrade pip
"$HOME/.venv-ntpublisher/bin/python3" -m pip install -U pyntcore
```

Confirm it imports cleanly:

```bash
"$HOME/.venv-ntpublisher/bin/python3" -c "import ntcore; print('ok')"
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
sudo sed -i "s|^ExecStart=.*|ExecStart=$HOME/.venv-ntpublisher/bin/python3 $HOME/orangepi-nt-publisher.py|" /tmp/orangepi-nt-publisher.service
```

This changes both the interpreter and script path to your login account.

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
- Look for the `/OrangePi` table (or `/OrangePi/LeftPi` and `/OrangePi/RightPi` for a named two-board install) with keys: `CPU_Pct`, `RAM_Used_MB`, `RAM_Total_MB`, `RAM_Pct`, `Disk_Used_GB`, `Disk_Total_GB`, `Disk_Pct`, `Temp_C`, `IP`, `Host`, the reboot/link/camera diagnostics (`SystemUptimeSec`, `BootId`, `NetCarrierChanges`, `UsbCameras`, ...) and the throughput-headroom values below.
- Values should update about twice a second (`ORANGEPI_METRICS_INTERVAL_SEC` changes that; disk usage is read every 10 s) and look sane (e.g. `Temp_C` matches what `cat /sys/class/thermal/thermal_zone0/temp` shows on the Pi, divided by 1000).

### Throughput-headroom values

Added for the vision throughput tests (`notes/10-27/notes.md`): can the Pi take a lower decimate or a
higher resolution without running out of CPU or throttling? All read from `/proc` and `/sys` with no
subprocesses; the robot copies them into the match log (`RealOutputs/OrangePi/...`) when
`FeatureSwitches.COPROCESSOR_HEALTH_LOGGING` is on. Arrays keep the topic count (and so the robot's
mirroring cost) low.

| Key | Type | Meaning |
|---|---|---|
| `CPU_Pct` | double | All cores averaged over the last interval. One maxed-out core shows as only ~12%. |
| `CpuCorePct` | double[] | Each core's use (core 0 first). On the RK3588S cores 0-3 are the slower A55s, 4-7 the faster A76s. |
| `CpuCoreMaxPct` | double | The busiest core. Near 100 while `CPU_Pct` is low = one thread is the limit. |
| `CpuFreqCpus` | string[] | Each CPU cluster (cores sharing one clock), e.g. `0-3`, `4-5`, `6-7`. The arrays below line up with it. |
| `CpuFreqMHz` | double[] | Current clock. It also drops when idle; that's normal power saving, not throttling. |
| `CpuFreqMaxMHz` | double[] | The cluster's hardware maximum. |
| `CpuFreqCapMHz` | double[] | The current upper limit. Below `CpuFreqMaxMHz` = the kernel is throttling that cluster. |
| `CpuThrottled` | boolean | Any cluster capped below its maximum. |
| `ThermalZones` | string[] | Every temperature sensor the kernel exposes, by name (its `type`). On an RK3588 typically `soc-thermal` (whole chip), `bigcore0-thermal` / `bigcore1-thermal` (each pair of A76 cores), `littlecore-thermal` (the A55s), `center-thermal`, `gpu-thermal`, `npu-thermal`. Check the real list on each board. |
| `ThermalTempC` | double[] | Each zone's temperature, in `ThermalZones` order. |
| `ThermalPassiveTripC` | double[] | Where each zone starts throttling (its lowest "passive" trip); -1 = none. |
| `ThermalCriticalTripC` | double[] | Where each zone forces a shutdown; -1 = none. |
| `TempMaxC` / `TempMaxZone` | double / string | The hottest zone right now, and which one. `Temp_C` is only the first zone. |
| `PvPid` | integer | PhotonVision's process id (-1 = not found; it is looked for every 5 s). A change = PhotonVision restarted. |
| `PvCpuPct` | double | All PhotonVision threads together, in cores' worth: 150 = one and a half cores busy. |
| `PvThreadCount` | integer | How many threads PhotonVision has. |
| `PvTopThreads` | string[] | The 8 busiest PhotonVision threads as `name/tid`, busiest first. |
| `PvTopThreadPct` | double[] | Each one's use, as % of one core. |
| `PvTopThreadCore` | integer[] | The core each last ran on (0-3 = A55, 4-7 = A76 on the RK3588S). |
| `PublisherCpuPct` | double | This publisher's own CPU use, as % of one core. Expected well under 1%. |

To see the same thing by hand on a Pi: `top -H -p $(pgrep -f photonvision)` (per thread),
`mpstat -P ALL 1` (per core, from the `sysstat` package), and
`grep . /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp`.

### PhotonVision settings and camera modes

So every log records how PhotonVision was set up, instead of relying on hand-written notes. On
10-27 the camera mode, decimate and Low Latency Mode were only in the notes. The publisher checks
every 5 s and publishes a value only when it changes, so each change lands in the match log once,
as `RealOutputs/OrangePi/<Pi>/...`. No robot code change is needed for that.

**Settings** come from PhotonVision's own settings file,
`/opt/photonvision/photonvision_config/photon.sqlite`. It is opened read-only, and only after the file
has been unchanged for 2 s. PhotonVision writes it 1–2 s after a change in the UI, so a new
value shows up within about 10 s. Set `PHOTONVISION_CONFIG_DB` in
`/etc/default/orangepi-nt-publisher` if the file is somewhere else.

| Key | Type | Meaning |
|---|---|---|
| `PvSettingsOk` / `PvSettingsError` | boolean / string | Whether the last read worked, and why not. |
| `PvCameras` | string[] | The active cameras, by nickname. Each has a `PhotonVision/<nickname>/` table. |
| `PhotonVision/<cam>/PipelineIndex`, `PipelineName`, `PipelineType`, `PipelineCount` | | The active pipeline. Index -1 = driver mode, -2 = calibration; then the pipeline values below keep their last values. |
| `.../Decimate`, `Threads`, `RefineEdges`, `Blur`, `DecisionMargin`, `PoseIterations`, `HammingDist`, `TagFamily`, `MultiTag` | | AprilTag tab. |
| `.../LowLatencyMode` | boolean | PhotonVision's `blockForFrames`. On = the ÷2 frame-rate cliff when a frame takes longer than one frame period (`docs/experiments/vision/2026-10-28-pv-frame-pacing/`). |
| `.../AutoExposure`, `Exposure`, `Brightness`, `Gain` | | Input tab. |
| `.../VideoModeIndex` | integer | Which entry of PhotonVision's resolution list is selected. The real mode is under `Video/` below. |
| `.../StreamDivisor`, `InputStream`, `OutputStream` | | Stream resolution and which streams are on. |
| `.../CalibratedResolutions` | string[] | Resolutions that have a calibration, e.g. `1280x800`. The current mode should be one of them. |
| `.../PipelineJson` | string | The whole active pipeline, for anything without its own key. |

**Camera modes** come from the V4L2 driver, which reports what the camera is really doing.
PhotonVision only saves the mode's index, so the driver is the place to read it. Read-only queries
are safe while PhotonVision is streaming. There is one table per capture node (a UVC camera's
metadata node is skipped):

| Key | Type | Meaning |
|---|---|---|
| `Video/<videoN>/Mode` | string | For example `800x600 MJPG @120`. |
| `Video/<videoN>/Width`, `Height`, `Fps`, `PixelFormat`, `Card` | | The same mode split into fields, plus the camera's name. |

**Verify on the bench before trusting it.** It was written without a Pi or PhotonVision to hand:
1. `PvSettingsOk` is true, and each value under `PhotonVision/<cam>/` matches the PhotonVision UI.
2. Change decimate in the UI. Within about 10 s, `Decimate` and `PipelineJson` update and nothing
   else changes.
3. `Video/<videoN>/Mode` matches the resolution and fps picked in the UI. Compare with
   `v4l2-ctl -d /dev/video0 --get-fmt-video --get-parm`.
4. PhotonVision still saves settings normally:
   `journalctl -u photonvision --since "10 min ago" | grep -i locked` should print nothing.

## 6. Clean up internet access

Before trusting the Pi on a robot again, finish the "disable Wi-Fi" step from `docs/orangepi-internet-access.md` (or revert ICS / unplug the radio's temporary WAN cable, whichever method you used). Re-check `nmcli device status` or equivalent shows no active wireless association.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'ntcore'` | Service's `ExecStart` still points at `/usr/bin/python3` instead of the venv | Re-check step 3, `systemctl daemon-reload`, restart the service |
| Service stuck in `activating (auto-restart)` | Script is crashing on every loop | `journalctl -u orangepi-nt-publisher.service -f` and read the traceback |
| `/OrangePi` table never appears in Glass/OutlineViewer | NT4 client never connected to the roboRIO | Confirm `TEAM_NUMBER` in the script matches 1405, confirm Pi and roboRIO are on the same radio network, confirm roboRIO is powered on |
| `pip install` fails with DNS errors again on a future re-install | Pi lost its temporary internet route | Re-run `docs/orangepi-internet-access.md` |
