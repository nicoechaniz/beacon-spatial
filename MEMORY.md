# beacon-spatial — Project Memory

## Stack Overview

13-band binaural spatializer for the Harmonic Beacon. Replaced Pure Data engine with SuperCollider + ATK (Ambisonic Toolkit) for HRTF binaural rendering.

- **scsynth** — audio server, JACK client via `pw-jack` (PipeWire compat)
- **sclang + beacon.scd** — synth engine, 13 bandpass filters, ATK binaural decoder, OSC receiver
- **Flask webui.py** — control surface at `http://localhost:5050`, sends OSC to sclang on port 57120
- **PipeWire** — system audio server at 48 kHz (avoids ALSA exclusive-mode conflicts that `jackd` caused)

## Key Files

| File | Purpose |
|------|---------|
| `beacon.scd` | SuperCollider engine. 13 bands, 69 OSCdefs, ATK kernels at 48kHz/512 samples |
| `beacon_pd_replica.scd` | PD replica — 6-band spatializer on port 9001. Exact PD math (15Hz BW, ITD, butterfly AM, pan LFO) |
| `webui.py` | Flask UI. Per-band gain/az/dist/Q/solo, spectrum viz, mix/master, record, reset, save/load presets |
| `start-beacon-pd.sh` | Launcher for PD replica sclang on port 9001 (runs alongside main beacon) |
| `start-beacon.sh` | Launcher. Starts pw-jack, scsynth, auto-connects JACK ports, starts sclang with beacon.scd |
| `harmonic_beacon_2026_05_13_session.wav` | 2-hour mono 48kHz sample source (not in git — 659MB) |
| `configs/` | JSON presets. UI saves/loads `bands: [{gain, az, dist, solo, q}, ...]` + mix/master |
| `legacy/` | Original Pure Data patches preserved |
| `research/` | Forum research docs (Claude/Grok/Kimi proposals + critiques) |

## How to Run

### Main beacon (13-band ATK)
```bash
cd ~/Projects/beacon-spatial
./start-beacon.sh
```

### PD replica (6-band, alongside main beacon)
```bash
# First start the main beacon (above), then:
cd ~/Projects/beacon-spatial
./start-beacon-pd.sh
```

Wait for `=== BEACON READY ===` and `=== PD REPLICA READY ===` in respective logs.
Then open `http://localhost:5050`.

The web UI's OSC `/control` handler sends to BOTH ports (57120 and 9001),
so all slider changes affect both the 13-band ATK and 6-band PD replica simultaneously.

If Flask is not running yet, start it manually:
```bash
source venv/bin/activate
python3 webui.py
```

## Audio Pipeline Gotchas

- **Use `pw-jack scsynth`, not `jackd`**. Direct `jackd` grabs ALSA exclusively and causes "Dummy Output" in PipeWire.
- **sclang needs a pseudo-TTY** to stay alive. `start-beacon.sh` uses `script -q -c 'sclang beacon.scd'`. The `-D` daemon flag causes immediate exit.
- **Sample rate is 48 kHz** (matching PipeWire default). The source WAV was converted from 44.1kHz video extract. ATK Listen kernels loaded at 48000/512.
- **JACK port auto-connect**: `start-beacon.sh` waits for scsynth ports and runs `pw-jack jack_connect` to system playback.

## OSC Protocol (webui.py → sclang port 57120)

All messages sent as `osc.send_message(addr, float(val))`:

| Address | Args | Meaning |
|---------|------|---------|
| `/beacon/gain` | bandIdx (0-12), value (0-3) | Band gain |
| `/beacon/azimuth` | bandIdx, value (-180..180) | Azimuth degrees |
| `/beacon/distance` | bandIdx, value (0..3) | Distance (ATK radius) |
| `/beacon/q` | bandIdx, value (0.001..0.5) | Filter Q / bandwidth |
| `/beacon/solo` | bandIdx, value (0 or 1) | Solo toggle |
| `/beacon/mix` | 0, value (0..1) | Dry/wet mix |
| `/beacon/master` | 0, value (0..3) | Master gain |
| `/beacon/record/start` | — | Start recording output WAV |
| `/beacon/record/stop` | — | Stop recording |
| `/beacon/reset` | — | Reset all to defaults |

## 13-Band Layout

| Band | Freq | Type | Default Q | Color |
|------|------|------|-----------|-------|
| 1 | 40 Hz | BPF | 1.0 | Red |
| 2 | 80 Hz | BPF | 0.5 | Orange |
| 3 | 120 Hz | BPF | 0.333 | Yellow |
| 4 | 160 Hz | BPF | 0.25 | Green |
| 5 | 200 Hz | BPF | 0.2 | Teal |
| 6 | 240 Hz | BPF | 0.167 | Blue |
| 7 | 480 Hz | BPF | 0.5 | Dark blue |
| 8 | 720 Hz | BPF | 0.333 | Purple |
| 9 | 960 Hz | BPF | 0.25 | Lavender |
| 10 | 1200 Hz | BPF | 0.2 | Pink |
| 11 | 1440 Hz | BPF | 0.167 | Light pink |
| 12 | 1680 Hz | BPF | 0.143 | Periwinkle |
| 13 | 1800+ Hz | HPF | — | Light gray |

