# Harmonic Beacon Spatializer

6-band binaural spatializer for the 40Hz natural harmonic series guitar.
Each string fundamental (40, 80, 120, 160, 200, 240 Hz) gets its own position in 3D space via headphones.

**Current engine:** SuperCollider (scsynth + ATK FOA + sclang OSCdefs) + Flask web UI.

## Quick Start

### 1. One-time setup (venv)

    cd ~/Projects/beacon-spatial
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

### 2. Start everything (recommended)

    ./start-beacon.sh

This starts (in order):
- JACK (if not running) with the project ALSA settings
- scsynth on 57110 (2 in / 2 out)
- sclang + `beacon.scd` (QT offscreen, OSC on 57120)
- Flask web UI from venv on http://localhost:5050

Press **Ctrl-C** in the terminal to cleanly stop all four.

### 3. Open browser

    http://localhost:5050

Move faders — changes go live via OSC to the 6-band spatializer.

### Legacy Pd version

The original Pd patch (`beacon-spatial.pd`) and related files remain in the tree for reference but are no longer the active target.

## Files

- `start-beacon.sh` — master launcher (JACK + scsynth + sclang + web UI)
- `beacon.scd` — SuperCollider synthdef + 6-band FoaPanB + OSCdef receivers (ATK)
- `webui.py` — Flask web UI (dark theme, 6-band + mix controls)
- `beacon-osc.json` — Open Stage Control layout (optional)
- `requirements.txt`, `venv/` — Python deps
- `extracto_2min.wav` — source loop (guitar harmonic series)
- Legacy: `beacon-spatial.pd`, `spatializer~.pd`, `generate.py`, `bridge.py`

## Architecture (current)

```
Browser (http://localhost:5050)
    |
    | HTTP POST /control
    v
Flask (webui.py, venv python)
    |
    | OSC UDP :57120
    v
sclang (beacon.scd) -- OSCdef --> synth.set()
    |
    | /n_set etc.
    v
scsynth -u 57110 (JACK backend)
    |
    | 6x BPF -> FoaPanB(az,1/dist) -> B-format sum -> FoaDecode(Listen) + dry
    v
JACK -> headphones (binaural)
```

## Web UI (standalone)

If you want to run pieces manually (e.g. during SC dev):

    # terminal 1
    jackd -d alsa -r 44100 -p 256 -n 2

    # terminal 2
    scsynth -u 57110 -i 2 -o 2

    # terminal 3
    QT_QPA_PLATFORM=offscreen sclang -D beacon.scd

    # terminal 4
    source venv/bin/activate && python3 webui.py

## Default Positions (per-band)

| Freq | Position | Azimuth | Distance |
|------|----------|---------|----------|
| 40Hz | rear/ground | 180 | 2.0 |
| 80Hz | rear-right | 135 | 2.5 |
| 120Hz | left side | -90 | 3.0 |
| 160Hz | front-left | -45 | 2.5 |
| 200Hz | front-right | 45 | 2.0 |
| 240Hz | front-center | 0 | 1.5 |

## Live Controls (Web UI + OSC)

- **Gains** (per band): 0–3
- **Azimuth** (left/right): -180..180 deg
- **Distance** (depth): 0–10
- **Wet / Dry / Master**

All changes have 50 ms lag on gain/az per spec. No LFOs, no reverb, plain FoaPanB + 1/distance.

## Important

- **Headphones required.** Binaural spatialization (Listen HRTF via ATK) only works on headphones.
- Requires SuperCollider + ATK quark + kernels (~/.local/share/ATK/kernels/FOA/decoders/listen).
- The launcher and .scd hard-code the absolute path to `extracto_2min.wav`.



