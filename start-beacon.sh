#!/bin/bash
#
# start-beacon.sh - Launcher for Harmonic Beacon Spatializer
# (SuperCollider scsynth + sclang + Flask Web UI)
#
# Starts full stack in project directory:
#   1. scsynth via pw-jack (PipeWire JACK compat) on UDP 57110
#   2. sclang (offscreen Qt) with beacon.scd (OSC receivers on 57120)
#   3. Flask web UI from ./venv (http://localhost:5050)
#
# PipeWire provides JACK compatibility (pw-jack), so no separate jackd needed.
# This avoids ALSA exclusive-mode conflicts that break desktop audio.
#
# Proper Ctrl-C / SIGTERM cleanup: kills all tracked child PIDs.
# Usage: ./start-beacon.sh
# Requires: pw-jack, scsynth, sclang in PATH + ./venv with flask + python-osc

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "  Harmonic Beacon Spatializer"
echo "  SuperCollider + Web UI"
echo "========================================"
echo "Dir: $PROJECT_DIR"
echo ""

SCSYNTH_PID=""
SCLANG_PID=""
WEBUI_PID=""

cleanup() {
    echo ""
    echo "[INFO] Shutdown signal. Stopping children..."
    for pid in "$WEBUI_PID" "$SCLANG_PID" "$SCSYNTH_PID"; do
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 0.6
    for pid in "$WEBUI_PID" "$SCLANG_PID" "$SCSYNTH_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    echo "[OK] All processes stopped."
    exit 0
}

trap cleanup INT TERM

# --- 1. scsynth via pw-jack (PipeWire) ---
echo "[1/3] scsynth via pw-jack (port 57110, 2in/2out)..."
echo "[INFO] pw-jack scsynth -u 57110 -i 2 -o 2"
pw-jack scsynth -u 57110 -i 2 -o 2 > /tmp/scsynth.log 2>&1 &
SCSYNTH_PID=$!
echo "      -> PID $SCSYNTH_PID (log: /tmp/scsynth.log)"
sleep 3

# Auto-connect JACK outputs to system playback
for i in $(seq 1 20); do
    if pw-jack jack_lsp 2>/dev/null | grep -q "SuperCollider:out_1"; then
        pw-jack jack_connect SuperCollider:out_1 "Built-in Audio Analog Stereo:playback_FL" 2>/dev/null || true
        pw-jack jack_connect SuperCollider:out_2 "Built-in Audio Analog Stereo:playback_FR" 2>/dev/null || true
        echo "[OK] scsynth connected to Built-in Audio"
        break
    fi
    sleep 0.5
done

# --- 2. sclang + beacon.scd ---
echo "[2/3] sclang + beacon.scd..."
# sclang needs a pseudo-TTY to stay alive (REPL loop). script(1) provides one.
QT_QPA_PLATFORM=offscreen script -q -c 'sclang -u 57120 -d . beacon.scd' /dev/null > /tmp/sclang.log 2>&1 &
SCLANG_PID=$!
echo "      -> PID $SCLANG_PID (log: /tmp/sclang.log)"
sleep 8

# --- 3. Flask Web UI from venv ---
echo "[3/3] Flask web UI..."
VENV_PY="$PROJECT_DIR/venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
    echo "[ERROR] No venv python at $VENV_PY (run: python3 -m venv venv && pip install -r requirements.txt)"
    cleanup
fi
$VENV_PY webui.py > /tmp/webui.log 2>&1 &
WEBUI_PID=$!
echo "      -> PID $WEBUI_PID (log: /tmp/webui.log)"

# --- Ready ---
echo ""
echo "========================================"
echo "  READY"
echo "========================================"
echo "  Web UI : http://localhost:5050"
echo "  OSC    : 127.0.0.1:57120 (sclang)"
echo "  Server : 127.0.0.1:57110 (scsynth)"
echo "  Logs   : /tmp/{scsynth,sclang,webui}.log"
echo "========================================"
echo "Press Ctrl-C to stop everything cleanly."
echo ""

wait

# Fallback if children exit on their own
cleanup
