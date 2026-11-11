#!/usr/bin/env bash
# Runs one bench step on an Orange Pi. The experiment runner (tools/exprunner) copies this folder
# to ~/bench/code and calls it over SSH; it can also be run by hand on the Pi.
#
#   bash ~/bench/code/run.sh <step> --results DIR [options]
#
# Steps:
#   env       Record the Pi's state (CPU clocks, temperatures, PhotonVision version) only.
#   capture   Grab frames straight from the camera into ~/bench/frames/<name>.mjpg.
#             Options: --name N --width W --height H --fps F [--count 300] [--skip 30] [--device /dev/video0]
#             PhotonVision is stopped while capturing (it holds the camera) and started again after.
#   selftest | inspect | steps | inflight
#             Run FrameCost (java/FrameCost.java) with PhotonVision's own jar and native libraries.
#             --frames N means ~/bench/frames/N.mjpg. Other options go to FrameCost unchanged.
#
# Options handled here, for every step:
#   --results DIR      where result.json and env.json go (required)
#   --stop-pv yes|no   stop PhotonVision during the step so it doesn't compete for CPU (default yes;
#                      capture always stops it). It is started again afterwards, also on failure.
#   --cores LIST       pin the step to these CPU cores with taskset, e.g. 4-7 (the fast cores)
#
# Environment overrides (normally not needed; for a non-standard install or a laptop smoke test):
#   BENCH_HOME (default ~/bench), BENCH_JAVA, BENCH_PV_JAR (classpath for PhotonVision's jar),
#   BENCH_CP_SEP (classpath separator, default ':'), BENCH_JAVA_OPTS (extra JVM options)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BENCH_HOME="${BENCH_HOME:-$HOME/bench}"
FRAMES_DIR="$BENCH_HOME/frames"

die() { echo "run.sh: $*" >&2; exit 2; }

[ $# -ge 1 ] || die "usage: run.sh <step> --results DIR [options]"
STEP="$1"; shift

RESULTS=""; STOP_PV="yes"; CORES=""
PASS=()          # options passed on to the step
while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "option $1 has no value"
    case "$1" in
        --results) RESULTS="$2" ;;
        --stop-pv) STOP_PV="$2" ;;
        --cores)   CORES="$2" ;;
        --frames)
            v="$2"; case "$v" in */*) ;; *) v="$FRAMES_DIR/$v.mjpg" ;; esac
            PASS+=(--frames "$v") ;;
        *) PASS+=("$1" "$2") ;;
    esac
    shift 2
done
[ -n "$RESULTS" ] || die "--results DIR is required"
mkdir -p "$RESULTS" "$FRAMES_DIR"

# ---------------------------------------------------------------- PhotonVision service

PV_WAS_ACTIVE=no
stop_pv() {
    if systemctl is-active --quiet photonvision; then
        PV_WAS_ACTIVE=yes
        echo "stopping PhotonVision for this step"
        sudo -n systemctl stop photonvision
    fi
}
restore_pv() {
    if [ "$PV_WAS_ACTIVE" = yes ]; then
        echo "starting PhotonVision again"
        sudo -n systemctl start photonvision || echo "run.sh: could not start PhotonVision; run: sudo systemctl start photonvision" >&2
    fi
}
trap restore_pv EXIT

# PhotonVision's java and jar, from its own service definition (so we use exactly what it runs).
pv_exec() { systemctl show -p ExecStart photonvision 2>/dev/null | sed -n 's/.*argv\[\]=\([^;]*\);.*/\1/p'; }
find_java() {
    if [ -n "${BENCH_JAVA:-}" ]; then echo "$BENCH_JAVA"; return; fi
    local j; j="$(pv_exec | awk '{print $1}')"
    if [ -n "$j" ] && [ -x "$j" ]; then echo "$j"; else command -v java || die "no java found"; fi
}
find_jar() {
    if [ -n "${BENCH_PV_JAR:-}" ]; then echo "$BENCH_PV_JAR"; return; fi
    local j; j="$(pv_exec | tr ' ' '\n' | grep -m1 '\.jar$' || true)"
    if [ -z "$j" ] || [ ! -f "$j" ]; then j="$(ls /opt/photonvision/*.jar 2>/dev/null | head -1 || true)"; fi
    [ -n "$j" ] || die "PhotonVision's jar not found (looked in its service and /opt/photonvision)"
    echo "$j"
}

# ---------------------------------------------------------------- the Pi's state, saved with every result

