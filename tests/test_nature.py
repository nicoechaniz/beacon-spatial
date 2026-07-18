"""Import + unit tests for nature.resonant_filter and nature.sample_layer (T3.1)."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

import nature
from nature.resonant_filter import ResonantFilter
from nature.sample_layer import SampleDescriptor, SampleLayer
from nature._vendor.nh_mask import harmonic_mask


SR = 48000
F1 = 100.0  # known fundamental for synthetic lattice tests


# ---------------------------------------------------------------------------
# Imports / package surface
# ---------------------------------------------------------------------------


def test_package_exports():
    assert nature.ResonantFilter is ResonantFilter
    assert nature.SampleLayer is SampleLayer
    assert nature.SampleDescriptor is SampleDescriptor


def test_vendor_harmonic_mask_importable():
    assert callable(harmonic_mask)


def test_no_nh_analysis_dependency():
    """resonant_filter must not import the nh_analysis package (vendorized)."""
    import importlib
    import sys

    # Ensure a clean check: vendor path is used, nh_analysis is never loaded.
    sys.modules.pop("nh_analysis", None)
    sys.modules.pop("nh_analysis.mask", None)
    importlib.reload(nature.resonant_filter)
    assert "nh_analysis" not in sys.modules
    assert "nh_analysis.mask" not in sys.modules
    # Vendor module is what supplies harmonic_mask
    assert "nature._vendor.nh_mask" in sys.modules


# ---------------------------------------------------------------------------
# ResonantFilter — harmonic / residual separation
# ---------------------------------------------------------------------------


def _synth_harmonics(
    f1: float,
    sr: int = SR,
    duration_s: float = 1.0,
    n_partials: int = 8,
    noise_amp: float = 0.05,
    seed: int = 0,
) -> np.ndarray:
    """Sum of harmonics on f1 lattice + low-level white noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(sr * duration_s), dtype=np.float64) / sr
    y = np.zeros_like(t)
    for n in range(1, n_partials + 1):
        amp = 1.0 / n
        y += amp * np.sin(2.0 * math.pi * n * f1 * t)
    y = y / (np.max(np.abs(y)) + 1e-12)
    y = y + noise_amp * rng.standard_normal(len(t))
    peak = np.max(np.abs(y))
    if peak > 0:
        y = 0.9 * y / peak
    return y.astype(np.float64)


def _spectral_power(audio: np.ndarray, n_fft: int = 8192) -> tuple[np.ndarray, np.ndarray]:
    """Return (freqs, power) for a Hann-windowed rFFT."""
    windowed = audio * np.hanning(len(audio))
    spec = np.fft.rfft(windowed, n=n_fft)
    power = np.abs(spec) ** 2
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / SR)
    return freqs, power


def _lattice_mask(freqs: np.ndarray, f1: float, half_bw: float = 12.0, n_max: int = 16) -> np.ndarray:
    on = np.zeros_like(freqs, dtype=bool)
    for n in range(1, n_max + 1):
        target = n * f1
        if target >= SR / 2:
            break
        on |= np.abs(freqs - target) <= half_bw
    return on


def _lattice_energy_ratio(audio: np.ndarray, f1: float, sr: int = SR) -> float:
    """Fraction of spectral power within ±12 Hz of n*f1 bins (n=1..16)."""
    freqs, power = _spectral_power(audio)
    total = float(np.sum(power)) + 1e-12
    on = _lattice_mask(freqs, f1)
    return float(np.sum(power[on]) / total)


def test_resonant_filter_separates_harmonics_from_noise():
    """Harmonic component energy concentrates on the f1 lattice; residual does not."""
    # Lattice partials + a strong off-lattice interferer + noise so residual has
    # something real to hold (pure harmonic residual is mostly mask leakage).
    duration_s = 1.0
    t = np.arange(int(SR * duration_s), dtype=np.float64) / SR
    lattice = _synth_harmonics(F1, sr=SR, duration_s=duration_s, n_partials=8, noise_amp=0.0)
    interferer_hz = 150.0  # 1.5 * f1 — deliberately off the integer lattice
    interferer = 0.45 * np.sin(2.0 * math.pi * interferer_hz * t)
    rng = np.random.default_rng(1)
    noise = 0.12 * rng.standard_normal(len(t))
    audio = lattice + interferer + noise
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = 0.9 * audio / peak

    # stability=0 keeps base_bw (40 Hz). With stability=1 the adaptive path
    # narrows to ~20 Hz — less than one STFT bin at n_fft=2048/48k — and
    # harmonic main-lobe energy leaks into residual. Test the comb mask
    # separation at a usable bandwidth.
    rf = ResonantFilter(sr=SR, base_bw=40.0, n_harmonics=16)
    result = rf.separate(audio, f1=F1, flatness=0.0, inharmonicity=0.0, stability=0.0)

    assert "harmonic_audio" in result
    assert "residual_audio" in result
    assert "mask" in result
    assert len(result["harmonic_audio"]) == len(audio)
    assert len(result["residual_audio"]) == len(audio)

    h_audio = result["harmonic_audio"]
    r_audio = result["residual_audio"]

    h_ratio = _lattice_energy_ratio(h_audio, F1)
    r_ratio = _lattice_energy_ratio(r_audio, F1)

    # Harmonic branch: energy concentrates on the f1 lattice.
    assert h_ratio > 0.55, f"harmonic lattice energy ratio too low: {h_ratio:.3f}"
    # Residual must be less lattice-aligned than the harmonic branch.
    assert r_ratio < h_ratio, (
        f"residual lattice ratio ({r_ratio:.3f}) should be < harmonic ({h_ratio:.3f})"
    )
    # With a strong off-lattice interferer, residual must not concentrate on lattice.
    assert r_ratio < 0.50, f"residual still too harmonic: {r_ratio:.3f}"

    # Absolute lattice power should land mostly in the harmonic branch.
    freqs, h_pow = _spectral_power(h_audio)
    _, r_pow = _spectral_power(r_audio)
    on = _lattice_mask(freqs, F1)
    h_lat = float(np.sum(h_pow[on]))
    r_lat = float(np.sum(r_pow[on]))
    assert h_lat > 2.0 * r_lat, (
        f"lattice power not concentrated in harmonic branch: h={h_lat:.3g} r={r_lat:.3g}"
    )

    # Off-lattice interferer (150 Hz) energy should prefer the residual branch.
    half = 10.0
    near_interf = (np.abs(freqs - interferer_hz) <= half)
    h_interf = float(np.sum(h_pow[near_interf]))
    r_interf = float(np.sum(r_pow[near_interf]))
    assert r_interf > h_interf, (
        f"off-lattice interferer not residual-dominant: h={h_interf:.3g} r={r_interf:.3g}"
    )

    desc = rf.descriptors(audio, h_audio, r_audio)
    assert desc["harmonicity"] > 0.2
    assert desc["harmonic_rms"] > 0.0
    for v in desc.values():
        assert math.isfinite(v)