Bands 1-6: 40 Hz bandwidth (40-240 Hz). Bands 7-12: 240 Hz bandwidth (480-1680 Hz). Band 13: HPF cutoff at 1800 Hz.

## Preset Format

```json
{
  "bands": [
    {"gain": 1.0, "az": 0, "dist": 2.0, "solo": 0, "q": 1.0},
    ...
  ],
  "mix": 1.0,
  "master": 1.0
}
```

Saved to `configs/<name>.json` via UI. `version_1.json` is the canonical preset committed to git. User presets (`U shape` etc.) are gitignored.

## Recording

Output WAV saved to project root (`~/Projects/beacon-spatial/`). Uses `Server.record` in SuperCollider (stereo 48kHz). Stop recording before quitting or the file may be truncated.

## Future Ideas

- Replace `PlayBuf` with `SoundIn.ar(0)` for live guitar input from Zoom R24
- Add LFO modulation for spatial movement (currently rejected — keep static)
- Costa Rica deployment: 24/7 beacon with distributed control

## Sensor Interpreter / Mobile Controller (2026-06-07)

First iteration of the web-based sensor controller for the "listener as interpreter" vision (see Kanban epic t_136498e6 and card t_7e7a726d).

- Added "Sensor Interpreter (Live Modulation)" section to the existing web UI (mobile-friendly).
- Supports DeviceOrientation (yaw/pitch/roll) + DeviceMotion (accel, rotation rate).
- Permissions handling (iOS requestPermission on gesture).
- **Editable mappings via in-UI JSON** (no code changes): user edits the textarea, Apply, or uses form-like controls in future.
- Default mapping (tunable, savable):
  - yaw (alpha): azimuth offset, bands "1-6" (low fundamentals), scale 1.0, offset 0
  - pitch (beta): distance, bands "1-6", scale 0.02, offset 2.0
  - roll (gamma): q (bandwidth), bands "7-12", scale 0.5, offset 0
  - accel (magnitude, gravity-subtracted): gain, bands "1-6", scale 0.3, offset 0
- Live toggle + global Influence slider (0-1) for blending sensor contribution.
- Throttled sends (~16-20Hz) to the existing /control endpoint (drives current SC spatializer live).
- Integrated with presets: sensor_mappings saved/loaded in the same config JSON as bands/mix/master.
- "Save with Current Preset", Export JSON, Reset to Default, Apply JSON.
- Current sensor values displayed live.
- Reuses the dark theme and existing OSC forwarding (no changes to beacon.scd or SC engine).
- Syntax verified, added to webui.py.

This enables rapid testing of different sensor-to-harmonic mappings on Android devices + iPhone without redeploys. Aligns with HIT: phone sensors as additional oscillatory processes coupling to the beacon field.

See Kanban for full acceptance and next cards (aggregate client modulation, clean stream receiver, native spatial).

## Sensor Interpreter — Audit & Fixes (2026-06-07)

Audited the Sensor Interpreter end-to-end after Grok session. Confirmed working and fixed three real bugs:

### Verified
- Presets NOT deleted — all 6 JSONs intact in `configs/`. `version_1.json` tracked in git; other 5 gitignored by design (`.gitignore` line 6).
- Save / Load functional: `/save_config`, `/load_config`, `/list_configs` all return 200. `gatherState()` includes `sensor_mappings` key. `applyState()` handles it. Old presets without `sensor_mappings` load fine (key is optional).
- Default mapping (`getDefaultSensorMappings()`) renders into hidden `sensor-mapping-json` textarea at `initSensorUI()` time. UI rebuilds 4 cards + 4 mapping rows. CONFIRMED present.
- Pipeline OSC verified end-to-end: curl → /control → sclang:57120 → scsynth:57110 → recorded WAV. `record/start` + `record/stop` produce stereo 48kHz IEEE Float WAV in project root.

### Bugs fixed
1. **setInterval leak on LIVE toggle** (was `webui.py:1064`): every LIVE/STOP cycle created a new `setInterval` without clearing the previous one. Refactored to single shared `sensorVizInterval`, cleared and re-created on each LIVE press. Also includes the `drawOrientationCanvas()` call that the original duplicate interval was missing.
2. **Duplicate setInterval**: `initSensorUI()` was running its own 160ms viz loop on top of the one in `toggleLiveSensorsUI()`. Removed the init-time loop — viz only runs after user opts in to LIVE.
3. **/control 500 on record/start** (was `webui.py:1237`): Flask did `float(value)` which crashes when the frontend sends a non-numeric label string ("session_…"). Wrapped in try/except, non-numeric values now coerce to 1.0 (truthy) / 0.0.

### Known / open
- **iOS Safari requires HTTPS** for DeviceOrientation/DeviceMotion. If testing from iPhone, the page loads on `http://192.168.x.x:5050` but the sensor permission prompt silently fails. Workarounds: tunnel via `cloudflared`/`ngrok`, or use Android Chrome where sensors work on LAN HTTP for `localhost` (not arbitrary IPs).
- **Permissions button MUST be tapped on iOS** before any sensor event arrives (it's a one-time gesture unlock).
- The `sensor-mapping-json` textarea is hidden (`display:none`) — visible mapping rows are the UI source of truth; the textarea is a compatibility shim.
