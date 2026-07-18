---
agent-id: grok
agent-name: Grok Build
model: default
timestamp: 2026-05-23T22:36:55-03:00
round: critique
---

**R2: Critique-All (SELF: grok)**

### Per-Peer Critique

**grok R1 (self-critique)**  
Accurate on the decisive installed-state evidence: Csound 6.18 + libosc.so + `/usr/share/csound/hrtf/*.dat` files are explicitly present, OSC port 9001 matches the current Flask/python-osc client with zero edits, and `hrtfmove*` / `hrtfstat` give true measured HRTF in <10 lines. Correctly flagged the existing PD `spatializer~` (sin-pan + single `delread~` ITD) as insufficient and the hard-wired LFO on band 6 as scope violation. The "drop-in" integration plan is the strongest practical advantage.  

Weaknesses: (1) "hrtf3d" is imprecise terminology (standard opcodes are `hrtfmove`/`hrtfmove2`/`hrtfstat`); (2) understated the real iteration difference between a `.csd` edit+restart cycle vs sclang REPL for tuning filter Q, HRTF distance curves, and azimuth feel during the WAV-to-live phase; (3) over-stated "only candidate that satisfies every constraint with native primitives" — SC also satisfies them once the (small) setup gap is closed. Confidence 82 was reasonable but would be higher with explicit low-frequency HRTF smoke test.

**claude R1**  
Excellent architectural motivation: SC + ATK gives a clean per-band `SynthDef`, first-class OSC (`/n_set` with lag), hot-reload, and the linear B-format sum-then-single-decode pattern is a genuine CPU win for independent azimuths. Strong on why the project feels like a "live instrument" that benefits from a performance-oriented environment.  

Gaps/flaws: (1) Assumes ATK quark + full HRTF kernels (SADIE-II / CIPIC / MIT-KEMAR) are a trivial "one evening" step — CTX only guarantees `sc3-plugins`, not ATK or the ~50-200 MB datasets; this is unsupported and directly impacts constraint 4 (velocity); (2) the required 1-line port change in `webui.py` (9001 → 57110/57120) is trivial but still a coupling that Csound avoids; (3) under-weights the fact that the existing dev surface (Flask + python-osc + `test_sender.py`) is already wired for 9001 and a text-patch style (Pd); introducing sclang is a larger context switch than a new `.csd`.

**kimi R1**  
Best-structured response: constraint matrix and risk table are clear and useful. Correctly ranks SC #1 on workflow and ecosystem while giving Csound a fair "MAYBE" on polling OSC and orchestra/score paradigm. Good mitigation (sum to single B-format before decode) and explicit OSCdef mapping examples.  

Weaknesses: (1) "SC is the only candidate that satisfies all three without compromise" is too absolute — Csound has zero new deps and exact port match, which *is* a material reduction in compromise for this snapshot; (2) for 40-240 Hz narrow-band guitar content the practical difference between k-rate `OSClisten` polling and SC's event-driven model is small (parameters change on musical time, not at audio rate); (3) same unsupported ATK assumption as claude.

### Synthesis

**Agree**  
- Max/MSP, REAPER+JSFX, Web Audio, real-time Python+sounddevice/scipy, and JUCE are correctly eliminated by at least one hard constraint on this Linux + Zoom R24 + low-latency live-input + "first iteration spatial only" brief.  
- Only SuperCollider and Csound remain viable.  
- OSC address schema (`/beacon/gain/N`, `/beacon/az/N`, `/beacon/dist/N`, `/beacon/wet`, etc.) must be preserved verbatim so the Flask layer and Open Stage Control layout stay untouched.  
- Start with WAV/`diskin2`/`PlayBuf`, prove spatial image on headphones, then swap to `inch`/`SoundIn.ar` + JACK.  
- Parameter smoothing (`.lag`, portamento, or `portk`) is mandatory to avoid zipper noise.  
- Both engines are JACK-native and can talk to the Zoom R24 at acceptable latency with proper `-b`/`-B`.

**Disagree**  
- Primary ranking split is real and evidence-based, not style. grok weighted "what is actually on disk today + zero UI delta + immediate HRTF data files" highest because constraint 4 (development velocity) and "iterate quickly with WAV then live" are explicit. claude and kimi weighted long-term spatial ecosystem, REPL ergonomics, and Ambisonics path higher. Both are defensible; the tie-breaker is the CTX statement of installed artifacts.  
- The "hot-reload makes SC decisively faster" claim is overstated for this narrow scope. After the initial `SynthDef` / instrument block is written, the iteration loop is "move slider in browser → hear change" for both; the edit cycle difference is seconds.  
- SC proposals treat ATK/HRIR acquisition as low-risk; this is unsupported by the common CTX (only `sc3-plugins` listed). Csound's `/usr/share/csound/hrtf/*.dat` + `libosc.so` are explicitly called out.

