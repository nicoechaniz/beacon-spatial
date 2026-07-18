"""Beacon-only sample descriptor modulation (T3.3).

Turns SampleDescriptor frames into OSC control messages for the living
beacon-spatial engine. This is a deliberate split of the legacy digital-beacon
modulator: only ``target_type == "beacon"`` is supported. Shaper /
VoiceParameterStore / digital_beacon / harmonic-shaper paths are excluded.

Pipeline per target
-------------------
1. Read raw descriptor from ``SampleDescriptor.to_dict()``.
2. Normalize to 0..1 via ``DESCRIPTOR_RANGES``.
3. Apply threshold (below → min_value), optional invert, scale/offset.
4. Clamp to [min_value, max_value].
5. Optional EWMA smoothing (``smooth`` as alpha toward the new value).
6. Emit a single OSC write through an injectable transport.

Allowed OSC surface (beacon-spatial formalization for this module)
------------------------------------------------------------------
Globals:
  - ``master``  → ``/beacon/master``
  - ``f1``      → ``/beacon/f1``
  - ``vsrate``  → ``/beacon/vsource``  (legacy param name; address is vsource)

Per-band (band index 1..N_BEACON_BANDS, q limited to 1..N_BEACON_Q_BANDS):
  - ``gain`` → ``/beacon/gain/{band}``
  - ``az``   → ``/beacon/az/{band}``
  - ``dist`` → ``/beacon/dist/{band}``
  - ``q``    → ``/beacon/q/{band}``
  - ``on``   → ``/beacon/on/{band}``

Band bounds follow the 13-band spatial engine (not the legacy 32-band
digital-beacon surface). Invalid band targets raise at validate time and are
never emitted.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, Union

from nature.sample_layer import SampleDescriptor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contract-aligned bounds (13-band living engine)
# ---------------------------------------------------------------------------

# Spatial engine band count (manifest). Legacy digital-beacon used 32.
N_BEACON_BANDS = 13
# BPF reciprocal-Q is only defined for bands 1..12 (band 13 is HPF).
N_BEACON_Q_BANDS = 12

BEACON_GLOBAL_PARAMS = frozenset({"master", "f1", "vsrate"})
BEACON_BAND_PARAMS = frozenset({"gain", "az", "dist", "q", "on"})
BEACON_PARAMS = BEACON_GLOBAL_PARAMS | BEACON_BAND_PARAMS

BEACON_OSC_GLOBAL = {
    "master": "/beacon/master",
    "f1": "/beacon/f1",
    "vsrate": "/beacon/vsource",
}

# Analysis descriptors still use 32 spectral slots from SampleLayer; only the
# OSC *targets* are clamped to the 13-band engine.
N_ANALYSIS_BANDS = 32

BASE_DESCRIPTORS = frozenset({
    "rms", "f0_hz", "f0_ratio", "centroid", "bandwidth", "flatness",
})
DERIVED_DESCRIPTORS = frozenset({
    "rms_delta", "rms_smooth", "f0_stability", "centroid_delta", "inharmonicity",
    "harmonicity", "residual_ratio", "harmonic_rms", "residual_rms",
})
BAND_DESCRIPTORS = frozenset(f"band_{i}" for i in range(N_ANALYSIS_BANDS))
HARMONIC_DESCRIPTORS = frozenset(f"harm_{i}" for i in range(N_ANALYSIS_BANDS))

DESCRIPTOR_RANGES: Dict[str, Tuple[float, float]] = {
    "rms": (0.0, 0.5),
    "f0_hz": (20.0, 200.0),
    "f0_ratio": (0.5, 4.0),
    "centroid": (20.0, 8000.0),
    "bandwidth": (20.0, 8000.0),
    "flatness": (0.0, 1.0),
    "rms_delta": (-0.2, 0.2),
    "rms_smooth": (0.0, 0.5),
    "f0_stability": (0.0, 1.0),
    "centroid_delta": (-1000.0, 1000.0),
    "inharmonicity": (0.0, 1.0),
    "harmonicity": (0.0, 1.0),
    "residual_ratio": (0.0, 1.0),
    "harmonic_rms": (0.0, 0.5),
    "residual_rms": (0.0, 0.5),
}
for _i in range(N_ANALYSIS_BANDS):
    DESCRIPTOR_RANGES[f"band_{_i}"] = (0.0, 1.0)
    DESCRIPTOR_RANGES[f"harm_{_i}"] = (0.0, 1.0)

VALID_DESCRIPTORS = (
    BASE_DESCRIPTORS | DERIVED_DESCRIPTORS | BAND_DESCRIPTORS | HARMONIC_DESCRIPTORS
)

# Built-in preset names retained from digital-beacon (beacon half only).
PRESET_NAMES = frozenset({
    "spectrum-projection",
    "harmonic-projection",
    "consonance-gate",
    "timbre-filter",
})

# Explicitly excluded legacy destinations (documentation + tests).
EXCLUDED_LEGACY_TARGETS = frozenset({
    "shaper",
    "VoiceParameterStore",
    "digital_beacon",
    "harmonic-shaper",
    # Legacy 32-band beacon band indices (14..32) and any band 0.
    "beacon.band_14..32",
    "beacon.band_0",
})


def _normalize_descriptor(name: str, raw: float) -> float:
    """Map a raw descriptor to a 0..1 range using declared (min, max)."""
    lo, hi = DESCRIPTOR_RANGES.get(name, (0.0, 1.0))
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (raw - lo) / (hi - lo)))


def max_band_for_param(param: str) -> int:
    """Return the inclusive upper band index allowed for a band param."""
    if param == "q":
        return N_BEACON_Q_BANDS
    return N_BEACON_BANDS


# ---------------------------------------------------------------------------
# Transport seam (tests inject a recorder; production uses UDP)
# ---------------------------------------------------------------------------


class OscTransport(Protocol):
    """Minimal send surface shared by UDP clients and test fakes."""

    def send_message(self, address: str, value: Any) -> None:
        ...


class RecordingOscTransport:
    """In-memory OSC recorder for unit tests and demos (no UDP)."""

    def __init__(self) -> None:
        self.messages: List[Tuple[str, Any]] = []

    def send_message(self, address: str, value: Any) -> None:
        self.messages.append((address, value))

    def clear(self) -> None:
        self.messages.clear()

    def addresses(self) -> List[str]:
        return [a for a, _ in self.messages]

    def by_address(self, address: str) -> List[Any]:
        return [v for a, v in self.messages if a == address]

    def last(self) -> Optional[Tuple[str, Any]]:
        return self.messages[-1] if self.messages else None


def make_udp_transport(host: str = "127.0.0.1", port: int = 57120) -> OscTransport:
    """Build a python-osc UDP client implementing OscTransport."""
    from pythonosc.udp_client import SimpleUDPClient

    return SimpleUDPClient(host, port)


# ---------------------------------------------------------------------------
# Target mapping
# ---------------------------------------------------------------------------


@dataclass
class ModulationTarget:
    """Declarative mapping from one descriptor field to one beacon parameter."""

    descriptor: str
    param: str
    band: Optional[int] = None
    scale: float = 1.0
    offset: float = 0.0
    min_value: float = 0.0
    max_value: float = 1.0
    smooth: float = 0.0  # 0..1 EWMA alpha toward the new value (legacy math)
    threshold: float = 0.0
    invert: bool = False
    active: bool = True
    # Fixed target type for this module; accepted in from_dict for legacy JSON.
    target_type: str = "beacon"

    _smoothed_value: float = field(default=0.0, repr=False)

    def validate(self) -> None:
        if self.descriptor not in VALID_DESCRIPTORS:
            raise ValueError(f"unknown descriptor: {self.descriptor}")
        if self.target_type != "beacon":
            raise ValueError(
                f"only target_type 'beacon' is supported in nature (got {self.target_type!r}); "
                f"shaper / digital destinations are excluded"
            )
        if self.param not in BEACON_PARAMS:
            raise ValueError(f"unknown beacon param: {self.param}")
        if self.param in BEACON_BAND_PARAMS:
            if self.band is None:
                raise ValueError(f"beacon param {self.param} requires band")
            lo = 1
            hi = max_band_for_param(self.param)
            if not (lo <= int(self.band) <= hi):
                raise ValueError(
                    f"beacon band {self.band} out of range for param {self.param} "
                    f"(allowed {lo}..{hi}; engine has {N_BEACON_BANDS} bands)"
                )
        elif self.band is not None:
            raise ValueError(
                f"global beacon param {self.param} must not set band (got {self.band})"
            )

    def osc_address(self) -> str:
        """Return the OSC address this target would emit (after validation)."""
        self.validate()
        if self.param in BEACON_OSC_GLOBAL:
            return BEACON_OSC_GLOBAL[self.param]
        assert self.band is not None
        return f"/beacon/{self.param}/{int(self.band)}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "descriptor": self.descriptor,
            "target_type": "beacon",
            "param": self.param,
            "band": self.band,
            "scale": self.scale,
            "offset": self.offset,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "smooth": self.smooth,
            "threshold": self.threshold,
            "invert": self.invert,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModulationTarget":
        return cls(
            descriptor=d["descriptor"],
            param=d["param"],
            band=d.get("band"),
            scale=float(d.get("scale", 1.0)),
            offset=float(d.get("offset", 0.0)),
            min_value=float(d.get("min_value", 0.0)),
            max_value=float(d.get("max_value", 1.0)),
            smooth=float(d.get("smooth", 0.0)),
            threshold=float(d.get("threshold", 0.0)),
            invert=bool(d.get("invert", False)),
            active=bool(d.get("active", True)),
            target_type=str(d.get("target_type", "beacon")),
        )


# ---------------------------------------------------------------------------
# Modulator
# ---------------------------------------------------------------------------


class SampleModulator:
    """Apply descriptor frames to beacon OSC targets only."""

    def __init__(
        self,
        transport: Optional[OscTransport] = None,
        sc_host: str = "127.0.0.1",
        sc_port: int = 57120,
    ):
        if transport is None:
            transport = make_udp_transport(sc_host, sc_port)
        self.transport = transport
        self.targets: List[ModulationTarget] = []
        self._lock = threading.Lock()

    def add_target(self, target: ModulationTarget) -> None:
        target.validate()
        with self._lock:
            self.targets.append(target)

    def set_targets(self, targets: Sequence[ModulationTarget]) -> None:
        for t in targets:
            t.validate()
        with self._lock:
            self.targets = list(targets)

    def remove_targets(self, descriptor: Optional[str] = None) -> None:
        with self._lock:
            if descriptor is None:
                self.targets.clear()
            else:
                self.targets = [t for t in self.targets if t.descriptor != descriptor]

    def list_targets(self) -> List[ModulationTarget]:
        with self._lock:
            return list(self.targets)

    def mapping_to_dict(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.list_targets()]

    def mapping_from_dict(self, data: Sequence[Dict[str, Any]]) -> None:
        targets = [ModulationTarget.from_dict(d) for d in data]
        self.set_targets(targets)

    def on_descriptor(
        self,
        desc: Union[SampleDescriptor, Dict[str, float]],
    ) -> None:
        """Feed one analysis frame; emit OSC for every active mapping."""
        if isinstance(desc, SampleDescriptor):
            values = desc.to_dict()
        else:
            values = dict(desc)

        with self._lock:
            targets = list(self.targets)

        for t in targets:
            if not t.active or t.descriptor not in values:
                continue
            raw = float(values[t.descriptor])
            value = self._map_value(t, raw)
            self._apply_beacon(t, value)

    def _map_value(self, t: ModulationTarget, raw: float) -> float:
        normalized = _normalize_descriptor(t.descriptor, raw)
        if normalized < t.threshold:
            value = t.min_value
        else:
            if t.invert:
                normalized = 1.0 - normalized
            value = t.offset + normalized * t.scale

        value = max(t.min_value, min(t.max_value, value))

        # EWMA: smooth is alpha toward the new sample (preserved from legacy).
        if t.smooth > 0:
            alpha = max(0.0, min(1.0, t.smooth))
            t._smoothed_value = alpha * value + (1.0 - alpha) * t._smoothed_value
            value = t._smoothed_value
        return value

    def _apply_beacon(self, t: ModulationTarget, value: float) -> None:
        # Defense in depth: never emit out-of-range band addresses.
        try:
            address = t.osc_address()
        except ValueError as exc:
            log.debug("skipping invalid beacon target %s: %s", t.param, exc)
            return
        self.transport.send_message(address, [float(value)])

    # ------------------------------------------------------------------
    # Presets (beacon half only; design semantics, not clinical claims)
    # ------------------------------------------------------------------

    def preset_mapping(self, name: str) -> None:
        """Install one of the four designated beacon-only presets."""
        if name not in PRESET_NAMES:
            raise ValueError(
                f"unknown preset: {name!r}; "
                f"allowed: {', '.join(sorted(PRESET_NAMES))}"
            )
        self.set_targets(build_preset(name))
        log.info("SampleModulator preset installed: %s", name)

    def list_presets(self) -> List[str]:
        return sorted(PRESET_NAMES)


def build_preset(name: str) -> List[ModulationTarget]:
    """Return beacon-only targets for a named preset (does not mutate state).

    Mapping semantics are design choices for exploratory control routing —
    not audio-effects claims or clinical assertions. See
    ``nature/MODULATION_PRESETS.md``.
    """
    if name == "spectrum-projection":
        # Project low/mid analysis energy onto three engine gain slots.
        # Legacy used band 14 for the third slot; that index is invalid on the
        # 13-band engine, so the third target maps analysis band_2 → engine
        # band 13 (highest slot / HPF region) instead.
        return [
            ModulationTarget(
                "band_0", "gain", band=1, scale=1.5, offset=0.0, max_value=1.5, smooth=0.8
            ),
            ModulationTarget(
                "band_1", "gain", band=7, scale=1.5, offset=0.0, max_value=1.5, smooth=0.8
            ),
            ModulationTarget(
                "band_2", "gain", band=13, scale=1.5, offset=0.0, max_value=1.5, smooth=0.8
            ),
        ]

    if name == "harmonic-projection":
        # Project sample energy at n*f1 onto engine bands 1..13 only.
        # Legacy also wrote shaper voices and bands 14..32 — excluded here.
        targets = [
            ModulationTarget(
                f"harm_{i}",
                "gain",
                band=i + 1,
                scale=1.5,
                offset=0.0,
                max_value=1.5,
                smooth=0.8,
            )
            for i in range(N_BEACON_BANDS)
        ]
        targets.append(
            ModulationTarget(
                "rms", "master", scale=1.3, offset=0.2, max_value=1.5, smooth=0.8
            )
        )
        return targets

    if name == "consonance-gate":
        # Harmonic content raises master; residual energy widens base BPF (q).
        # Shaper shape/master rows from legacy are dropped.
        return [
            ModulationTarget(
                "harmonicity",
                "master",
                scale=1.0,
                offset=0.2,
                max_value=1.2,
                smooth=0.9,
            ),
            ModulationTarget(
                "residual_rms",
                "q",
                band=1,
                scale=1.5,
                offset=0.5,
                max_value=2.0,  # contract q range upper bound
                smooth=0.9,
            ),
        ]

    if name == "timbre-filter":
        # Noisiness widens base BPF; energy pushes base-band distance.
        # Legacy centroid→shaper.shape row is dropped.
        return [
            ModulationTarget(
                "flatness",
                "q",
                band=1,
                scale=1.5,
                offset=0.5,
                max_value=2.0,
                smooth=0.9,
            ),
            ModulationTarget(
                "rms",
                "dist",
                band=1,
                scale=10.0,
                offset=0.0,
                max_value=10.0,
                smooth=0.8,
            ),
        ]

    raise ValueError(f"unknown preset: {name!r}")
