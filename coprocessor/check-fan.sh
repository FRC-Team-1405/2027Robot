#!/usr/bin/env bash
# Read-only fan diagnostics for the Orange Pi 5 V1.3.2.
# Run from the repository root: sudo bash coprocessor/check-fan.sh
# Version: 2026-10-03.4
set -u
printf 'check-fan.sh version 2026-10-03.4\n'
printf 'Running file: %s\n' "$(readlink -f "${BASH_SOURCE[0]}")"
if [ "${1:-}" = --version ]; then exit 0; fi
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
find -L /proc/device-tree -type d \( -iname '*fan*' -o -name 'pwm@*' \) 2>/dev/null |
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
find -L /boot -type f \( -iname '*fan*' -o -iname '*pwm*.dtbo' \) 2>/dev/null
printf '\nBoot configuration\n'
for file in /etc/default/u-boot /boot/ubuntuEnv.txt /boot/armbianEnv.txt /boot/orangepiEnv.txt /boot/extlinux/extlinux.conf; do
    [ -r "$file" ] || continue
    printf '%s\n' "$file"
    cat "$file"
done
printf '\nPWM driver state\n'
if [ -r /sys/kernel/debug/pwm ]; then cat /sys/kernel/debug/pwm; fi
printf '\nFan/PWM kernel messages\n'
dmesg | grep -Ei 'pwm|fan' | tail -n 50 || true

printf '\nLive overlay status\n'
if [ -d /proc/device-tree/opi5-diagnostic-fan ]; then
    printf 'Fan overlay node PRESENT\n'
    for prop in compatible status; do
        printf '%s: ' "$prop"
        tr '\0' '\n' < "/proc/device-tree/opi5-diagnostic-fan/$prop"
    done
else
    printf 'Fan overlay node ABSENT: the booted tree does not include our fan node.\n'
fi
if [ -f /proc/device-tree/pwm@febf0000/status ]; then
    printf 'PWM12 status: '
    tr '\0' '\n' < /proc/device-tree/pwm@febf0000/status
fi
printf '\nFan hwmon control values\n'
for hw in /sys/class/hwmon/hwmon*; do
    [ -r "$hw/name" ] || continue
    case "$(cat "$hw/name")" in
        *fan*)
            printf '%s\n' "$hw"
            for prop in name pwm1 pwm1_enable fan1_input; do
                [ ! -r "$hw/$prop" ] || { printf '%s: ' "$prop"; cat "$hw/$prop"; }
            done
            ;;
    esac
done
printf '\nFan platform driver binding\n'
for dev in /sys/bus/platform/devices/*fan*; do
    [ -d "$dev" ] || continue
    printf '%s\n' "$dev"
    readlink -f "$dev/driver" 2>/dev/null || true
done
printf '\nDeferred driver probes\n'
if [ -r /sys/kernel/debug/devices_deferred ]; then cat /sys/kernel/debug/devices_deferred; fi
