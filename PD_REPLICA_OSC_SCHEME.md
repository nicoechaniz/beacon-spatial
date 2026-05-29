# PD Replica — OSC Address Scheme

## Overview

The PD replica spatializer listens for OSC on port **9001** (same as the
original Pure Data patch). The web UI (`webui.py` on `:5050`) sends `/beacon/*`
messages to the main sclang on port 57120, and also forwards a copy to port
9001 for the PD replica.

All messages follow the same address scheme as the main 13-band beacon.
No changes to HTTP routes or OSC addresses were needed.

## Architecture

```
webui.py :5050
    │
    ├── OSC :57120 ──→ sclang (beacon.scd) ──→ scsynth :57110 (13-band ATK)
    │
    └── OSC :9001  ──→ sclang (beacon_pd_replica.scd) ──→ scsynth :57110 (6-band PD)
```

The webui.py `/control` handler sends each OSC message to **both** targets.
The try/except block silently handles the case where the PD replica is not
running.

## OSC Address Table (PD Replica)

| Address | Args | Range | Synth Control | Meaning |
|---------|------|-------|---------------|---------|
| `/beacon/gain/N` | float | 0–3 | `gainN` | Band gain (N=1..6) |
| `/beacon/az/N` | float | -180–180 | `azN` | Azimuth degrees (N=1..6) |
| `/beacon/dist/N` | float | 0–10 | `distN` | Distance (N=1..6) |
| `/beacon/q/N` | float | 0.1–50 | `qN` | BPF Q (N=1..6) |
| `/beacon/mix` | float | 0–1 | `wet`, `dry` | Wet/dry balance (wet=val, dry=1-val) |
| `/beacon/master` | float | 0–3 | `master` | Master gain |
| `/beacon/reset` | int | 1 | — | Restore all parameters to defaults |

### Placeholder addresses (accepted but no-op)

| Address | Status | Notes |
|---------|--------|-------|
| `/beacon/solo/+` | ⏳ Placeholder | Wildcard — all solo messages accepted, currently no-op |
| `/beacon/record/start` | ⏳ Placeholder | Recording not yet implemented |
| `/beacon/record/stop` | ⏳ Placeholder | Recording not yet implemented |

These will be implemented when phase 2 sound-design parameters are added.

## External software (Open Stage Control) compatibility

The `beacon-osc.json` template (in project root) also sends `/beacon/gain/N`,
`/beacon/az/N`, `/beacon/dist/N`, `/beacon/wet`, `/beacon/dry`, `/beacon/master`,
and `/beacon/lfo/offset`. The PD replica handles:

- `/beacon/gain/N` ✅ → maps to `gainN`
- `/beacon/az/N`   ✅ → maps to `azN`
- `/beacon/dist/N` ✅ → maps to `distN`
- `/beacon/wet`    ⏳ → not mapped (the PD replica uses `/beacon/mix` for wet)
- `/beacon/dry`    ⏳ → not mapped (derived from mix)
- `/beacon/master` ✅ → maps to `master`
- `/beacon/lfo/offset` → not yet applicable (LFO center is 0.08Hz ±90°)

## Parameter mappings: PD → SuperCollider

These are the exact mapping from PD number boxes to SC synth controls.
The values match the PD patch defaults.

| Band | Freq | Default Gain | Default Az | Default Dist | Default Q |
|------|------|-------------|------------|-------------|-----------|
| 1 | 40 Hz | 1.2 | 180° | 2.0 | 2.67 |
| 2 | 80 Hz | 1.0 | 135° | 2.5 | 5.33 |
| 3 | 120 Hz | 1.0 | -90° | 3.0 | 8.0 |
| 4 | 160 Hz | 1.0 | -45° | 2.5 | 10.67 |
| 5 | 200 Hz | 1.0 | 45° | 2.0 | 13.33 |
| 6 | 240 Hz | 1.3 | 0° | 1.5 | 16.0 |

## Phase 2 placeholders

The following OSCdefs are registered but currently no-op, ready for
phase 2 when new parameters are added to the SynthDef:

- `/beacon/solo/+` — per-band solo/mute (wildcard)
- `/beacon/record/start` — WAV recording
- `/beacon/record/stop` — stop recording
