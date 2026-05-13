# Harmonic Beacon Spatializer

6-band binaural spatializer for the 40Hz natural harmonic series guitar.
Each string fundamental (40, 80, 120, 160, 200, 240 Hz) gets its own position in 3D space via headphones.

## Files

- `beacon-spatial.pd` — main Pure Data performance patch
- `spatializer~.pd` — binaural spatializer abstraction (keep in same folder)
- `generate.py` — Python script that generates both Pd patches
- `bridge.py` — OSC bridge (Open Stage Control -> Pd)
- `beacon-osc.json` — starter layout for Open Stage Control
- `requirements.txt` — Python dependencies

## Quick Start (Pd only)

1. Open `beacon-spatial.pd` in Pure Data (vanilla 0.55+)
2. **Media > Audio Settings** — input = Zoom R24 Ch1, output = headphones
3. DSP auto-starts. Strum the guitar.
4. Drag number boxes to tweak positions, gains, wet/dry mix.

## Web UI with Open Stage Control

### 1. Install bridge dependencies

    pip install -r requirements.txt

### 2. Start the bridge

    python3 bridge.py

The bridge listens for OSC on UDP port 9000 and forwards commands to Pd via TCP port 8000.

### 3. Start Open Stage Control

Download from https://openstagecontrol.ammd.net/

Launch with the starter layout:

    open-stage-control --load beacon-osc.json --send 127.0.0.1:9000

Or import `beacon-osc.json` from the Open Stage Control editor and adjust the layout visually.

### 4. Open the Pd patch

    pd beacon-spatial.pd

Make sure `[netreceive 8000 1]` is loaded (bottom right of patch). The UI will now control all parameters remotely.

## Architecture

```
Open Stage Control (browser/phone/tablet)
    |
    | OSC UDP :9000
    v
bridge.py
    |
    | FUDI/TCP :8000
    v
Pd [netreceive 8000 1] -> [route b1 b2 ...] -> floatatoms -> spatializers
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

All parameters are message boxes / floatatoms in the Pd patch. Click and drag to change.

- **Gains** (per band): 0-3
- **Azimuth** (left/right position): -180 to 180
- **Distance** (depth): 0-10
- **Wet/Dry** (spatial vs raw): 0-1
- **Master**: 0-2
- **Butterfly Center** (LFO offset): -180 to 180

## Important

- **Headphones required.** The binaural effect only works on headphones.
- **YouTube carries stereo well.** Use it as the primary audio stream.
- **Zoom flattens to mono/compressed.** Use Zoom for video/voice only.