**Peer-gaps (tests/risks)**  
- No proposal includes a minimal low-frequency HRTF smoke test: single 40 Hz band, slow azimuth sweep 0→180°, confirm audible head-shadow/timbre shift (not just level) on the actual guitar sample.  
- Guitar is an extended radiating source ~1 m wide, not a point source at ear distance. "az/dist" controls will be artistic; this should be documented rather than assumed literal.  
- No latency or xrun numbers with the actual Zoom R24 + JACK + target buffer sizes on this machine.  
- Csound-specific: behavior of `hrtfmove2` at <100 Hz with OSC-driven k-rate updates and the narrow bp~ bands.  
- SC-specific: time-to-working-HRTF on this exact install (ATK quark + dataset download success/failure).  
- Perceptual delta at 40-240 Hz: how much "truer" does the HRTF version actually sound versus a well-tuned constant-power + ITD for this harmonic-series guitar? (May be modest; still required by constraint 3.)

**Adopt-from-peer**  
- Kimi's constraint matrix and risk table format — clear and should be carried forward into any implementation checklist.  
- Claude + kimi B-format sum-then-decode pattern: correct and efficient when independent per-band azimuths are required (pan each band in B-format, sum 4 channels, single HRTF decode). For Csound v1 we will stay with direct per-band `hrtfmove2` (simpler, matches installed path); the pattern is noted for any future Ambisonics expansion.  
- Explicit verify command lists and "start with file input, then live" discipline.  
- Smoothing on every controllable parameter.  
- Preserve exact current OSC namespace (no renaming).

**Revised recommendation**  
After full round-1 critique, **grok R2 reaffirms Csound as the top candidate for the immediate task**.

**GO/NO-GO: GO — Csound**

**Rationale (synthesis)**: It is the only option for which every required primitive (OSC receive, true HRTF with shipped data, live JACK input, bandpass, mix) is already on disk, requires no new downloads or quark installs, and allows the entire existing control layer (`webui.py`, `test_sender.py`, browser UI, Open Stage Control) to remain byte-for-byte unchanged. This directly minimizes risk against constraints 2 and 4. SC is a strong, principled #2 that would be preferred if the project charter were "build a long-term spatial-audio research platform" or if ATK + datasets were already confirmed present.

**Blockers/risks (updated)**  
- Low: `.csd` syntax learning curve for a Python-heavy team (mitigation: structure mirrors current Pd graph — 6 parallel bp + spatial + sum).  
- Low: `hrtfmove2` azimuth/elevation/distance scaling feel on an extended guitar source (artistic mapping, not literal).  
- Medium: optimal bandpass bandwidths for 40 Hz harmonic isolation without beating or loss of "liveness" (must be tuned against the 2-min sample).  
- None critical.

**Recommended implementation order (merged, ≤6 steps)**  
1. Author `beacon-spatial.csd`: orchestra header (sr=48000, ksmps suitable for low latency), `OSCinit(9001)`, 6 band instruments (or one re-usable instrument) using `butterbp`/`reson` + `hrtfmove2` (or `hrtfstat`) with `k-az`, `k-dist`, `k-gain` driven from OSC, wet/dry/master, `outch`.  
2. Add clean input switch: `diskin2` for WAV test mode, `inch` for live Zoom R24 (JACK).  
3. Write or extend a one-line `run-csound.sh` / README section with the exact command (`csound -+rtaudio=jack -iadc -odac -b 128 -B 512 --sample-rate=48000 ...`).  
4. Drive with **unmodified** `test_sender.py` + browser at :5050; confirm values appear and audio spatializes.  
5. A/B comparison (Pd vs Csound on same OSC stream) + low-frequency HRTF smoke test + parameter smoothing.  
6. Tune filters/HRTF curves on the real guitar, document, deprecate the PD `spatializer~` subgraph, mark v1 complete.

**Integration plan with existing OSC control layer**  
Zero delta. `webui.py` continues to send to `127.0.0.1:9001`. Stop `pd`, start `csound ... beacon-spatial.csd`. All POST /control routes, Open Stage Control layout, and message schema remain identical. This is the cleanest possible engine swap.

**Rank of the three R1 proposals (for this specific CTX)**  
1. grok R1 — highest fidelity to the concrete installed artifacts and minimal-surprise integration.  
2. kimi R1 — clearest risk framing and verification discipline.  
3. claude R1 — strongest "why this is a performance instrument" motivation and architectural clarity.

**Final note**: The round demonstrates healthy disagreement on weighting (installed minimalism vs ecosystem/repl ergonomics). The evidence in the shared CTX — explicit Csound HRTF data + exact port match + no new assets — makes Csound the rational, lowest-risk choice for the stated first-iteration goal. SC remains the logical next engine to prototype once the spatial guitar is working in performance and the team has cycles to invest in the ATK path.

R2 complete (grok). Synthesis delivered. Ready for codex or implementation decision.
