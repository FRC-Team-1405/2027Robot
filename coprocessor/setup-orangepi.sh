#!/usr/bin/env bash
# Run on the Orange Pi as SSH user pi, from any working directory.
set -Eeuo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venv-ntpublisher"
PHASE="startup"
UNITS=(orangepi-nt-publisher.service orangepi-vision-recorder@left.service orangepi-vision-recorder@right.service)
SELECTED=()
WORK_DIR=""

usage() {
    cat <<'EOF'
Usage: bash setup-orangepi.sh [--status | --logs | --help]

Without options, walks through installing metrics, camera recorders, or both.
Run as SSH user pi, NOT with sudo. The installer
uses sudo only for OS packages, systemd units, and /etc configuration.
Python packages go into ~/.venv-ntpublisher; system Python is never pip-installed.

--status  Check PhotonVision, installed coprocessor services, Python, and disk.
--logs    Show recent journal entries for PhotonVision and all three services.
These diagnostic modes do not install, restart, or change configuration.
EOF
}

cleanup() { [[ -z "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"; }
trap cleanup EXIT

show_logs() {
    local unit
    for unit in photonvision.service "${UNITS[@]}"; do
        printf '\n--- %s (last 30 entries) ---\n' "$unit"
        sudo journalctl --no-pager -n 30 -u "$unit" || true
    done
}

failed() {
    local rc=$1 line=$2
    trap - ERR
    printf '\nERROR during %s (line %s, exit %s).\n' "$PHASE" "$line" "$rc" >&2
    echo 'Changes already completed are kept; fix the error and rerun this installer.' >&2
    echo 'For apt/pip failures, check the temporary internet route and DNS.' >&2
    echo 'For service failures, check the interpreter, file paths, and journal below.' >&2
    show_logs
    printf 'Debug again with: bash %q --status  or  bash %q --logs\n' "$SOURCE_DIR/setup-orangepi.sh" "$SOURCE_DIR/setup-orangepi.sh" >&2
    exit "$rc"
}
trap 'failed "$?" "$LINENO"' ERR

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

confirm() {
    local answer
    read -r -p "$1 [y/N] " answer || return 1
    [[ "$answer" == [yY] || "$answer" == [yY][eE][sS] ]]
}

check_unit() {
    local unit=$1
    printf '\n--- %s ---\n' "$unit"
    systemctl --no-pager --full status "$unit" || true
    if ! systemctl is-active --quiet "$unit"; then
        echo "FAIL: $unit is not active."
        sudo journalctl --no-pager -n 20 -u "$unit" || true
        return 1
    fi
}

status_check() {
    local result=0 unit
    echo "Python environment: $VENV"
    if [[ -x "$VENV/bin/python3" ]] && "$VENV/bin/python3" -c 'import ntcore; print("ntcore import: OK")'; then
        :
    else
        echo 'FAIL: venv or ntcore missing; rerun setup to install Python dependencies.'
        result=1
    fi
    df -h "$HOME"
    check_unit photonvision.service || result=1
    for unit in "${UNITS[@]}"; do
        if [[ "$(systemctl show "$unit" -p LoadState --value)" == not-found ]]; then
            echo "$unit: not installed (optional until selected in setup)."
        else
            check_unit "$unit" || result=1
            systemctl show "$unit" -p ExecStart -p NRestarts -p EnvironmentFiles
            if ! systemctl is-enabled --quiet "$unit"; then
                echo "FAIL: $unit is not enabled at boot."
                result=1
            fi
        fi
    done
    echo 'Active services do not prove NT connectivity, raw-camera correctness, or enabled-bit decoding.'
    return "$result"
}

# Do not source systemd EnvironmentFiles as shell code.
probe_stream() {
    python3 - "$1" <<'PY'
import shlex
import sys
import urllib.request
from pathlib import Path

try:
    values = {}
    for line in Path(sys.argv[1]).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = " ".join(shlex.split(value))
    url = values["CAMERA_STREAM_URL"]
    if not url.startswith(("http://", "https://")):
        raise ValueError("CAMERA_STREAM_URL must be an HTTP(S) URL")
    with urllib.request.urlopen(url, timeout=5) as response:
        kind = response.headers.get("Content-Type", "").lower()
        if not any(item in kind for item in ("multipart/x-mixed-replace", "image/jpeg")):
            raise ValueError(f"Unexpected stream Content-Type: {kind!r}")
        print(f"Stream responds: {url} ({kind})")
except Exception as exc:
    print(f"WARNING: camera stream check failed: {exc}", file=sys.stderr)
    sys.exit(1)
PY
}

configure_camera() {
    local camera=$1 url file="/etc/orangepi-vision-recorder/$1.env"
    if sudo test -f "$file"; then
        echo "Keeping existing $file (edit manually if the raw stream changed)."
        sudo cat "$file" > "$WORK_DIR/$camera.env"
        if ! grep -qE '^[[:space:]]*RECORDINGS_DIR=' "$WORK_DIR/$camera.env"; then
            printf '\nRECORDINGS_DIR=%s/vision-recordings\n' "$HOME" >> "$WORK_DIR/$camera.env"
            sudo install -m 644 "$WORK_DIR/$camera.env" "$file"
            echo "Added missing RECORDINGS_DIR for the current login account."
        fi
    else
        echo "Confirm the $camera camera RAW stream in PhotonVision's dashboard first."
        echo 'Bench reference only: left=1183, right=1181; ports can change.'
        read -r -p "Confirmed raw MJPEG URL for $camera (no default; blank skips camera): " url
        [[ -n "$url" ]] || { echo "Skipping $camera recorder."; return; }
        [[ "$url" =~ ^https?://[^[:space:]\"\'\\]+$ ]] || die 'Enter an HTTP(S) URL without spaces, quotes, or backslashes.'
        printf 'CAMERA_STREAM_URL=%s\nRECORDINGS_DIR=%s/vision-recordings\n' "$url" "$HOME" > "$WORK_DIR/$camera.env"
        sudo install -m 644 "$WORK_DIR/$camera.env" "$file"
    fi
    if ! probe_stream "$WORK_DIR/$camera.env"; then
        confirm "Stream check failed. Install $camera anyway for later debugging?" || { echo "Skipping $camera recorder."; return; }
    fi
    SELECTED+=("orangepi-vision-recorder@$camera.service")
}

install_unit() {
    local template=$1 script=$2
    # Windows transfer may preserve CRLF; normalize the unit before systemd reads it.
    tr -d '\r' < "$SOURCE_DIR/$template" > "$WORK_DIR/$template"
    sed -i "s|^ExecStart=.*|ExecStart=$VENV/bin/python3 $HOME/$script|" "$WORK_DIR/$template"
    if [[ "$SOURCE_DIR/$script" != "$HOME/$script" ]]; then
        install -m 755 "$SOURCE_DIR/$script" "$HOME/$script"
    fi
    sudo install -m 644 "$WORK_DIR/$template" "/etc/systemd/system/$template"
}

[[ $# -le 1 ]] || { usage; exit 2; }
MODE=${1:-install}
case "$MODE" in install|--status|--logs) ;; --help|-h) usage; exit 0 ;; *) usage; exit 2 ;; esac
command -v systemctl >/dev/null || die 'This script requires a systemd-based Orange Pi image.'
command -v sudo >/dev/null || die 'sudo is required; run this from the normal SSH account.'
[[ $EUID -ne 0 ]] || die 'Run bash setup-orangepi.sh as SSH user pi, without sudo.'
[[ "$(id -un)" == pi ]] || die 'The correct SSH account is pi. Reconnect with ssh pi@photonvision.local.'
case "$MODE" in
    --status) if status_check; then exit 0; else exit 1; fi ;;
    --logs) show_logs; exit 0 ;;
esac

[[ -t 0 ]] || die 'Installation is interactive; run in an SSH terminal. Use --status for diagnostics.'
# These paths are rendered into ExecStart and EnvironmentFile values.
[[ "$HOME" =~ ^/[a-zA-Z0-9_./-]+$ ]] || die 'Home path contains unsupported characters for generated systemd units.'
command -v apt-get >/dev/null || die 'Installation requires a Debian/Ubuntu image with apt-get.'
command -v python3 >/dev/null || die 'Install python3 on this image first.'
for file in orangepi-nt-publisher.py orangepi-nt-publisher.service orangepi-vision-recorder.py orangepi-vision-recorder@.service; do
    [[ -f "$SOURCE_DIR/$file" ]] || die "Missing $file beside this installer; copy the entire coprocessor folder."
done

echo 'Orange Pi setup: team 1405; shared Python venv; systemd services.'
echo "Login: $(id -un); home: $HOME; source: $SOURCE_DIR"
echo '1) Metrics publisher  2) Camera recorders (left/right)  3) Both  4) Quit'
read -r -p 'Install which services? [3] ' choice
choice=${choice:-3}
case "$choice" in 1|2|3) ;; 4) exit 0 ;; *) die 'Choose 1, 2, 3, or 4.' ;; esac
confirm 'Install/update selected scripts and units, and restart selected services?' || exit 0
PHASE='sudo access'
sudo -v
WORK_DIR=$(mktemp -d)

