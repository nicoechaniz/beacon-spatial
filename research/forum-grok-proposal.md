---
agent-id: grok
agent-name: Grok Build
model: default
timestamp: 2026-05-23T22:31:37-03:00
round: round-1
---

**R1: propose-best-solution**

### Findings by severity
**Critical (current PD + scope):**
- spatializer~.pd (line 5-21) implements only sin-based constant-power + single delread~ ITD. Explicitly "not true HRTF".
- LFO hard-wired on band 6 + metro/snapshot (violates "spatial distribution only").
- 6 independent bp~ + spatializer~ + sum graph works, but engine replacement required for HRTF.

**Disqualifiers (fail ≥1 constraint on Linux + installed stack):**
- Max/MSP: no native Linux, Wine audio xruns. Fails 2+4.
- REAPER+JSFX: not installed, DAW overhead, no native HRTF UGen, manual conv in JSFX heavy. Fails velocity + scope.
- Web Audio API: no raw UDP OSC receive (needs bridge), browser getUserMedia latency unsuitable for Zoom R24 pro input, no JACK. Fails 1+2.
- Python scipy/sounddevice custom: OSC trivial (python-osc already dep), WAV fast, but real-time partitioned FFT conv for 6×2 HRTF channels + stable low-lat callback on Linux audio is high-risk (GC, no native scheduler). HRTF from scratch (phase, near-field, ITD/ILD correct) requires significant DSP code + IR assets. Fails 2+3 reliably without months of tuning.

**Viable:**
- SuperCollider (scsynth 3.13 + sclang + sc3-plugins present): passes 1-5. Native OSC, SoundIn/JACK, PartConv+HOA binaural possible. But HRTF requires either HOA indirection or manual IR loading + 12 PartConvs. More boilerplate than needed.
- **Csound 6.18 (installed + libosc.so + /usr/share/csound/hrtf/*.dat)**: passes all 5 cleanly. Direct OSC opcodes (OSCinit/OSClisten), hrtf3d/hrtfmove opcodes with shipped 44.1/48 kHz .dat files (true measured HRTF, az+dist), inch/diskin2, butterbp/reson, JACK/ALSA native, zero new deps.

### Top 2 ranking + justification
1. **Csound** — lowest friction, highest fidelity match. HRTF is first-class opcode + data files (constraint 3 satisfied in <10 lines). OSC receive is native in the same .csd as audio engine (constraint 1). Live input + WAV swap trivial. Scope discipline easy (no LFO instr). Installed, Linux/JACK pro-audio ready.
2. **SuperCollider** — strong #2. Same OSC/JACK strengths, larger spatial community, but HRTF path longer (HOA or custom PartConv) and no pre-shipped simple per-source HRTF like Csound's.

### Winning option: Csound
**GO/NO-GO: GO**

**Blockers/risks:**
- Minor: hrtf3d az range/elev handling + best filter Q to preserve harmonic isolation (test with extracto_2min). IR data is for head, guitar is extended source — acceptable for v1.
- None critical (all pieces present).

**Recommended implementation order (plan-max-6):**
1. Create `beacon-spatial.csd` skeleton: orchestra header, OSCinit on 9001, 6 parallel band instruments (bp + gain + hrtf3d + outs).
2. Map exact addresses: `/beacon/gain/N`, `/beacon/az/N`, `/beacon/dist/N`, `/beacon/wet`, `/beacon/dry`, `/beacon/master` (drop lfo/offset per scope).
3. Add conditional input: chnget or cmdline for "wav" mode (diskin2) vs live (inch). Master mix + outch.
4. Test OSC roundtrip using existing `test_sender.py` + webui.py (no changes).
5. JACK + Zoom R24 validation (low-lat -b/-B, ch1 in).
6. Update README.md + add `run-csound.sh` helper; mark Pd as deprecated.

**Edits+paths:**
- `beacon-spatial.csd` (new, ~60-80 LOC engine)
- `README.md` (small run section + deprecate note)
- (optional) `research/csound-notes.md`
- No changes to `webui.py`, `beacon-osc.json`, `bridge.py`, `generate.py`, `*.pd`, `test_*.py`

**Integration plan with existing OSC control layer:**
Zero delta to Flask layer. webui.py already does `SimpleUDPClient("127.0.0.1", 9001).send_message("/beacon/...", val)`. Csound OSCinit will consume the identical packets on the same port. Stop `pd`, run `csound ... beacon-spatial.csd`. Browser UI, Open Stage Control layout, and all POST /control calls remain untouched. Perfect drop-in.

**Verify-commands:**
- `csound --version`
- `csound -+rtaudio=jack -iadc -odac -b 128 -B 512 --sample-rate=48000 beacon-spatial.csd`
- `python3 test_sender.py` (or browser at :5050) while csound runs; watch console for OSC.
- `jack_lsp -c` (confirm Zoom ch1 → csound:0)
- `aplay -l` + `jackd -d alsa ...` fallback

**Alternative + tradeoff:**
- SC: more flexible long-term (Ambisonics path), but +20-30 LOC + IR prep for equivalent HRTF quality. Choose if team already lives in sclang.
- Python custom: fastest iteration for Python-only devs, but 2-3× effort on stable HRTF engine + download IRs + risk of xruns during performance. Only if "stay in Python" is hard requirement.

**Confidence + unknowns: 82**
High on fit (installed + opcodes + data + OSC match + 0 frontend change). Unknowns: exact hrtf3d distance scaling feel on guitar, optimal bp~ bandwidths for 40 Hz series isolation without beating, team tolerance for Csound syntax (vs Python).

**Rationale (concise):** Csound is the only candidate that satisfies every constraint with native primitives already on disk, requires no new packages/assets, and allows the Flask/OSC UI layer to be left 100% intact. It is the minimal, correct, pro-audio path from "Pd constant-power" to "true HRTF spatial distribution" while respecting scope discipline and dev velocity. 

Task complete. Ready for implementation of beacon-spatial.csd.
