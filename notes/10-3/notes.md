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
```
