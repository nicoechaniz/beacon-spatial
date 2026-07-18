"""Focused tests for beacon-only descriptor modulation (T3.3)."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import nature
from nature.sample_layer import SampleDescriptor
from nature.sample_modulation_manager import SampleModulationManager
from nature.sample_modulator import (
    BEACON_PARAMS,
    DESCRIPTOR_RANGES,
    EXCLUDED_LEGACY_TARGETS,
    N_BEACON_BANDS,
    N_BEACON_Q_BANDS,
    PRESET_NAMES,
    ModulationTarget,
    RecordingOscTransport,
    SampleModulator,
    build_preset,
    _normalize_descriptor,
)


NATURE_DIR = Path(__file__).resolve().parents[1] / "nature"
RUNTIME_MODULES = (
    "sample_modulator.py",
    "sample_modulation_manager.py",
    "sample_layer.py",
    "resonant_filter.py",
    "__init__.py",
)


# ---------------------------------------------------------------------------
# No Shaper / digital_beacon imports in runtime nature source
# ---------------------------------------------------------------------------


def _collect_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
                names.add(node.module)
    return names


def test_no_shaper_or_digital_beacon_import_in_nature_runtime():
    """Target runtime source must not import Shaper / digital_beacon paths."""
    forbidden_roots = {
        "digital_beacon",
        "harmonic_shaper",
        "harmonic-shaper",
        "VoiceParameterStore",
    }
    # Also scan raw source for forbidden symbols that might appear without import.
    forbidden_substrings = (
        "digital_beacon",
        "VoiceParameterStore",
        "harmonic_shaper",
        "harmonic-shaper",
        "from digital_beacon",
        "import digital_beacon",
    )
    for name in RUNTIME_MODULES:
        path = NATURE_DIR / name
        assert path.is_file(), f"missing runtime module {path}"
        text = path.read_text(encoding="utf-8")
        imports = _collect_imports(path)
        for bad in forbidden_roots:
            assert bad not in imports, f"{name} imports {bad}"
        for sub in forbidden_substrings:
            # Allow documentation mentions in comments/docstrings only via
            # EXCLUDED list and explicit "excluded" prose — still ban import lines.
            if sub.startswith("from ") or sub.startswith("import "):
                assert sub not in text, f"{name} contains import of {sub}"
        # Hard ban: no shaper target application API
        assert "_apply_shaper" not in text, f"{name} still has shaper apply path"
        assert "SHAPER_PARAMS" not in text, f"{name} still defines SHAPER_PARAMS"


def test_package_exports_modulator():
    assert nature.SampleModulator is SampleModulator
    assert nature.RecordingOscTransport is RecordingOscTransport
    assert nature.SampleModulationManager is SampleModulationManager
    assert nature.N_BEACON_BANDS == 13


# ---------------------------------------------------------------------------
# Validation / invalid target rejection
# ---------------------------------------------------------------------------


def test_rejects_shaper_target_type():
    t = ModulationTarget("rms", "master", target_type="shaper")
    with pytest.raises(ValueError, match="only target_type 'beacon'"):
        t.validate()


def test_rejects_unknown_param():
    with pytest.raises(ValueError, match="unknown beacon param"):
        ModulationTarget("rms", "sidechain").validate()


def test_rejects_band_required_missing():
    with pytest.raises(ValueError, match="requires band"):
        ModulationTarget("rms", "gain").validate()


def test_rejects_legacy_32_band_indices():
    with pytest.raises(ValueError, match="out of range"):
        ModulationTarget("band_0", "gain", band=14).validate()
    with pytest.raises(ValueError, match="out of range"):
        ModulationTarget("band_0", "gain", band=32).validate()
    with pytest.raises(ValueError, match="out of range"):
        ModulationTarget("band_0", "gain", band=0).validate()


def test_rejects_q_on_hpf_band_13():
    with pytest.raises(ValueError, match="out of range"):
        ModulationTarget("flatness", "q", band=13).validate()
    # band 12 is the last valid q band
    ModulationTarget("flatness", "q", band=N_BEACON_Q_BANDS).validate()


def test_rejects_global_param_with_band():
    with pytest.raises(ValueError, match="must not set band"):
        ModulationTarget("rms", "master", band=1).validate()


def test_set_targets_never_installs_invalid():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    with pytest.raises(ValueError):
        mod.set_targets([ModulationTarget("rms", "gain", band=20)])
    assert mod.list_targets() == []


def test_invalid_target_never_emitted_even_if_forced():
    """Defense in depth: band 14 cannot produce an OSC write."""
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    # Bypass set_targets validation by mutating after a valid install is impossible;
    # instead call _apply_beacon with an invalid target object.
    bad = ModulationTarget("band_0", "gain", band=14)
    mod._apply_beacon(bad, 0.5)
    assert rec.messages == []
    assert not any("/beacon/gain/14" in a for a in rec.addresses())


# ---------------------------------------------------------------------------
# Normalize / clamp / threshold / invert / smoothing
# ---------------------------------------------------------------------------


def test_normalize_descriptor_midpoint():
    lo, hi = DESCRIPTOR_RANGES["rms"]
    mid = (lo + hi) / 2.0
    assert abs(_normalize_descriptor("rms", mid) - 0.5) < 1e-9
    assert _normalize_descriptor("rms", hi + 10) == 1.0
    assert _normalize_descriptor("rms", lo - 10) == 0.0


def test_clamp_and_scale_emit_bounded_value():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.add_target(
        ModulationTarget(
            "rms",
            "master",
            scale=10.0,
            offset=0.0,
            min_value=0.1,
            max_value=0.4,
        )
    )
    # raw rms in range high → normalized ~1 → would be 10, clamped to 0.4
    mod.on_descriptor(SampleDescriptor(rms=0.5))
    assert rec.last() is not None
    addr, args = rec.last()
    assert addr == "/beacon/master"
    assert args == [pytest.approx(0.4)]


def test_threshold_forces_min_value():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.add_target(
        ModulationTarget(
            "rms",
            "master",
            scale=1.0,
            offset=0.0,
            min_value=0.05,
            max_value=1.0,
            threshold=0.5,  # on normalized 0..1
        )
    )
    # raw 0.0 → normalized 0 < 0.5 → min_value
    mod.on_descriptor(SampleDescriptor(rms=0.0))
    assert rec.last()[1] == [pytest.approx(0.05)]


def test_invert_flips_normalized_before_scale():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.add_target(
        ModulationTarget(
            "flatness",
            "master",
            scale=1.0,
            offset=0.0,
            min_value=0.0,
            max_value=1.0,
            invert=True,
            smooth=0.0,
        )
    )
    # flatness range 0..1; raw 0.25 → norm 0.25 → invert 0.75
    mod.on_descriptor(SampleDescriptor(flatness=0.25))
    assert rec.last()[1] == [pytest.approx(0.75)]


def test_ewma_smoothing_moves_toward_new_value():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    t = ModulationTarget(
        "rms",
        "master",
        scale=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=1.0,
        smooth=0.5,
    )
    mod.add_target(t)
    # First frame: value V, smoothed = 0.5*V + 0.5*0
    # rms max range 0.5 → raw 0.5 → norm 1.0 → value 1.0
    mod.on_descriptor(SampleDescriptor(rms=0.5))
    first = rec.messages[0][1][0]
    assert abs(first - 0.5) < 1e-9  # alpha 0.5 from 0 → 0.5
    # Second identical frame: 0.5*1 + 0.5*0.5 = 0.75
    mod.on_descriptor(SampleDescriptor(rms=0.5))
    second = rec.messages[1][1][0]
    assert abs(second - 0.75) < 1e-9


# ---------------------------------------------------------------------------
# Descriptor → bounded OSC addresses
# ---------------------------------------------------------------------------


def test_global_and_band_addresses():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.set_targets([
        ModulationTarget("rms", "master", scale=1.0, max_value=1.0),
        ModulationTarget("f0_hz", "f1", scale=180.0, offset=20.0, min_value=20.0, max_value=200.0),
        ModulationTarget("f0_ratio", "vsrate", scale=1.0, offset=0.0, min_value=0.25, max_value=2.0),
        ModulationTarget("band_0", "gain", band=3, scale=1.0, max_value=1.5),
        ModulationTarget("rms", "az", band=5, scale=180.0, offset=-90.0, min_value=-180.0, max_value=180.0),
        ModulationTarget("rms", "dist", band=2, scale=10.0, max_value=10.0),
        ModulationTarget("flatness", "q", band=4, scale=1.0, max_value=2.0),
        ModulationTarget("rms", "on", band=1, scale=1.0, max_value=1.0),
    ])
    desc = SampleDescriptor(
        rms=0.25,
        f0_hz=110.0,
        f0_ratio=2.0,
        flatness=0.5,
        band_energy={0: 0.5},
    )
    mod.on_descriptor(desc)
    addrs = rec.addresses()
    assert "/beacon/master" in addrs
    assert "/beacon/f1" in addrs
    assert "/beacon/vsource" in addrs
    assert "/beacon/gain/3" in addrs
    assert "/beacon/az/5" in addrs
    assert "/beacon/dist/2" in addrs
    assert "/beacon/q/4" in addrs
    assert "/beacon/on/1" in addrs
    # Never emit 32-band legacy addresses
    for a in addrs:
        if a.startswith("/beacon/gain/") or a.startswith("/beacon/az/"):
            n = int(a.rsplit("/", 1)[-1])
            assert 1 <= n <= N_BEACON_BANDS


def test_on_descriptor_accepts_dict():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.add_target(ModulationTarget("harmonicity", "master", scale=1.0, offset=0.0, max_value=1.0))
    mod.on_descriptor({"harmonicity": 0.8, "rms": 0.1})
    assert rec.last()[0] == "/beacon/master"
    assert rec.last()[1][0] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(PRESET_NAMES))
def test_each_preset_installs_valid_beacon_only_targets(name: str):
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.preset_mapping(name)
    targets = mod.list_targets()
    assert targets, f"preset {name} produced no targets"
    for t in targets:
        assert t.target_type == "beacon"
        t.validate()
        assert t.param in BEACON_PARAMS
        if t.band is not None:
            assert 1 <= t.band <= N_BEACON_BANDS
            if t.param == "q":
                assert t.band <= N_BEACON_Q_BANDS


def test_spectrum_projection_addresses():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.preset_mapping("spectrum-projection")
    desc = SampleDescriptor(band_energy={0: 0.5, 1: 0.5, 2: 0.5})
    mod.on_descriptor(desc)
    addrs = set(rec.addresses())
    assert addrs == {"/beacon/gain/1", "/beacon/gain/7", "/beacon/gain/13"}
    assert "/beacon/gain/14" not in addrs


def test_harmonic_projection_bands_1_to_13_only():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.preset_mapping("harmonic-projection")
    harm = {i: 0.4 for i in range(32)}
    mod.on_descriptor(SampleDescriptor(rms=0.25, harm_energy=harm))
    gain_bands = sorted(
        int(a.rsplit("/", 1)[-1])
        for a in rec.addresses()
        if a.startswith("/beacon/gain/")
    )
    assert gain_bands == list(range(1, 14))
    assert "/beacon/master" in rec.addresses()
    assert not any(
        a.startswith("/beacon/gain/") and int(a.rsplit("/", 1)[-1]) > 13
        for a in rec.addresses()
    )


def test_consonance_gate_and_timbre_filter_emit():
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)

    mod.preset_mapping("consonance-gate")
    mod.on_descriptor(SampleDescriptor(harmonicity=0.9, residual_rms=0.2))
    assert "/beacon/master" in rec.addresses()
    assert "/beacon/q/1" in rec.addresses()
    # No shaper-like addresses
    assert all(a.startswith("/beacon/") for a in rec.addresses())

    rec.clear()
    mod.preset_mapping("timbre-filter")
    mod.on_descriptor(SampleDescriptor(flatness=0.4, rms=0.25))
    assert "/beacon/q/1" in rec.addresses()
    assert "/beacon/dist/1" in rec.addresses()


def test_unknown_preset_raises():
    mod = SampleModulator(transport=RecordingOscTransport())
    with pytest.raises(ValueError, match="unknown preset"):
        mod.preset_mapping("tune-to-sample")
    with pytest.raises(ValueError, match="unknown preset"):
        build_preset("rhythmic-pump")


def test_excluded_legacy_documented():
    assert "shaper" in EXCLUDED_LEGACY_TARGETS
    assert "VoiceParameterStore" in EXCLUDED_LEGACY_TARGETS
    assert "digital_beacon" in EXCLUDED_LEGACY_TARGETS


# ---------------------------------------------------------------------------
# Manager seam + nature player routes
# ---------------------------------------------------------------------------


def test_manager_feed_descriptor_and_nature_routes():
    rec = RecordingOscTransport()
    mgr = SampleModulationManager(transport=rec)
    mgr.apply_preset("spectrum-projection")
    mgr.feed_descriptor(SampleDescriptor(band_energy={0: 0.5, 1: 0.2, 2: 0.1}))
    assert any(a.startswith("/beacon/gain/") for a in rec.addresses())

    rec.clear()
    mgr.nature_load("/tmp/example_nature.wav")
    mgr.nature_gain(0.5)
    mgr.nature_stop()
    assert rec.messages[0][0] == "/beacon/nature/load"
    assert rec.messages[0][1][0].endswith("example_nature.wav")
    assert rec.messages[1] == ("/beacon/nature/gain", [0.5])
    assert rec.messages[2] == ("/beacon/nature/stop", [])


def test_manager_nature_gain_clamped():
    rec = RecordingOscTransport()
    mgr = SampleModulationManager(transport=rec)
    mgr.nature_gain(2.5)
    assert rec.last()[1] == [1.0]
    mgr.nature_gain(-1.0)
    assert rec.last()[1] == [0.0]


def test_manager_attach_layer_wires_callback():
    rec = RecordingOscTransport()
    mgr = SampleModulationManager(transport=rec)
    mgr.apply_preset("consonance-gate")

    class FakeLayer:
        def __init__(self):
            self.on_descriptor = None

    layer = FakeLayer()
    mgr.attach_layer(layer)  # type: ignore[arg-type]
    assert layer.on_descriptor is not None
    # Bound methods are not identical by `is` across attribute access; call through.
    layer.on_descriptor(SampleDescriptor(harmonicity=1.0, residual_rms=0.0))
    assert rec.messages, "wired callback should drive modulator"
    assert "/beacon/master" in rec.addresses()
    assert "/beacon/q/1" in rec.addresses()


# ---------------------------------------------------------------------------
# Recorder-based end-to-end demo (used in report)
# ---------------------------------------------------------------------------


def test_recorder_descriptor_to_osc_demo():
    """End-to-end: descriptor dict → preset → bounded OSC log."""
    rec = RecordingOscTransport()
    mod = SampleModulator(transport=rec)
    mod.preset_mapping("harmonic-projection")

    desc = SampleDescriptor(
        rms=0.3,
        harm_energy={i: (0.1 * ((i % 5) + 1)) for i in range(20)},
    )
    mod.on_descriptor(desc)

    assert rec.messages, "expected OSC messages"
    for addr, args in rec.messages:
        assert addr.startswith("/beacon/")
        assert isinstance(args, list) and len(args) == 1
        assert math.isfinite(float(args[0]))
        if "/gain/" in addr:
            band = int(addr.rsplit("/", 1)[-1])
            assert 1 <= band <= 13
            assert 0.0 <= args[0] <= 1.5

    # Snapshot for human report readability
    demo_log = [(a, round(float(v[0]), 4)) for a, v in rec.messages]
    assert any(a == "/beacon/master" for a, _ in demo_log)
    assert any(a == "/beacon/gain/1" for a, _ in demo_log)
