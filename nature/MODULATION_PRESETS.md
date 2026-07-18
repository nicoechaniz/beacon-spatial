# Beacon-only modulation presets (T3.3)

Declarative descriptor→OSC mappings for exploratory control of the 13-band
beacon-spatial engine. These are **design choices for routing analysis to
formal control addresses**, not effect recipes or clinical claims.

Source boundary: legacy digital-beacon `sample_modulator.py` beacon half only.
Shaper targets, VoiceParameterStore, and 32-band engine indices are excluded.

## Allowed controls

| Param | OSC address | Notes |
|-------|-------------|--------|
| `master` | `/beacon/master` | global |
| `f1` | `/beacon/f1` | global (retained name; not all engines bind this) |
| `vsrate` | `/beacon/vsource` | global (param name vs address asymmetry preserved) |
| `gain` | `/beacon/gain/{N}` | N = 1..13 |
| `az` | `/beacon/az/{N}` | N = 1..13 |
| `dist` | `/beacon/dist/{N}` | N = 1..13 |
| `q` | `/beacon/q/{N}` | N = 1..12 (BPF only) |
| `on` | `/beacon/on/{N}` | N = 1..13 |

Invalid band indices (0, 14..32, or q on band 13) are rejected at validate time
and never emitted.

## Excluded legacy destinations

- Entire `target_type == "shaper"` surface (master, sidechain, LFO, per-voice)
- `VoiceParameterStore` dual-write on f1 / vsrate
- `digital_beacon` / `harmonic-shaper` imports
- Beacon bands 14..32 and band 0 (legacy 32-slot digital surface)
- Non-designated presets (`tune-to-sample`, `rhythmic-pump`, `phase-manifold-tune`, `default`)

## Presets

### `spectrum-projection`

| Descriptor | Target | scale / offset / max | smooth |
|------------|--------|----------------------|--------|
| `band_0` | `gain` band 1 | 1.5 / 0 / 1.5 | 0.8 |
| `band_1` | `gain` band 7 | 1.5 / 0 / 1.5 | 0.8 |
| `band_2` | `gain` band 13 | 1.5 / 0 / 1.5 | 0.8 |

**Design choice:** low / mid / higher analysis energy illuminates three spatial
gain slots (base, mid-series, highest engine band). Legacy used engine band 14
for the third slot; that index is invalid on the 13-band manifest, so band 13
is used instead. Shaper master row dropped.

### `harmonic-projection`

| Descriptor | Target | scale / offset / max | smooth |
|------------|--------|----------------------|--------|
| `harm_0` … `harm_12` | `gain` bands 1…13 | 1.5 / 0 / 1.5 | 0.8 |
| `rms` | `master` | 1.3 / 0.2 / 1.5 | 0.8 |

**Design choice:** sample energy near each integer multiple of the analysis `f1`
lattice is projected onto the matching engine band gain. Only bands 1..13 are
written (legacy also mapped harmonics 14..32 and shaper voices). Overall RMS
scales master.

### `consonance-gate`

| Descriptor | Target | scale / offset / max | smooth |
|------------|--------|----------------------|--------|
| `harmonicity` | `master` | 1.0 / 0.2 / 1.2 | 0.9 |
| `residual_rms` | `q` band 1 | 1.5 / 0.5 / 2.0 | 0.9 |

**Design choice:** more harmonic content raises overall level; more residual
energy widens the base BPF reciprocal-Q. Legacy shaper shape/master rows and
q max of 3.0 are dropped (max 2.0 aligns with the instrument contract range).

### `timbre-filter`

| Descriptor | Target | scale / offset / max | smooth |
|------------|--------|----------------------|--------|
| `flatness` | `q` band 1 | 1.5 / 0.5 / 2.0 | 0.9 |
| `rms` | `dist` band 1 | 10.0 / 0 / 10.0 | 0.8 |

**Design choice:** noisier / flatter spectra widen the base filter; louder
chunks push base-band distance. Legacy centroid→shaper shape row is dropped.

## Pipeline

```
SampleDescriptor.to_dict()
  → normalize (DESCRIPTOR_RANGES → 0..1)
  → threshold / invert / scale+offset
  → clamp [min_value, max_value]
  → EWMA if smooth > 0
  → OscTransport.send_message(address, [value])
```

Transport is injectable: production uses UDP (`python-osc`); tests use
`RecordingOscTransport` (no listener required).

## Usage

```python
from nature.sample_modulator import RecordingOscTransport, SampleModulator
from nature.sample_layer import SampleDescriptor

rec = RecordingOscTransport()
mod = SampleModulator(transport=rec)
mod.preset_mapping("consonance-gate")
mod.on_descriptor(SampleDescriptor(harmonicity=0.9, residual_rms=0.1))
print(rec.messages)
```

Optional manager (analysis wire + nature load/gain/stop):

```python
from nature.sample_modulation_manager import SampleModulationManager

mgr = SampleModulationManager(transport=rec)
mgr.apply_preset("spectrum-projection")
mgr.nature_load("~/Projects/beacon-spatial/assets/nature-samples/dominicalito_frogs_pond.wav")
mgr.nature_gain(0.5)
```
