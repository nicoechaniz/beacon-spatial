#!/usr/bin/env bash
set -euo pipefail

cd /home/nicolas/Projects/beacon-spatial

# Kill existing
killall sclang 2>/dev/null || true
killall scsynth 2>/dev/null || true
killall jackd 2>/dev/null || true
pkill -f 'python.*webui.py' 2>/dev/null || true
sleep 2

# 1. JACK
nohup jackd -d alsa -d hw:0,0 -r 44100 -p 256 -n 2 > /tmp/jackd_run.log 2>&1 &
JACK_PID=$!
echo "JACK PID: $JACK_PID"
sleep 3

# 2. scsynth
nohup scsynth -u 57110 -l 1 -i 2 -o 2 > /tmp/scsynth_run.log 2>&1 &
SC_PID=$!
echo "scsynth PID: $SC_PID"
sleep 3

# 3. sclang (needs pseudo-TTY to stay alive, no -D)
QT_QPA_PLATFORM=offscreen nohup script -q -c 'sclang -u 57120 -d . beacon.scd' /dev/null > /tmp/sclang_run.log 2>&1 &
SCLANG_PID=$!
echo "sclang PID: $SCLANG_PID"
sleep 12

# 4. Flask web UI (use venv python)
noown=""  # typo guard
nohup /home/nicolas/Projects/beacon-spatial/venv/bin/python webui.py > /tmp/webui_run.log 2>&1 &
WEB_PID=$!
echo "webui PID: $WEB_PID"
sleep 3

# Verify
ps -p $JACK_PID -o pid=,comm= || echo "JACK not running"
ps -p $SC_PID -o pid=,comm= || echo "scsynth not running"
ps -p $SCLANG_PID -o pid=,comm= || echo "sclang not running"
ps -p $WEB_PID -o pid=,comm= || echo "webui not running"

# Keep this script alive so Hermes background process stays
echo "Stack running. Waiting..."
while true; do
  sleep 60
  # Health check: restart if any died
  if ! kill -0 $JACK_PID 2>/dev/null; then
    echo "JACK died, restarting..."
    nohup jackd -d alsa -d hw:0,0 -r 44100 -p 256 -n 2 > /tmp/jackd_run.log 2>&1 &
    JACK_PID=$!
  fi
  if ! kill -0 $SC_PID 2>/dev/null; then
    echo "scsynth died, restarting..."
    nohup scsynth -u 57110 -l 1 -i 2 -o 2 > /tmp/scsynth_run.log 2>&1 &
    SC_PID=$!
  fi
  if ! kill -0 $SCLANG_PID 2>/dev/null; then
    echo "sclang died, restarting..."
    QT_QPA_PLATFORM=offscreen nohup script -q -c 'sclang -u 57120 -d . beacon.scd' /dev/null > /tmp/sclang_run.log 2>&1 &
    SCLANG_PID=$!
  fi
  if ! kill -0 $WEB_PID 2>/dev/null; then
    echo "webui died, restarting..."
    nohup /home/nicolas/Projects/beacon-spatial/venv/bin/python webui.py > /tmp/webui_run.log 2>&1 &
    WEB_PID=$!
  fi
done
