---
agent-id: codex
agent-name: Codex
model: default
timestamp: 2026-05-23T22:41:20-03:00
round: synthesis
---

## TL;DR
Use **Csound first**, but treat it as a fast implementation spike rather than a permanent architectural bet. It best matches the first-iteration goal if the claimed local Csound/HRTF assets are real: true HRTF, native OSC, live JACK input, and no Flask changes. **SuperCollider remains the clear fallback and longer-term option** if Csound is not installed, HRTF assets are missing, or Csound iteration feels too slow.

**Final Approach**
**GO: Csound as the first replacement engine.**

Evidence from the agent round favors Csound for the immediate v1 because it can preserve the current OSC layer on port `9001`, use native OSC receive, process JACK/ALSA live input, and use built-in HRTF opcodes such as `hrtfmove` / `hrtfmove2`. That directly satisfies the five constraints with the smallest migration surface.

Top 2 ranking:

1. **Csound**
   Best fit for the first scoped migration: six bandpass paths, OSC-controlled gain/azimuth/distance, true HRTF, WAV-first then live input, no LFOs/effects.

2. **SuperCollider**
   Stronger long-term live-coding and spatial-audio environment, especially with ATK / Ambisonics. It loses the immediate slot only because ATK/HRTF setup and port/control decisions add more setup risk than Csound for v1.

**Adopted Recommendations**
Preserve the existing Flask OSC schema and port if possible: `webui.py` should keep sending to `127.0.0.1:9001`.

Implement a new `beacon-spatial.csd` with:

- WAV input mode first, likely via `diskin2`
- live input mode second, via `inch`
- six bandpass filters at `40/80/120/160/200/240 Hz`
- per-band `gain`, `az`, and `dist`
- `hrtfmove2` or related Csound HRTF opcode
- simple distance attenuation
- parameter smoothing, e.g. `portk`, to prevent zipper noise
- no LFOs, delays, modulation, or extra effects in v1

**Open Disagreements**
The only serious disagreement is Csound vs SuperCollider.

Csound wins if the local claim is true: `csound`, OSC support, and HRTF `.dat` files are already available.

SuperCollider wins if Csound is missing, the HRTF opcodes/assets are not available, or Csound’s edit/run cycle slows iteration too much.

Also unresolved: at `40-240 Hz`, HRTF cues may be subtle. The wavelength is large relative to the head, so the audible improvement over PD’s current ITD/panning may be modest. That does not invalidate the HRTF requirement, but it makes early A/B testing essential.

**Implementation Order**
1. Verify engine availability: `csound`, OSC support, and HRTF data files.
2. Convert the test asset to WAV if needed; AAC may not work directly in either Csound or SC.
3. Build `beacon-spatial.csd` with WAV input and six static bands.
4. Add OSC mappings for existing `/beacon/...` messages on port `9001`.
5. Add HRTF spatialization and parameter smoothing.
6. A/B against the current PD patch using the same WAV and OSC gestures.
7. Switch input from WAV to Zoom R24 live input through JACK.
8. Document startup commands and keep the PD patch as legacy fallback.

**Integration Plan**
No Flask rewrite for the Csound path.

Current:

```text
Browser -> Flask web UI -> python-osc UDP -> Pd on 9001
```

Target:

```text
Browser -> Flask web UI -> python-osc UDP -> Csound on 9001
```

The OSC addresses should remain unchanged. Only the audio engine process changes.

**Rollback**
Keep the current PD patch working until Csound passes:

- WAV playback
- OSC parameter control
- HRTF spatial movement
- live Zoom R24 input
- latency/xrun sanity check

If Csound fails any critical item, switch to SuperCollider with this architecture:

```text
6 bandpass signals -> per-band Ambisonic panning -> summed B-format -> one binaural HRTF decoder
```

**Confidence**
Confidence is **medium-high** for Csound as the fastest v1 path, conditional on verifying the installed Csound/HRTF assets.

Main unknowns:

- whether Csound and HRTF data are actually present
- whether AAC needs conversion to WAV
- Zoom R24 JACK latency on the target machine
- perceptual improvement of HRTF at very low harmonic frequencies
- exact mapping of “distance” since most HRTF datasets are far-field and point-source oriented
