#!/bin/bash
# start-beacon-pd.sh — Launcher for PD Replica spatializer (6-band, port 9001)
#
# Runs alongside the main beacon (start-beacon.sh). Uses the same scsynth.
# Starts:
#   1. sclang with beacon_pd_replica.scd on port 9001
#   2. (Web UI OSC forwarding handled by webui.py's second client)
#
# Usage:
#   ./start-beacon-pd.sh          # live input from R24 CH1
#   ./start-beacon-pd.sh --file   # use recorded WAV source
#
# Requires: scsynth already running from start-beacon.sh, sclang in PATH

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Source mode
BEACON_SOURCE="live"
if [ "${1:-}" == "--file" ]; then
    BEACON_SOURCE="file"
fi
export BEACON_SOURCE

# Locate the scd file — try workspace first, then project dir
SCD_PATH=""
for try in \
    "$PROJECT_DIR/beacon_pd_replica.scd" \
    "$HOME/.hermes/kanban/boards/beacon-spatial/workspaces/t_75d31c3f/beacon_pd_replica.scd"; do
    if [ -f "$try" ]; then
        SCD_PATH="$try"
        break
    fi
done

if [ -z "$SCD_PATH" ]; then
    echo "[ERROR] beacon_pd_replica.scd not found. Copy it to the project dir."
    exit 1
fi

echo "=============================================="
echo "  PD REPLICA SPATIALIZER (port 9001)"
echo "  Source: $BEACON_SOURCE"
echo "=============================================="
echo "  sclang -> scsynth:57110  |  OSC in: 9001"
echo ""

SCLANG_PID=""
cleanup() {
    echo ""
    echo "[PD] Shutdown. Killing sclang..."
    [ -n "$SCLANG_PID" ] && kill "$SCLANG_PID" 2>/dev/null || true
    sleep 0.3
    [ -n "$SCLANG_PID" ] && kill -0 "$SCLANG_PID" 2>/dev/null && kill -9 "$SCLANG_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "[PD] Stopped."
    exit 0
}
trap cleanup INT TERM

echo "[1/1] sclang + beacon_pd_replica.scd (mode: $BEACON_SOURCE)..."
QT_QPA_PLATFORM=offscreen BEACON_SOURCE=$BEACON_SOURCE \
    script -q -c 'sclang -u 9001 -d . "'"$SCD_PATH"'"' /dev/null > /tmp/sclang_pd.log 2>&1 &
SCLANG_PID=$!
echo "      -> PID $SCLANG_PID (log: /tmp/sclang_pd.log)"

sleep 6

echo ""
echo "=============================================="
echo "  PD REPLICA READY"
echo "=============================================="
echo "  OSC    : 127.0.0.1:9001 (sclang)"
echo "  Server : 127.0.0.1:57110 (scsynth, shared)"
echo "  Log    : /tmp/sclang_pd.log"
echo "  Web UI : http://localhost:5050 (sends to both beacons)"
echo "=============================================="
echo "Press Ctrl-C to stop."
echo ""

wait
cleanup
