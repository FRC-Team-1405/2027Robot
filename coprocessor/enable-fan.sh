#!/usr/bin/env bash
# Enable the dedicated fan socket on Orange Pi 5 V1.3.2.
# Based on Orange Pi's rk3588s-orangepi-5.dts: PWM12, pwm12m1, 50000 ns.
# Usage: sudo bash coprocessor/enable-fan.sh [--install|--remove]
# No argument validates only. --install changes boot configuration, never reboots.
# Version: 2026-10-03.3 — compatible with older u-boot-update.
set -euo pipefail
SCRIPT_VERSION=2026-10-03.3
printf 'enable-fan.sh version %s\n' "$SCRIPT_VERSION"
printf 'Running file: %s\n' "$(readlink -f "${BASH_SOURCE[0]}")"
if [ "${1:-}" = --version ]; then exit 0; fi
mode="${1:---check}"
case "$mode" in --check|--install|--remove) ;; *) echo "Use --install, --remove, or no argument."; exit 1;; esac
[ "$EUID" -eq 0 ] || { echo "Run with sudo."; exit 1; }
conf=/etc/default/u-boot
edit_fan_config() {
    python3 - "$conf" "$@" <<'PY'
import pathlib, re, shlex, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text() if path.exists() else ""
text = re.sub(r"(?m)^# BEGIN OPI5 FAN\n.*?^# END OPI5 FAN\n?", "", text, flags=re.S)
if sys.argv[2] == "install":
    text = text.rstrip("\n") + "\n\n# BEGIN OPI5 FAN\n"
    text += "U_BOOT_FDT_OVERLAYS_DIR=" + shlex.quote(sys.argv[3]) + "\n"
    text += "U_BOOT_FDT_OVERLAYS=" + shlex.quote(sys.argv[4].strip()) + "\n"
    text += "# END OPI5 FAN\n"
path.write_text(text)
PY
}
backup=/boot/opi5-fan-backup
if [ "$mode" = --remove ]; then
    [ -f "$conf" ] && grep -q '^# BEGIN OPI5 FAN$' "$conf" || {
        echo "No fan configuration installed."; exit 0;
    }
    edit_fan_config remove
    u-boot-update
    echo "Fan overlay removed from boot configuration. Reboot to apply."
    exit 0
fi
for tool in dtc fdtoverlay fdtget u-boot-update python3; do
    command -v "$tool" >/dev/null || {
        echo "Missing $tool. Install dependencies: sudo apt install device-tree-compiler u-boot-menu"
        exit 1
    }
done
model=$(tr -d '\0' < /proc/device-tree/model)
[ "$model" = "Orange Pi 5" ] || { echo "Unexpected model: $model"; exit 1; }
[ "$(stat -c %d /)" = "$(stat -c %d /boot)" ] || {
    echo "Separate /boot partition: this installer needs adjusted U-Boot paths."; exit 1;
}
grep -q 'U_BOOT_FDT_OVERLAYS' "$(command -v u-boot-update)" || {
    echo "This u-boot-update lacks device-tree overlay support."; exit 1;
}
kernel=$(uname -r)
base="/lib/firmware/$kernel/device-tree/rockchip/rk3588s-orangepi-5.dtb"
[ -f "$base" ] || { echo "Missing expected base device tree: $base"; exit 1; }
[ "$(fdtget -t s "$base" / model)" = "$model" ] || {
    echo "Base device tree does not match running board."; exit 1;
}
# Use bootloader overlays only when the installed base contains the needed symbols.
for symbol in pwm12 pwm12m1_pins; do
    fdtget -t s "$base" /__symbols__ "$symbol"
