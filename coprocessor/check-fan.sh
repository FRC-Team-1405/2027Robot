#!/usr/bin/env bash
# Read-only fan diagnostics for the Orange Pi 5 V1.3.2.
# Run from the repository root: sudo bash coprocessor/check-fan.sh
set -u
printf '\nBoard and kernel\n'
tr '\0' '\n' < /proc/device-tree/model
uname -r
printf '\nOS\n'
cat /etc/os-release
printf '\nFan driver kernel configuration\n'
if [ -r "/boot/config-$(uname -r)" ]; then
    grep -E 'CONFIG_(SENSORS_PWM_FAN|PWM_ROCKCHIP|OF_OVERLAY)=' "/boot/config-$(uname -r)" || true
fi
printf '\nLoaded fan modules\n'
lsmod | grep -Ei 'fan|pwm' || true
printf '\nCooling devices\n'
grep . /sys/class/thermal/cooling_device*/type 2>/dev/null || true
printf '\nPWM controllers\n'
for chip in /sys/class/pwm/pwmchip*; do
    [ -d "$chip" ] || continue
    readlink -f "$chip"
    cat "$chip/npwm"
done
printf '\nDevice-tree fan and PWM nodes\n'
find /proc/device-tree -type d \( -iname '*fan*' -o -name 'pwm@*' \) 2>/dev/null |
while IFS= read -r node; do
    printf '%s\n' "$node"
    for prop in status compatible; do
        if [ -f "$node/$prop" ]; then
            printf '  %s: ' "$prop"
            tr '\0' '\n' < "$node/$prop"
        fi
    done
done
printf '\nPWM12 device-tree symbol\n'
if [ -f /proc/device-tree/__symbols__/pwm12 ]; then
    tr '\0' '\n' < /proc/device-tree/__symbols__/pwm12
fi
printf '\nAvailable fan and PWM overlays\n'
find /boot -type f \( -iname '*fan*' -o -iname '*pwm*.dtbo' \) 2>/dev/null
printf '\nBoot configuration\n'
for file in /boot/ubuntuEnv.txt /boot/armbianEnv.txt /boot/orangepiEnv.txt /boot/extlinux/extlinux.conf; do
    [ -r "$file" ] || continue
    printf '%s\n' "$file"
    cat "$file"
done
printf '\nPWM driver state\n'
if [ -r /sys/kernel/debug/pwm ]; then cat /sys/kernel/debug/pwm; fi
printf '\nFan/PWM kernel messages\n'
dmesg | grep -Ei 'pwm|fan' | tail -n 50 || true
