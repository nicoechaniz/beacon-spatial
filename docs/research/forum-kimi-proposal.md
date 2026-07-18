---
agent-id: kimi
agent-name: Kimi Code CLI
model: default
timestamp: 2026-05-23T22:34:30-03:00
round: round-1
---

## Candidate Evaluation — beacon-spatial PD Replacement

### Current Architecture Snapshot
- **DSP**: Pd vanilla → `bp~` (6 narrow bands, ~15Hz BW) → `spatializer~` (sin-pan + ITD delay + `1/d` attenuation) → wet/dry mix → `dac~`
- **Control**: Flask (`webui.py`, port 5050) → HTTP POST → `python-osc` UDP → Pd (`udpreceive 9001` + `oscparse` + `route`)
- **Input**: `adc~ 1` (Zoom R24 Ch1) or WAV via test patches
- **Gap**: `spatializer~` is **NOT** HRTF — it's amplitude panning + simple delay. The user explicitly requires true binaural/HRTF spatialization.

---

### Constraint Matrix

| Candidate | Real-time OSC | Live Audio In | True HRTF | Dev Velocity | Scope Discipline | Verdict |
|-----------|:-------------:|:-------------:|:---------:|:------------:|:----------------:|:-------:|
| **SuperCollider** | ✅ Native `/s_new`, `/n_set` | ✅ `SoundIn.ar`, JACK/ALSA, low latency | ✅ ATK Ambisonics→HRTF decode, or `Convolution2` with IR buffers | ✅ SynthDef hot-reload, sclang REPL | ✅ Clean Synth/SynthDef model | **GO** |
| **Python + scipy/sounddevice** | ✅ `python-osc` thread | ⚠️ PortAudio works, but GIL + numpy FFT = drop risk at low latency | ✅ `scipy.signal.fftconvolve` or overlap-add possible | ✅ Fast scripting | ✅ Easy to limit | **NO-GO** |
| **Max/MSP** | ✅ Excellent | ✅ Excellent | ✅ `spat~`, HOA | ✅ Excellent | ✅ Good | **NO-GO** (no Linux native, Wine unusable for pro-audio latency) |
| **REAPER + JSFX** | ❌ No native OSC in JSFX audio thread; ReaScript is control-only | ✅ Excellent | ⚠️ Manual convolution only; no built-in HRTF opcodes | ❌ JSFX is limited EEL2; slow iteration | ❌ DAW paradigm fights "spatializer only" scope | **NO-GO** |
| **Web Audio API** | ❌ No OSC; requires WebSocket bridge adding latency | ⚠️ `getUserMedia`; browsers often mix multi-channel interfaces to stereo | ⚠️ `ConvolverNode` but dynamic azimuth requires IR crossfading (not natively supported) | ⚠️ OK for prototyping | ✅ Good | **NO-GO** |
| **Faust** | ✅ `faust2jack -osc` | ✅ JACK/ALSA, compiled C++ | ✅ Can implement partitioned convolution or use Faust libraries | ⚠️ Compile-run cycle; no REPL | ✅ Excellent functional purity | **MAYBE** |
| **Csound** | ✅ `OSClisten` (k-rate polling) | ✅ JACK/ALSA/PortAudio | ✅ **`hrtfmove2`** — built-in interpolated HRTF (MIT KEMAR) | ⚠️ Orchestra/score paradigm; slower than SC | ✅ Good | **MAYBE** |
| **JUCE** | ✅ `juce_osc` | ✅ Excellent | ✅ `juce::dsp::Convolution` | ❌ C++ boilerplate + compile times | ✅ Good | **NO-GO** (overkill for iteration) |

---

### Ranked Recommendation

#### 🥇 #1 — SuperCollider (`scsynth` + direct OSC from Flask)
**Confidence: HIGH**

**Why it wins:**
- **Real-time OSC**: `scsynth` is designed around OSC. The existing Flask UI can send directly to port `57110` with zero architectural changes beyond the port number. Parameter changes use `/n_set` (instant, sample-accurate with `lag`).
- **Live audio**: `SoundIn.ar(0)` replaces `adc~`. Proven sub-10ms latency via JACK or ALSA.
- **True HRTF**: The **Ambisonics Toolkit (ATK)** provides `FoaPanB.ar` → `FoaDecode.ar(decoder)` where `decoder` is an HRTF kernel (KEMAR, CIPIC, Listen). This is *genuine* binaural convolution, not panning + delay. First-order Ambisonics is perfectly adequate for 40–240Hz (wavelength >> head size, spatial resolution is inherently limited anyway).
- **Velocity**: SynthDefs can be redefined while the server runs. Start with `Buffer.read` + `PlayBuf` for the 2-minute WAV, then swap one line to `SoundIn.ar`.
- **Scope**: SynthDef architecture makes it trivial to keep only spatialization (no LFOs, no FX).

**Risks/Unknowns:**
- **ATK setup**: Requires installing the ATK quark and downloading HRTF datasets (~50–200MB). One-time setup.
- **CPU with 6 bands**: `FoaDecode` uses FIR convolution. 6 parallel B-format panner-decoder chains could be CPU-heavy. Mitigation: sum to single B-format *before* decode (1 decoder for all 6 bands), or use `PartConv` for more efficient partitioned convolution if needed. *Likely not an issue at these low frequencies with modern CPUs.*
- **Crossfading azimuth**: Ambisonics panning is continuous — no IR switching clicks. This is a major win over direct convolution approaches.

