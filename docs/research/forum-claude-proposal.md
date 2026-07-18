---
agent-id: claude
agent-name: Claude Code
model: default
timestamp: 2026-05-23T22:29:52-03:00
round: round-1
---

# R1: Replace PD — Spatial Audio Engine Selection

## Findings by severity

**[HIGH] Max/MSP — NO-GO (Linux)**
No native Linux build; Wine + real-time audio is unreliable. Eliminate.

**[HIGH] Python + sounddevice — NO-GO for production**
GIL + GC pauses cause real-time glitches at low buffer sizes. Workable for offline HRIR design, unsafe as the live engine driving a Zoom R24 on stage. Eliminate as primary.

**[HIGH] JUCE — NO-GO (velocity)**
C++ build/iterate loop violates constraint 4. Eliminate.

**[MED] Web Audio — NOT RECOMMENDED**
`PannerNode` with HRTF is real (MIT KEMAR), but routing Zoom R24 input into the browser on Linux requires `snd-aloop`/PipeWire loopback; fragile for live use, and OSC needs a WebSocket bridge. Keep as fallback only.

**[MED] REAPER + JSFX / IEM / SPARTA — VIABLE BUT HEAVY**
SPARTA `sparta_binauraliser` is real HRTF; REAPER has OSC. But DAW model fights the live-control dataflow and the iteration cycle is GUI-bound. Overkill for spatial-only first iteration.

**[OK] Faust — STRONG #3**
`-osc`, JACK target, recompile-and-reload loop; HRTF via convolution feasible. Slightly more plumbing than SC for HRIR loading; pick if SC scheduler proves problematic.

**[OK] Csound — STRONG #2**
`hrtfmove2`/`hrtfstat` are mature real-HRTF opcodes with bundled MIT-KEMAR HRIR files. OSC native (`OSClisten`). Closest semantic match to current PD patch (text DSL, `butterbp`, JACK in). Lowest friction to first sound.

**[OK] SuperCollider — RECOMMENDED #1**
- OSC: first-class on both `scsynth` (UDP 57110) and `sclang` (UDP 57120). Flask can keep sending `/band/N/*`; sclang `OSCdef` maps to `Synth.set`.
- Live in: `SoundIn.ar([n,m])` over JACK; Zoom R24 surfaces as JACK ports.
- True HRTF: `Convolution2.ar` with HRIR buffers from a SOFA set (SADIE-II or MIT-KEMAR), or ATK `FoaDecode`/`HoaBinaural` for an Ambisonic-then-binaural path.
- Velocity: sclang REPL hot-reloads `SynthDef`s without restarting `scsynth`; six bands = six `Synth` instances of one def.
- Scope: dataflow is naturally per-source, no DAW timeline, no unwanted effect chain.

## Ranking & justification

1. **SuperCollider** — best balance of real-time safety, HRTF maturity, hot-reload velocity, and clean OSC mapping to the existing Flask layer. Mature binaural ecosystem (ATK, sc3-plugins).
2. **Csound** — shortest path to a first binaural sound because `hrtfmove2` is a single opcode with bundled HRIRs; pick this if SC's HRIR/SOFA setup blocks progress in the first session.

## Plan (≤6)

1. Install `supercollider`, `sc3-plugins`, ensure JACK is running and Zoom R24 ports visible (`jack_lsp`).
2. Obtain HRIR set: SADIE-II (or MIT-KEMAR shipped with sc3-plugins) — convert/load left+right impulse responses into `Buffer.read`.
3. Author `engine_sc/spatial.scd`: one `SynthDef \band` = `BPF` → per-side `Convolution2` (HRIR selected by azimuth bin) → distance attenuation/IID → output bus. Boot script instantiates 6 `Synth(\band)` with band index 0..5.
4. Author OSC layer in same file: `OSCdef`s for `/band/{N}/gain`, `/band/{N}/az`, `/band/{N}/dist` → `synths[N].set(...)`. Match current Flask message names verbatim.
5. Source switch: start with `PlayBuf.ar` reading `extracto_2min.aac` (converted to WAV); replace with `SoundIn.ar(zoomChannel)` once parity confirmed.
6. Point Flask UI at SC: change OSC target port (PD `9001` → sclang `57120`) in `web/app.py`; keep message schema identical so the UI is unchanged.

## Edits + paths (proposed; not applied — R1 is no-tools)

- `engine_sc/spatial.scd` — new; SynthDef + OSCdefs + boot block.
- `engine_sc/hrir/` — new; SOFA/WAV HRIR assets.
- `web/app.py` — change OSC destination port constant from `9001` to `57120`.
- `README.md` — update run instructions (boot order: jackd → scsynth/sclang → Flask).
- `Makefile`/scripts (optional) — `make engine` to start sclang with `spatial.scd`.
- Leave PD patch in tree under `legacy/` for reference until parity reached.

## Verify commands

- JACK + device: `jack_lsp | grep -i zoom`
- Boot engine: `sclang engine_sc/spatial.scd` (watch for "OSCdef" registration log)
- OSC parity (no UI): `oscsend localhost 57120 /band/0/gain f 0.5` then `/band/0/az f 90`
- End-to-end: launch Flask, move a slider, confirm left/right balance shifts and HRIR colouration audible on headphones
- Latency sanity: `jack_iodelay` round-trip; target <20 ms in/out

## Alternative + tradeoff

**Csound path**: replace step 3 with `instr 1`: `kfreq` bandpass → `hrtfmove2 asig, kaz, kel, "hrtf-44100-left.dat", "hrtf-44100-right.dat"`. Pros: first sound in one evening; HRIRs bundled. Cons: per-source instr instances and global mixing are clunkier than SC's bus/Synth model; community momentum for binaural research lives more in SC/Faust.

## Confidence + unknowns

- Confidence **HIGH** that SuperCollider satisfies all 5 constraints.
- Confidence **MED-HIGH** that SC beats Csound for this project specifically — driven by hot-reload velocity and Flask integration cleanliness, not by DSP capability.
- Unknowns: (a) which HRIR set the user prefers (SADIE-II vs MIT-KEMAR vs CIPIC) — affects timbre, not architecture; (b) Zoom R24 JACK latency on the user's specific kernel/PipeWire setup; (c) whether 40 Hz fundamental band needs FIR rather than `Convolution2` partitioning at chosen block size (low-freq HRIR is long).

## Rationale

The constraints rule out commercial/closed (Max), high-latency-prone (Python), and GUI-heavy (REAPER) candidates. Among the survivors, SuperCollider uniquely combines (i) a hard-real-time C++ server, (ii) a live-coding control language with OSC parity to the existing Flask schema, and (iii) production-grade HRTF tooling — without forcing a rewrite of the web UI. Csound is the safety net because `hrtfmove2` is the lowest-effort path to a verified binaural output if SC integration stalls.

**GO** on SuperCollider, contingent on confirming HRIR source in step 2.
