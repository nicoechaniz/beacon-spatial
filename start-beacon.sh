#!/bin/bash
#
# start-beacon.sh - Launcher for Harmonic Beacon Spatializer
# (SuperCollider scsynth + sclang + Flask Web UI [+ optional HTTPS tunnel])
#
# Starts full stack in project directory:
#   1. scsynth via pw-jack (PipeWire JACK compat) on UDP 57110
#   2. sclang (offscreen Qt) with beacon.scd (OSC receivers on 57120)
#   3. Flask web UI from ./venv (http://localhost:5050)
#   4. [optional] cloudflared quick-tunnel — gives a public https://
#      URL so phone browsers treat the page as a "secure context"
#      and allow DeviceOrientation / DeviceMotion sensor APIs.
#
# PipeWire provides JACK compatibility (pw-jack), so no separate jackd needed.
# This avoids ALSA exclusive-mode conflicts that break desktop audio.
#
# Proper Ctrl-C / SIGTERM cleanup: kills all tracked child PIDs.
# Usage: ./start-beacon.sh [--live|--file] [--no-https]
#   --live (default): SoundIn.ar(0) from R24 CH1
#   --file:           PlayBuf with harmonic_beacon_2026_05_13_session.wav
#   --no-https:       skip the cloudflared tunnel (LAN-only mode)
# Requires: pw-jack, scsynth, sclang in PATH + ./venv with flask + python-osc
# Optional: cloudflared at ~/.local/bin/cloudflared (for --no-https bypass)

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Parse args
BEACON_SOURCE="live"
ENABLE_HTTPS=1
for arg in "$@"; do
    case "$arg" in
        --file)   BEACON_SOURCE="file" ;;
        --live)   BEACON_SOURCE="live" ;;
        --no-https) ENABLE_HTTPS=0 ;;
    esac
done
export BEACON_SOURCE

echo "========================================"
echo "  Harmonic Beacon Spatializer"
echo "  Source: $BEACON_SOURCE"
echo "  HTTPS tunnel: $([ $ENABLE_HTTPS -eq 1 ] && echo 'yes (cloudflared)' || echo 'no  (--no-https)')"
echo "========================================"
echo "Dir: $PROJECT_DIR"
echo ""

SCSYNTH_PID=""
SCLANG_PID=""
WEBUI_PID=""
CFD_PID=""
TUNNEL_URL=""