json_str() { printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"; }
write_env() {
    local f="$RESULTS/env.json" freqs temps gov
    freqs="$(for c in /sys/devices/system/cpu/cpu[0-9]*; do cat "$c/cpufreq/scaling_cur_freq" 2>/dev/null || echo 0; done | paste -sd, -)"
    temps="$( { cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null || true; } | paste -sd, -)"
    gov="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo unknown)"
    {
        echo "{"
        echo "  \"step\": $(json_str "$STEP"),"
        echo "  \"when_utc\": $(json_str "$(date -u +%Y-%m-%dT%H:%M:%SZ)"),"
        echo "  \"host\": $(json_str "$(hostname)"),"
        echo "  \"kernel\": $(json_str "$(uname -r)"),"
        echo "  \"cpu_khz\": [${freqs:-}],"
        echo "  \"thermal_millic\": [${temps:-}],"
        echo "  \"governor\": $(json_str "$gov"),"
        echo "  \"photonvision_jar\": $(json_str "$(find_jar 2>/dev/null || echo none)"),"
        echo "  \"photonvision_was_running\": $(json_str "$PV_WAS_ACTIVE"),"
        echo "  \"loadavg\": $(json_str "$(cat /proc/loadavg 2>/dev/null || true)"),"
        echo "  \"cores_pinned\": $(json_str "$CORES")"
        echo "}"
    } > "$f"
}

maybe_pin() { if [ -n "$CORES" ]; then echo taskset -c "$CORES"; fi; }
SEP="${BENCH_CP_SEP:-:}"
# shellcheck disable=SC2206
JAVA_OPTS=(${BENCH_JAVA_OPTS:-})

# ---------------------------------------------------------------- steps

opt() {  # opt NAME DEFAULT -> value of --NAME in PASS, or DEFAULT
    local name="--$1" i
    for ((i = 0; i < ${#PASS[@]}; i += 2)); do
        if [ "${PASS[i]}" = "$name" ]; then echo "${PASS[i+1]}"; return; fi
    done
    echo "$2"
}

case "$STEP" in
    env)
        write_env ;;

    capture)
        NAME="$(opt name '')"; W="$(opt width '')"; H="$(opt height '')"; FPS="$(opt fps '')"
        COUNT="$(opt count 300)"; SKIP="$(opt skip 30)"; DEV="$(opt device /dev/video0)"
        [ -n "$NAME" ] && [ -n "$W" ] && [ -n "$H" ] && [ -n "$FPS" ] || die "capture needs --name --width --height --fps"
        command -v v4l2-ctl >/dev/null || die "v4l2-ctl not installed (sudo apt install v4l-utils)"
        stop_pv
        sleep 1
        OUT="$FRAMES_DIR/$NAME.mjpg"
        v4l2-ctl -d "$DEV" --set-fmt-video="width=$W,height=$H,pixelformat=MJPG"
        v4l2-ctl -d "$DEV" --set-parm="$FPS"
        v4l2-ctl -d "$DEV" --get-fmt-video --get-parm > "$RESULTS/v4l2-format.txt"
        v4l2-ctl -d "$DEV" --list-ctrls > "$RESULTS/v4l2-controls.txt" || true
        echo "capturing $COUNT frames (skipping the first $SKIP) to $OUT"
        start=$(date +%s.%N)
        v4l2-ctl -d "$DEV" --stream-mmap --stream-skip="$SKIP" --stream-count="$COUNT" --stream-to="$OUT"
        end=$(date +%s.%N)
        write_env
        echo "{\"name\": $(json_str "$NAME"), \"file\": $(json_str "$OUT"), \"bytes\": $(stat -c %s "$OUT"), \"count\": $COUNT, \"skip\": $SKIP, \"seconds\": $(echo "$end - $start" | bc 2>/dev/null || echo null)}" > "$RESULTS/capture.json"
        restore_pv; PV_WAS_ACTIVE=no
        # What the camera actually sent: frame count and JPEG layout (1- or 3-channel).
        JAVA="$(find_java)"; JAR="$(find_jar)"
        "$JAVA" "${JAVA_OPTS[@]}" -cp "$HERE/classes$SEP$JAR" FrameCost inspect --frames "$OUT" --out "$RESULTS/result.json"
        ;;

    selftest|inspect|steps|inflight)
        JAVA="$(find_java)"; JAR="$(find_jar)"
        [ -d "$HERE/classes" ] || die "no compiled classes in $HERE/classes; sync from the laptop first"
        if [ "$STOP_PV" = yes ]; then stop_pv; sleep 2; fi
        write_env
        echo "java: $JAVA ($("$JAVA" -version 2>&1 | head -1)); jar: $JAR"
        # shellcheck disable=SC2046
        $(maybe_pin) "$JAVA" "${JAVA_OPTS[@]}" -cp "$HERE/classes$SEP$JAR" FrameCost "$STEP" "${PASS[@]}" --out "$RESULTS/result.json"
        ;;

    *)
        die "unknown step: $STEP" ;;
esac
