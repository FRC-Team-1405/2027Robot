# Coprocessor fan diagnosis — 2026-10-03

## Confirmed hardware and setup

- Physical board marking reported by Stephen: **`OPi V1.3.2`**. Preserve this exact marking; it does not by itself establish a Plus/Pro/Max model.
- Fans are plugged into the dedicated **two-pin fan port**, as reported by Stephen, one fan per coprocessor. Neither fan is spinning; reported temperature is approximately **67 °C**.
- Coprocessor names: `Left` and `Right`; hostnames: `LeftPi` and `RightPi`; PhotonVision camera nicknames: `LeftCam` and `RightCam`.
- Updating the robot's VisionConstants camera names to match `LeftCam` and `RightCam` restored vision updates to odometry (confirmed by Stephen).
- Diagnostic output below is from **RightPi**. Its loaded device tree reports **`Orange Pi 5`**; this is a software-reported model, recorded separately from the physical board marking.
- RightPi exposes `pwmchip0` and `pwmchip1`, but the captured cooling-device/hwmon listings show no registered fan controller. The mapping of these PWM controllers to the fan port remains unverified.
- Pending checks: `uname -r` and `readlink -f /sys/class/pwm/pwmchip*/device`. Do not assume either PWM controller drives the fan port solely from its presence.

## Captured command output

```text
pi@RightPi:~$ grep . /sys/class/thermal/cooling_device*/type
/sys/class/thermal/cooling_device0/type:cpufreq-cpu0
/sys/class/thermal/cooling_device1/type:cpufreq-cpu4
/sys/class/thermal/cooling_device2/type:cpufreq-cpu6
/sys/class/thermal/cooling_device3/type:devfreq-fb000000.gpu
/sys/class/thermal/cooling_device4/type:devfreq-dmc


pi@RightPi:~$ grep . /sys/class/hwmon/hwmon*/name
/sys/class/hwmon/hwmon0/name:soc_thermal
/sys/class/hwmon/hwmon1/name:bigcore0_thermal
/sys/class/hwmon/hwmon2/name:bigcore1_thermal
/sys/class/hwmon/hwmon3/name:littlecore_thermal
/sys/class/hwmon/hwmon4/name:center_thermal
/sys/class/hwmon/hwmon5/name:gpu_thermal
/sys/class/hwmon/hwmon6/name:npu_thermal
/sys/class/hwmon/hwmon7/name:tcpm_source_psy_6_0022


pi@RightPi:~$ cat /proc/device-tree/model
Orange Pi 5pi@RightPi:~$
pi@RightPi:~$ ls /sys/class/p
pci_bus/      power_supply/ ptp/
phy/          pps/          pwm/
pi@RightPi:~$ ls /sys/class/pwm/
pwmchip0  pwmchip1

pi@RightPi:~$ uname -r
6.1.0-1025-rockchip


pi@RightPi:~$ readlink -f /sys/class/pwm/pwmchip*
/sys/devices/platform/fd8b0020.pwm/pwm/pwmchip0
/sys/devices/platform/febd0020.pwm/pwm/pwmchip1
```

## Diagnosis from checkFanOutput.txt

- Ubuntu 24.04.4, kernel `6.1.0-1025-rockchip`.
- `CONFIG_SENSORS_PWM_FAN=m`: the fan driver is built as a module, but not loaded in the captured output.
- Both exposed PWM channels are requested by LCD backlight drivers. They are not available for a fan test.
- The installed device tree has a `pwm12` symbol pointing at `/pwm@febf0000`, but PWM12 is not registered as an active PWM controller in the output.
- Orange Pi's vendor Pi 5 configuration uses PWM12 with `pwm12m1_pins` for the fan: https://github.com/orangepi-xunlong/linux-orangepi/blob/orange-pi-6.1-rk35xx/arch/arm64/boot/dts/rockchip/rk3588s-orangepi-5.dts
- Likely cause: installed device-tree configuration does not enable the dedicated fan controller. Physical fan operation remains unverified.
- User reports the purchased fan is advertised as Orange Pi 5 Plus compatible. Exact fan model, voltage label, and connector polarity have not been verified.

### Prepared test

`coprocessor/enable-fan.sh` compiles a PWM12 overlay, validates that it applies to the installed Pi 5 DTB, and (with `--install`) enables it through a u-boot-menu configuration fragment. It preserves existing overlay selection, backs up boot settings, and does not reboot automatically. Initial test runs the fan at full speed; no temperature policy is installed. Shell syntax checked; not hardware-tested.

Run on RightPi first, from the repo root:

```bash
git pull
sudo bash coprocessor/enable-fan.sh --install
# Only after the script reports Installed:
sudo reboot
```

Missing tools: `sudo apt install device-tree-compiler u-boot-menu` (requires internet). After reconnecting, confirm the fan spins and rerun `check-fan.sh` if it does not. Undo with `sudo bash coprocessor/enable-fan.sh --remove`, then reboot. If boot fails, restore the saved extlinux.conf on the SD card and remove the script's configuration fragment; the script prints the paths.
