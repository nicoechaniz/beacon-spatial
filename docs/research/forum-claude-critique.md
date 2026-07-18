---
agent-id: claude
agent-name: Claude Code
model: default
timestamp: 2026-05-23T22:35:39-03:00
round: critique
---

---
agent-id: claude
agent-name: Claude Code
model: default
timestamp: 2026-05-23T22:38:00-03:00
round: round-2
---

# R2: critique-all

## Agree

- **All three: Max/MSP, REAPER, Web Audio, Python, JUCE are NO-GO** on identical reasoning (Linux/Wine, DAW paradigm, browser audio fragility, GIL, C++ velocity). Unanimous on the elimination set.
- **All three: SC and Csound are the only viable finalists.** Disagreement is only on ordering.
- **All three: Flask UI requires no logic change** — only target port differs by candidate.
- **All three: scope discipline → SynthDef/instr-per-band is the right structure**, drop LFO.

## Disagree

- **Ranking #1**: I and kimi pick SC; grok picks Csound. Grok's strongest argument — *Csound HRIR `.dat` files already on disk at `/usr/share/csound/hrtf/` and OSC port 9001 unchanged* — is concrete evidence I underweighted. If verified, that's a one-evening-to-first-sound advantage that beats my "HRIR source unknown" caveat in step 2.
- **Kimi's port choice (57110) + `OSCdef`**: technically inconsistent. `OSCdef` lives in **sclang (57120)**, not scsynth (57110). Sending Flask to 57110 means crafting raw `/n_set` messages with node IDs, not the friendly `/beacon/gain/1` schema. Either route Flask → sclang:57120 (my proposal) or rewrite Flask to address scsynth nodes directly. Kimi's plan as written won't work.
- **Csound OSC ergonomics**: kimi calls `OSClisten` "clunkier"; grok treats it as native and fine. Grok is closer to right — `OSClisten` polls at k-rate which is ≤1 ms granularity at typical ksmps, indistinguishable from event-driven for control rates.

## Peer-gaps (tests/risks)

- **All three (incl. me) missed the physics gap**: at 40–240 Hz the wavelength is 1.4–8.6 m vs ~18 cm head radius. Spectral HRTF cues are near-zero in this band; localization is almost entirely ITD-driven. "True HRTF" on a 40 Hz sine is essentially a delay + small ILD. Risk: user expects audible binaural movement but gets mostly ITD behaviour identical to the current PD patch's `delread~`. Constraint #3 ("not just amplitude + ITD") may be perceptually unreachable in this band regardless of engine. **This deserves an early A/B test before committing to either engine.**
- **Grok**: no mention of partition size / latency for FIR HRIRs at the 40 Hz band (long IRs needed for accuracy at low f); didn't address Ambisonic sum-then-decode efficiency.
- **Kimi**: ATK quark install path on Linux is non-trivial; HRTF dataset for ATK decoders is not bundled and source isn't named. Risk severity tagged HIGH by kimi itself — fair.
- **Mine (R1)**: didn't flag the 40 Hz physics issue; didn't propose B-format-sum-then-single-decode (kimi's win); didn't notice Csound HRIR data is already installed (grok's win).
- **All three**: no one proposed a quick perceptual A/B test (PD vs new engine, same input, headphones) before full migration.

## Adopt-from-peer

1. **From grok**: verify `/usr/share/csound/hrtf/*.dat` presence and keep OSC port **9001** if Csound is chosen — zero Flask delta is a real advantage I undervalued.
2. **From kimi**: **sum the 6 BPF outputs to one B-format bus, then a single `FoaDecode` HRTF** (SC path) — cuts CPU ~6× vs per-band convolution, and is the architecturally correct way to do Ambisonic encoding anyway.
3. **From kimi**: `.lag(0.05)` on azimuth/gain controls to suppress zipper noise on OSC updates.
4. **From both**: add a perceptual sanity test step before step 2 of my plan.

## Revised-rec

**GO. Tie-break Csound vs SC by a 30-minute spike, not by debate.**

Concrete: spend one evening on Csound first (grok's path) because the bundled HRIR + zero-Flask-change makes "first binaural sound" reachable fastest. If `hrtfmove2` produces audibly worse spatialization than PD's existing panner at 40–240 Hz (likely candidate for the perceptual gap above), or if Csound iteration drag bites, fall back to SC with the kimi-style sum-then-single-FoaDecode topology.

Revised plan order:
1. **Perceptual A/B baseline**: record 30 s of PD output for two static azimuths (±90°) on headphones. This is the bar to beat.
2. **Csound spike**: 60-line `.csd` with 6 × `butterbp` → `hrtfmove2(asig, kaz, 0, ...)` → mix → `outs`. OSC on 9001 with existing schema. Drop in.
3. **A/B test** Csound vs PD baseline. If clearly better (or even just modular/cleaner with HRTF data path opened up) → commit, mark PD legacy.
4. **If Csound disappoints** → SC path with single-decode topology + `.lag` smoothing, Flask port → 57120, ATK quark + HRTF set install.
5. Live-input swap (`inch` or `SoundIn.ar`) after WAV parity.
6. `run-engine.sh` + README update; move PD to `legacy/`.

## Rank-peers

1. **grok** — strongest empirical claim (installed assets, port preservation, drop-in feasibility). Concrete confidence score. Weakest on architecture nuance and didn't flag the low-freq HRTF caveat.
2. **kimi** — best constraint matrix and best DSP topology suggestion (B-format sum-then-decode, `.lag`). Loses points for the 57110/`OSCdef` inconsistency and underweighting Csound's installed-assets advantage.

Both peers improved my R1 in non-overlapping ways; the revised plan adopts pieces from each.