#### 🥈 #2 — Csound (`hrtfmove2`)
**Confidence: MEDIUM**

**Why it's viable:**
- `hrtfmove2` is purpose-built for exactly this: dynamic HRTF with built-in interpolation between azimuth/elevation measurements. No manual buffer management.
- MIT KEMAR data ships with Csound.

**Why it's second:**
- OSC integration (`OSClisten`) is polling-based and clunkier than SC's event-driven model.
- Recompiling the orchestra for iteration is slower than SC's hot-reload.
- Less ecosystem support for modern control surfaces/web integration.

---

### GO/NO-GO Decision

**GO — SuperCollider**

---

### Implementation Plan (Max 6 Steps)

| Step | Action | File(s) | Verification |
|------|--------|---------|--------------|
| 1 | Install SuperCollider, sc3-plugins, ATK quark, and HRTF kernels. | system packages | `sclang -e "Quarks.install(\"atk\")"` then recompile SC class library. |
| 2 | Write `beacon.scd`: SynthDef with 6×`BPF`, `FoaPanB` per band, summed B-format → `FoaDecode` (HRTF) → wet/dry → `Out`. Add OSCdef mapping `/beacon/*` → `synth.set`. Start with `PlayBuf` (WAV test). | `beacon.scd` (new) | Run `sclang beacon.scd`; confirm audio playback and OSC response via `webui.py` or `test_sender.py`. |
| 3 | Point Flask UI to scsynth. Change `webui.py` OSC client port from `9001` to `57110`. | `webui.py` (1-line edit) | Move faders in browser; confirm parameter changes in SC Post window. |
| 4 | Switch input from WAV to live audio. Replace `PlayBuf` with `SoundIn.ar(0)` in SynthDef. | `beacon.scd` | Connect Zoom R24; strum guitar; confirm spatialized output in headphones. |
| 5 | Parameter smoothing. Add `.lag(0.05)` to azimuth/gain controls in SynthDef to avoid zipper noise during rapid OSC changes. | `beacon.scd` | Rapidly move azimuth slider; output should glide smoothly. |
| 6 | Freeze deployment. Option A: run `scsynth` headless with `-D 0` and load SynthDef via OSC. Option B: wrap `sclang beacon.scd` in a systemd user service or shell script for show reliability. | `start-beacon.sh` (new) | Reboot; run `./start-beacon.sh`; verify full stack (Zoom → SC → headphones) with UI control. |

---

### Integration with Existing OSC Control Layer

**No bridge needed.** The existing stack is:

```
Browser → HTTP POST → Flask (webui.py) → OSC/UDP → [PORT]
```

Today: port `9001` → Pd  
Tomorrow: port `57110` → `scsynth`

The OSC address schema (`/beacon/gain/1`, `/beacon/az/1`, etc.) is preserved. In `beacon.scd`, map with:

```supercollider
OSCdef(\beaconGain1, { |msg| ~synth.set(\gain1, msg[1]) }, '/beacon/gain/1');
OSCdef(\beaconAz1,   { |msg| ~synth.set(\az1,   msg[1]) }, '/beacon/az/1');
// ... etc
```

This means `webui.py` requires **zero** logic changes — only the target port changes.

---

### Alternative + Trade-off

| Alternative | When to Choose | Trade-off |
|-------------|---------------|-----------|
| **Csound** | If ATK installation fails or SC CPU usage is too high for your hardware. | Simpler HRTF setup (`hrtfmove2` is one opcode) but clunkier control and slower iteration. |
| **Faust** | If you later need a standalone binary with minimal dependencies (e.g., embedding in a hardware box). | Best performance/smallest footprint, but slowest iteration cycle (compile C++ each change). |

---

### Blockers or Risks

| Severity | Risk | Mitigation |
|----------|------|------------|
| **HIGH** | ATK HRTF dataset download/size or network issues. | Fallback to Csound `hrtfmove2` which uses bundled KEMAR data. |
| **MEDIUM** | `FoaDecode` CPU load with 6 summed B-format channels on older hardware. | Sum all 6 bands to a single 4-channel B-format signal, then run **one** `FoaDecode`. This is the recommended architecture anyway. |
| **LOW** | `SoundIn.ar(0)` may need JACK to achieve stable low latency with Zoom R24. | Use `scsynth -H ZoomR24` or start JACK first with `qjackctl`/`jackd`, then boot scsynth. |

---

### Rationale

The project needs **true HRTF** but also needs to **iterate fast** (WAV first, live second) and **retain the existing Flask UI**. SuperCollider is the only candidate that satisfies all three without compromise. Its ATK-based Ambisonics→HRTF pipeline is academically rigorous binaural synthesis, and the OSC layer is native — the web UI talks directly to the audio engine with no middleware. Csound's `hrtfmove2` is a credible fallback if ATK setup becomes problematic, but SC's live-coding workflow will materially accelerate the iteration from WAV sample to live Zoom R24 performance.
