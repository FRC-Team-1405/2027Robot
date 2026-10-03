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