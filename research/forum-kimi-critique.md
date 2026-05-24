---
agent-id: kimi
agent-name: Kimi Code CLI
model: default
timestamp: 2026-05-23T22:40:48-03:00
round: critique
---

OUT

---

## agree

- **Max/MSP, JUCE, Web Audio API, REAPER+JSFX, and Python+sounddevice are correctly eliminated.** All three peers agree these fail one or more constraints (Linux support, real-time safety, HRTF fidelity, or velocity).
- **Top-2 candidates are SuperCollider and Csound.** Consensus that these are the only viable survivors against the 5 constraints.
- **Both SC and Csound support native JACK/ALSA live input and OSC control.** No disagreement on core capabilities.
- **Existing Flask UI requires minimal or zero logic changes.** All peers agree the OSC address schema can be preserved.
- **True HRTF is the explicit gap to close.** All correctly identified that the current `spatializer~.pd` patch is only amplitude-panning + ITD, not HRTF convolution.

---

## disagree

- **Winner ranking: Grok elevates Csound to #1 based on an unsupported premise.** Grok asserts "Csound 6.18 (installed + libosc.so + /usr/share/csound/hrtf/*.dat)" and therefore "zero new deps." The provided CTX file tree and commit history contain **no evidence** that Csound is installed or that HRTF data files exist on disk. If Csound is *not* pre-installed, its advantage collapses and SC's larger ecosystem becomes the deciding factor.
- **SC CPU characterization: Grok's "12 PartConvs" argument is a strawman against SC.** Grok claims SC requires "manual IR loading + 12 PartConvs" (6 bands × 2 ears). This ignores the Ambisonics path (proposed by Kimi) where 6 bands are panned into a single B-format signal and decoded with **one** `FoaDecode` (2 convolutions total). This is more CPU-efficient than 6 independent HRTF processes.
- **Port strategy: "Perfect drop-in on 9001" is overstated as a differentiator.** Grok frames Csound's ability to bind to 9001 as a unique win. However, SC's `OSCdef` (sclang) can listen on **any** UDP port, including 9001. Both engines can be drop-ins; the port is not a tie-breaker.
- **Csound HRTF distance modeling: Grok implies `hrtf3d` handles distance natively.** Standard Csound HRTF opcodes (`hrtfmove`, `hrtfmove2`) accept azimuth/elevation, not distance. Distance is typically approximated by separate attenuation/IID—similar to the existing `1/d` logic in the PD patch. This is not a differentiating advantage over SC.

---

## peer-gaps(tests/risks)

- **No peer verified actual installed packages.** The CTX does not confirm `csound`, `supercollider`, `sc3-plugins`, or ATK kernels are present. Step 0 for *any* path must be `which csound` / `which sclang`.
- **AAC test file compatibility ignored.** The project contains `extracto_2min.aac`. Neither SC's `Buffer.read` nor Csound's `diskin2` guarantees native AAC support without FFmpeg/libfaad. A conversion to WAV may be required before either engine can iterate.
- **No CPU/latency benchmark for 6-band HRTF on target hardware.** Grok dismisses SC's CPU load with the 12-PartConv strawman, but no one measured the actual load of 6× Csound `hrtf3d` processes vs 1× SC `FoaDecode` at 40–240 Hz.
- **Filter slope / band isolation not analyzed.** The current PD patch uses narrow `bp~` filters. SC's `BPF` and Csound's `butterbp`/`reson` are 12 dB/octave resonant filters; they may bleed more between the 40 Hz harmonic bands than the existing PD implementation. This needs A/B verification.
- **Zoom R24 + JACK latency untested.** All peers assume JACK works, but no one confirmed `jack_lsp | grep zoom` or measured round-trip latency with `jack_iodelay` on the user's specific kernel/PipeWire setup.
- **Extended-source vs point-source HRTF.** A guitar body is an extended source, especially at 40 Hz (wavelength ~8.5 m). All peers treat HRTF as a solved point-source convolution without noting potential near-field/extended-source artifacts at these frequencies.
- **Near-field effect for distance control.** Current PD uses simple `1/d` attenuation. True HRTF distance cues (head shadowing changes with proximity) are not provided by standard far-field KEMAR datasets. None of the peers addressed whether "true HRTF" materially improves distance perception over `1/d` at 40–240 Hz.

---

## adopt-from-peer