done
modinfo pwm_fan >/dev/null || { echo "pwm_fan kernel module is missing."; exit 1; }
# Read the same configuration locations as u-boot-update, preserving existing overlays.
set +u
[ ! -f /etc/default/u-boot ] || . /etc/default/u-boot
if grep -q '/etc/u-boot-menu/conf.d/' "$(command -v u-boot-update)"; then
    for file in /usr/share/u-boot-menu/conf.d/*.conf /etc/u-boot-menu/conf.d/*.conf; do
        [ ! -f "$file" ] || . "$file"
    done
fi
set -u
overlay_dir="${U_BOOT_FDT_OVERLAYS_DIR:-/boot/dtbo}"
[ "${overlay_dir#/boot/}" != "$overlay_dir" ] || {
    echo "Overlay directory must be under /boot: $overlay_dir"; exit 1;
}
# A pre-existing explicit FDT can refer to a different base: don't guess.
[ -z "${U_BOOT_FDT:-}" ] || {
    echo "An explicit U_BOOT_FDT is already configured; review it before installing."; exit 1;
}
tempdir=$(mktemp -d)
trap 'rm -rf "$tempdir"' EXIT
cat > "$tempdir/fan.dts" <<'DTS'
/dts-v1/;
/plugin/;
/ {
    compatible = "rockchip,rk3588s-orangepi-5";
    fragment@0 {
        target = <&pwm12>;
        __overlay__ {
            status = "okay";
            pinctrl-names = "default";
            pinctrl-0 = <&pwm12m1_pins>;
        };
    };
    fragment@1 {
        target-path = "/";
        __overlay__ {
            opi5_fan: opi5-diagnostic-fan {
                compatible = "pwm-fan";
                #cooling-cells = <2>;
                pwms = <&pwm12 0 50000 0>;
                cooling-levels = <255 255>;
                status = "okay";
            };
        };
    };
};
DTS
dtc -@ -I dts -O dtb -o "$tempdir/fan.dtbo" "$tempdir/fan.dts"
fdtoverlay -i "$base" -o "$tempdir/merged.dtb" "$tempdir/fan.dtbo"
pwm_path=$(fdtget -t s "$base" /__symbols__ pwm12)
[ "$(fdtget -t s "$tempdir/merged.dtb" "$pwm_path" status)" = okay ]
[ "$(fdtget -t s "$tempdir/merged.dtb" /opi5-diagnostic-fan compatible)" = pwm-fan ]
echo "Validated overlay against $base"
if [ "$mode" = --check ]; then
    echo "Ready. To install: sudo bash coprocessor/enable-fan.sh --install"
    exit 0
fi
# Preserve original settings for recovery before the first installation.
mkdir -p "$backup"
if [ ! -f "$backup/extlinux.conf" ]; then
    cp -a /boot/extlinux/extlinux.conf "$backup/extlinux.conf"
    [ ! -f /etc/default/u-boot ] || cp -a /etc/default/u-boot "$backup/u-boot"
fi
mkdir -p "$overlay_dir" "$(dirname "$conf")"
install -m 0644 "$tempdir/fan.dtbo" "$overlay_dir/opi5-diagnostic-fan.dtbo"
# Empty overlay selection normally means load all files in the directory.
# Preserve that behavior if other overlays are already present.
overlays="${U_BOOT_FDT_OVERLAYS:-}"
if [ -z "$overlays" ]; then
    for file in "$overlay_dir"/*.dtbo; do
        [ -f "$file" ] || continue
        overlays="$overlays $(basename "$file")"
    done
elif [[ " $overlays " != *" opi5-diagnostic-fan.dtbo "* ]]; then
    overlays="$overlays opi5-diagnostic-fan.dtbo"
fi
# Preserve all existing settings, adding only a removable marked block.
if [ -f "$conf" ]; then
    cp -a "$conf" "$tempdir/u-boot.before"
else
    touch "$tempdir/u-boot.was-absent"
fi
edit_fan_config install "$overlay_dir" "$overlays"
cp -a /boot/extlinux/extlinux.conf "$tempdir/extlinux.before"
if ! u-boot-update || ! grep -q 'fdtoverlays .*opi5-diagnostic-fan.dtbo' /boot/extlinux/extlinux.conf; then
    if [ -f "$tempdir/u-boot.was-absent" ]; then
        rm -f "$conf"
    else
        cp -a "$tempdir/u-boot.before" "$conf"
    fi
    cp -a "$tempdir/extlinux.before" /boot/extlinux/extlinux.conf
    echo "Overlay was not enabled; boot configuration restored. Do not reboot for this test."
    exit 1
fi
echo "Installed. Reboot this Pi to test. The fan should run at full speed."
echo "Undo after boot: sudo bash coprocessor/enable-fan.sh --remove"
echo "If boot fails, restore /boot/extlinux/extlinux.conf from $backup/extlinux.conf on the SD card"
echo "and remove the BEGIN OPI5 FAN / END OPI5 FAN block from $conf."
