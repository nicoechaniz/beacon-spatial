# `beacon-osc.json` — unmapped OSC addresses

Open Stage Control template for the Harmonic Beacon. Most faders/knobs use
the live SuperCollider scheme (`/beacon/gain/N`, `/beacon/az/N`,
`/beacon/dist/N`, `/beacon/master`).

JSON cannot hold comments, so unmapped addresses are documented here instead
of inside the template (avoids unknown keys that Open Stage Control may
reject or ignore unpredictably).

## Addresses with no destination in the current engines

| Widget id | Address in template | Status | Notes |
|-----------|---------------------|--------|-------|
| `wet` | `/beacon/wet` | **Unmapped** | Main engine (`beacon.scd` :57120) and PD replica (:9001) use a single **`/beacon/mix`** (0..1) for wet/dry balance (`wet = mix`, `dry = 1 − mix`). |
| `dry` | `/beacon/dry` | **Unmapped** | Same as above — no separate dry OSCdef. |
| `lfo_offset` | `/beacon/lfo/offset` | **Unmapped** | Main engine is static (no LFO). PD replica has fixed butterfly AM / pan LFO; center is not OSC-exposed. |

## Mapped addresses in this template

| Pattern | Engine support |
|---------|----------------|
| `/beacon/gain/1` … `/beacon/gain/6` | Main (1..13) and replica (1..6) |
| `/beacon/az/1` … `/beacon/az/6` | Main and replica |
| `/beacon/dist/1` … `/beacon/dist/6` | Main and replica |
| `/beacon/master` | Main and replica (template range max is 2; engine allows 0..3) |

## Gaps vs the live 13-band engine

This layout only exposes bands **1–6** (legacy 6-band UI). The main engine
also has bands **7–13**, plus `/beacon/q/N`, `/beacon/solo/N`,
`/beacon/record/start`, `/beacon/record/stop`, and `/beacon/reset`, which
are not present in the template.

To drive wet/dry from Open Stage Control today, replace the wet/dry faders
with one fader addressed to **`/beacon/mix`** (0..1), or map both UI widgets
to compute a single mix value externally.