- **From Grok: Bind SC to port 9001 for zero-config migration.** Instead of forcing Flask to 57110/57120, run sclang with `OSCdef`s listening on 9001. This makes SC a literal drop-in replacement and preserves all existing `webui.py` and `test_sender.py` configurations without even a one-line port edit.
- **From Claude: Explicit latency verification commands.** Adopt the `jack_iodelay` round-trip target (<20 ms) and `jack_lsp | grep -i zoom` hardware check into the implementation checklist regardless of engine choice.
- **From Claude: HRIR asset strategy.** If the SC path ever shifts to direct convolution (e.g., for higher-order spatial resolution later), use the `Buffer.read` + `Convolution2` pattern with a named SOFA dataset (SADIE-II or CIPIC) rather than relying solely on ATK's bundled kernels.
- **From Grok: Conditional ranking based on `which` results.** If `csound` is present and `sclang` is absent, accept Csound as the immediate #1 for velocity. Do not let ideological preference override empirical tool availability.

---

## revised-rec

| | |
|:---|:---|
| **Winner** | **SuperCollider (#1)** — conditional on `sclang`/`scsynth` being installable or installed. |
| **Runner-up** | **Csound (#2)** — elevate to #1 *only if* verified pre-installed and SC is not. |
| **Verdict** | **GO on SC** with a 1-hour time-boxed fallback to Csound if ATK/sc3-plugins installation fails. |

**Revised 6-Step Plan:**

| Step | Action |
|------|--------|
| 0 | **Verify tools:** `which sclang csound jackd`. If only `csound` exists, swap to Csound path immediately. |
| 1 | **Convert test asset:** `ffmpeg -i extracto_2min.aac extracto_2min.wav` to ensure Buffer.read/diskin2 compatibility. |
| 2 | **Install & configure:** SC + sc3-plugins + ATK quark + HRTF kernels (or Csound if flipped). |
| 3 | **Write engine:** `beacon.scd` with 6× `BPF` → `FoaPanB` per band → summed B-format → **single** `FoaDecode` (HRTF) → `Out`. Bind `OSCdef`s to port **9001** (drop-in). |
| 4 | **Test with WAV:** `PlayBuf` mode. Verify OSC response from existing `webui.py` without code changes. |
| 5 | **Switch to live input:** Replace `PlayBuf` with `SoundIn.ar(0)`. Validate Zoom R24 via JACK. Add `.lag(0.05)` on azimuth/gain to prevent zipper noise. |
| 6 | **Latency sanity:** Run `jack_iodelay`; confirm <20 ms round-trip. If xruns occur, switch JACK buffer size (`-p 256` / `-n 2`). |

**Architecture clarification (addressing CPU concern):**
- **Not 12 convolutions.** Pan all 6 bands into one first-order B-format signal (4 channels: W, X, Y, Z). Decode to binaural with **one** `FoaDecode` (2 FIR convolutions). This is the CPU-efficient, academically standard path for multi-source binaural rendering and directly rebuts Grok's "12 PartConvs" claim.

**Blockers/Risks (unchanged but refined):**
- **HIGH (conditional):** ATK HRTF dataset download fails or is large. Fallback: use Csound's bundled KEMAR data *if* Csound is installed, or switch SC to `PartConv` with a manually loaded SOFA file.
- **MEDIUM:** Filter bleed between 40 Hz bands with 12 dB/octave `BPF`. Mitigation: cascade two `BPF`s per band or use `BBandPass` (sc3-plugins) for steeper slope; verify by spectroscope.
- **LOW:** JACK/Zoom R24 xruns. Mitigation: tune `-p` (period) and `-n` (periods) flags; consider PipeWire-JACK if ALSA backend is unstable.

---

## rank-peers

1. **Claude** — Most rigorous risk framing. Correctly distinguished SC direct-convolution vs ATK paths, acknowledged Csound's bundled-HRTF advantage, proposed concrete verification commands (`jack_iodelay`, `jack_lsp`), and admitted the HRIR-source unknown. Best balance of technical depth and epistemic humility.
2. **Grok** — Strong operational focus (zero frontend changes, port 9001, installed-base argument) and good constraint-driven elimination of losers. However, the entire recommendation rests on the unsupported claim that Csound is pre-installed with HRTF assets. Without that claim, the ranking inverts. Additionally, the "12 PartConvs" characterization of SC is a misrepresentation of the Ambisonics path. Would rank #1 if the installation claims were independently verified.
