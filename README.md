# Harmonic Beacon Spatializer

6-band binaural spatializer for the 40Hz natural harmonic series guitar.
Each string fundamental (40, 80, 120, 160, 200, 240 Hz) gets its own position in 3D space via headphones.

## Files

- `beacon-spatial.pd` — main Pure Data performance patch
- `spatializer~.pd` — binaural spatializer abstraction (keep in same folder)
- `generate.py` — Python script that generates both Pd patches
- `webui.py` — Flask web UI (sends OSC directly to Pd)
- `beacon-osc.json` — starter layout for Open Stage Control (optional)
- `bridge.py` — legacy OSC bridge (not needed with webui.py)
- `requirements.txt` — Python dependencies
- `test_bridge.py` — automated test suite

## Quick Start (Pd only)

1. Open `beacon-spatial.pd` in Pure Data (vanilla 0.55+)
2. **Media > Audio Settings** — input = Zoom R24 Ch1, output = headphones
3. DSP auto-starts. Strum the guitar.
4. Drag number boxes to tweak positions, gains, wet/dry mix.

## Web UI (Flask)

### 1. Install dependencies

    cd ~/Projects/beacon-spatial
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

### 2. Start Pd with the patch

    pd beacon-spatial.pd

### 3. Start the web UI (in another terminal)

    cd ~/Projects/beacon-spatial
    source venv/bin/activate
    python3 webui.py

### 4. Open your browser

    http://localhost:5000

The web UI sends OSC directly to Pd via UDP port 9001. No bridge needed.

## Architecture

```
Browser (http://localhost:5000)
    |
    | HTTP POST /control
    v
Flask (webui.py)
    |
    | OSC UDP :9001
    v
Pd [netreceive 9001] -> [oscparse] -> [route] -> floatatoms -> spatializers
```

## Default Positions

| Freq | Position | Azimuth | Distance |
|------|----------|---------|----------|
| 40Hz | rear/ground | 180 | 2.0 |
| 80Hz | rear-right | 135 | 2.5 |
| 120Hz | left side | -90 | 3.0 |
| 160Hz | front-left | -45 | 2.5 |
| 200Hz | front-right | 45 | 2.0 |
| 240Hz | front-center (orbiting) | 0 + LFO | 1.5 |

## Live Controls

All parameters are number boxes / floatatoms in the Pd patch. Click and drag to change.

- **Gains** (per band): 0–3
- **Azimuth** (left/right position): -180 to 180
- **Distance** (depth): 0–10
- **Wet/Dry** (spatial vs raw): 0–1
- **Master**: 0–2
- **Butterfly Center** (LFO offset): -180 to 180

## Important

- **Headphones required.** The binaural effect only works on headphones.
- **YouTube carries stereo well.** Use it as the primary audio stream.
- **Zoom flattens to mono/compressed.** Use Zoom for video/voice only.