cleanup() {
    echo ""
    echo "[INFO] Shutdown signal. Stopping children..."
    for pid in "$CFD_PID" "$WEBUI_PID" "$SCLANG_PID" "$SCSYNTH_PID"; do
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 0.6
    for pid in "$CFD_PID" "$WEBUI_PID" "$SCLANG_PID" "$SCSYNTH_PID"; do
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
        # Disconnect any previous output connections
        pw-jack jack_disconnect SuperCollider:out_1 "Built-in Audio Analog Stereo:playback_FL" 2>/dev/null || true
        pw-jack jack_disconnect SuperCollider:out_1 "Built-in Audio Analog Stereo:playback_FR" 2>/dev/null || true
        pw-jack jack_disconnect SuperCollider:out_2 "Built-in Audio Analog Stereo:playback_FL" 2>/dev/null || true
        pw-jack jack_disconnect SuperCollider:out_2 "Built-in Audio Analog Stereo:playback_FR" 2>/dev/null || true
        pw-jack jack_disconnect SuperCollider:out_1 "R24 Analog Stereo:playback_FL" 2>/dev/null || true
        pw-jack jack_disconnect SuperCollider:out_2 "R24 Analog Stereo:playback_FR" 2>/dev/null || true
        # Connect to both Built-in and R24 outputs
        pw-jack jack_connect SuperCollider:out_1 "Built-in Audio Analog Stereo:playback_FL" 2>/dev/null || true
        pw-jack jack_connect SuperCollider:out_2 "Built-in Audio Analog Stereo:playback_FR" 2>/dev/null || true
        pw-jack jack_connect SuperCollider:out_1 "R24 Analog Stereo:playback_FL" 2>/dev/null || true
        pw-jack jack_connect SuperCollider:out_2 "R24 Analog Stereo:playback_FR" 2>/dev/null || true
        echo "[OK] scsynth outputs connected to Built-in Audio + R24"
        break
    fi
    sleep 0.5
done

# Auto-connect R24 CH1 (capture_FL) to SuperCollider input 1 (SoundIn.ar index 0)
for i in $(seq 1 20); do
    if pw-jack jack_lsp 2>/dev/null | grep -q "SuperCollider:in_1"; then
        # Disconnect any previous input connections
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_FL" SuperCollider:in_1 2>/dev/null || true
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_FR" SuperCollider:in_1 2>/dev/null || true
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_RL" SuperCollider:in_1 2>/dev/null || true
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_RR" SuperCollider:in_1 2>/dev/null || true
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_FC" SuperCollider:in_1 2>/dev/null || true
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_SL" SuperCollider:in_1 2>/dev/null || true
        pw-jack jack_disconnect "R24 Analog Surround 7.1:capture_SR" SuperCollider:in_1 2>/dev/null || true
        # Connect only CH1
        pw-jack jack_connect "R24 Analog Surround 7.1:capture_FL" SuperCollider:in_1 2>/dev/null || true
        echo "[OK] R24 CH1 connected to SuperCollider input 1"
        break
    fi
    sleep 0.5
done

# --- 2. sclang + beacon.scd ---
echo "[2/3] sclang + beacon.scd (mode: $BEACON_SOURCE)..."
# sclang needs a pseudo-TTY to stay alive (REPL loop). script(1) provides one.
QT_QPA_PLATFORM=offscreen BEACON_SOURCE=$BEACON_SOURCE script -q -c 'sclang -u 57120 -d . beacon.scd' /dev/null > /tmp/sclang.log 2>&1 &
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

# --- 4. [Optional] cloudflared HTTPS tunnel ---
# A LAN-IP http:// page has no "secure context", so phone browsers
# (Android Chrome, iOS Safari) block DeviceOrientation / DeviceMotion.
# The cloudflared quick-tunnel gives a public https:// URL that does
# satisfy the secure-context requirement, so phone sensors work.
if [ $ENABLE_HTTPS -eq 1 ]; then
    CFD_BIN="$HOME/.local/bin/cloudflared"
    if [ ! -x "$CFD_BIN" ]; then
        echo "[WARN] cloudflared not found at $CFD_BIN — skipping HTTPS tunnel."
        echo "       Phone sensors will NOT work over LAN http://."
        echo "       Install with: curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o $CFD_BIN && chmod +x $CFD_BIN"
    else
        echo "[4/4] cloudflared quick-tunnel..."
        # Run cloudflared, capture log, find the URL when ready
        $CFD_BIN tunnel --url http://127.0.0.1:5050 --no-autoupdate > /tmp/cloudflared.log 2>&1 &
        CFD_PID=$!
        echo "      -> PID $CFD_PID (log: /tmp/cloudflared.log)"

        # Wait up to 15s for the URL to appear in the log
        for i in $(seq 1 30); do
            TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | head -1 || true)
            if [ -n "$TUNNEL_URL" ]; then
                break
            fi
            sleep 0.5
        done
    fi
fi

# --- Ready ---
echo ""
echo "========================================"
echo "  READY"
echo "========================================"
echo "  Web UI : http://localhost:5050"
echo "  OSC    : 127.0.0.1:57120 (sclang)"
echo "  Server : 127.0.0.1:57110 (scsynth)"
if [ -n "$TUNNEL_URL" ]; then
    echo ""
    echo "  >>> HTTPS TUNNEL (for phone sensors) <<<"
    echo "  >>> $TUNNEL_URL"
    echo "  >>> Open this URL on your phone to enable sensor access."
fi
echo "  Logs   : /tmp/{scsynth,sclang,webui,cloudflared}.log"
echo "========================================"
echo "Press Ctrl-C to stop everything cleanly."
echo ""

wait

# Fallback if children exit on their own
cleanup