def test_resonant_filter_descriptors_and_bandwidth():
    rf = ResonantFilter(sr=SR, base_bw=40.0, max_bw=200.0)
    # Stable tonal -> narrower; noisy/flat -> wider
    narrow = rf.bandwidth_hz(flatness=0.0, inharmonicity=0.0, stability=1.0)
    wide = rf.bandwidth_hz(flatness=1.0, inharmonicity=1.0, stability=0.0)
    assert narrow < wide
    assert 10.0 <= narrow <= 200.0

    audio = _synth_harmonics(F1, duration_s=0.5)
    chunk_desc = rf.separate_chunk(audio, f1=F1)
    assert set(chunk_desc) >= {"harmonicity", "residual_ratio", "harmonic_rms", "residual_rms"}


# ---------------------------------------------------------------------------
# SampleLayer — load generated WAV, analyze one chunk
# ---------------------------------------------------------------------------


def _write_wav(path: Path, audio: np.ndarray, sr: int = SR) -> None:
    """Write mono float audio as 16-bit PCM WAV."""
    audio = np.asarray(audio, dtype=np.float64)
    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio = audio / peak
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def test_sample_layer_descriptor_on_synthetic_wav(tmp_path: Path):
    """SampleLayer loads a ~1 s WAV and yields a sane SampleDescriptor."""
    pitch_hz = 220.0  # A3 — well inside yin C2–C7 range
    duration_s = 1.0
    t = np.arange(int(SR * duration_s), dtype=np.float64) / SR
    # Strong fundamental + a few partials so yin is reliable
    y = (
        0.7 * np.sin(2 * math.pi * pitch_hz * t)
        + 0.25 * np.sin(2 * math.pi * 2 * pitch_hz * t)
        + 0.1 * np.sin(2 * math.pi * 3 * pitch_hz * t)
    )
    y = 0.9 * y / (np.max(np.abs(y)) + 1e-12)

    # Task asks for /tmp; also keep a copy under pytest tmp for isolation.
    wav_path = Path("/tmp") / "beacon_spatial_nature_test_tone.wav"
    _write_wav(wav_path, y, sr=SR)
    # Mirror into pytest tmp as well (CI-friendly cleanup not required for /tmp)
    _write_wav(tmp_path / "tone.wav", y, sr=SR)

    layer = SampleLayer(
        path=str(wav_path),
        sr=SR,
        chunk_s=0.1,  # 100 ms — enough frames for yin/stft
        f0_beacon_hz=40.4,
        output_device=None,  # no playback in tests
    )
    assert len(layer._y) > 0
    assert len(layer._y_harmonic) == len(layer._y)
    assert len(layer._y_residual) == len(layer._y)

    chunk, h_chunk, r_chunk = layer._next_chunk()
    # Prefer a mid-file chunk (skip possible edge effects at start)
    layer._position = SR // 4
    chunk, h_chunk, r_chunk = layer._next_chunk()
    desc = layer._analyze(chunk, h_chunk, r_chunk)

    assert isinstance(desc, SampleDescriptor)
    assert desc.rms > 0.0
    assert math.isfinite(desc.rms)
    assert math.isfinite(desc.f0_hz)
    assert not math.isnan(desc.f0_hz)
    # f0 near the synthesized pitch (yin tolerance)
    assert desc.f0_hz > 0.0, "f0 should be detected on a pure-ish tone"
    assert abs(desc.f0_hz - pitch_hz) / pitch_hz < 0.08, (
        f"f0={desc.f0_hz:.1f} far from expected {pitch_hz}"
    )

    d = desc.to_dict()
    for key, val in d.items():
        assert math.isfinite(float(val)), f"NaN/Inf in descriptor field {key}={val}"

    # Sanity on spectral fields
    assert desc.centroid > 0.0
    assert 0.0 <= desc.flatness <= 1.0 + 1e-6
    assert desc.band_energy is not None and len(desc.band_energy) == SampleLayer.N_BANDS
    assert desc.harm_energy is not None and len(desc.harm_energy) > 0


def test_sample_layer_missing_file():
    with pytest.raises(FileNotFoundError):
        SampleLayer(path="/tmp/definitely_does_not_exist_beacon_nature.wav", sr=SR)