PHASE='Python virtual environment'
if [[ ! -x "$VENV/bin/python3" ]] || ! "$VENV/bin/python3" -m pip --version >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3-venv
    python3 -m venv "$VENV"
fi
if ! "$VENV/bin/python3" -c 'import ntcore' >/dev/null 2>&1; then
    "$VENV/bin/python3" -m pip install pyntcore
fi
"$VENV/bin/python3" -c 'import ntcore; print("ntcore import: OK")'

if [[ "$choice" == 1 || "$choice" == 3 ]]; then
    PHASE='metrics publisher installation'
    install_unit orangepi-nt-publisher.service orangepi-nt-publisher.py
    echo 'Keeping /etc/default/orangepi-nt-publisher if present (metrics namespace).'
    SELECTED+=(orangepi-nt-publisher.service)
fi
if [[ "$choice" == 2 || "$choice" == 3 ]]; then
    PHASE='camera recorder configuration'
    sudo install -d -m 755 /etc/orangepi-vision-recorder
    configure_camera left
    configure_camera right
    if [[ " ${SELECTED[*]} " == *'orangepi-vision-recorder@'* ]]; then
        install_unit orangepi-vision-recorder@.service orangepi-vision-recorder.py
        mkdir -p "$HOME/vision-recordings"
    fi
fi

PHASE='service startup'
if [[ ${#SELECTED[@]} -eq 0 ]]; then
    echo 'No services selected for startup. Camera configurations already written are kept.'
    exit 0
fi
if [[ ${#SELECTED[@]} -gt 0 ]]; then
    sudo systemctl daemon-reload
    for unit in "${SELECTED[@]}"; do
        sudo systemctl enable "$unit"
        sudo systemctl restart "$unit"
        before=$(systemctl show "$unit" -p NRestarts --value)
        # Catch immediate crashes/restart loops rather than one transient active state.
        for attempt in 1 2 3; do sleep 2; check_unit "$unit"; done
        after=$(systemctl show "$unit" -p NRestarts --value)
        [[ "$before" == "$after" ]] || die "$unit restarted during startup; inspect with --logs."
    done
fi
PHASE='final status check'
status_check
echo 'Setup checks passed. Verify /OrangePi updates in NT, raw frames while enabled,'
echo 'FMSInfo enabled-bit decoding, and PhotonVision FPS/latency on the bench.'
echo 'Recorder storage cap is 5GB PER camera; check free space for both cameras.'
echo 'Disconnect temporary Wi-Fi/internet before returning the Pi to the robot.'
