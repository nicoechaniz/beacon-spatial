"""Minimal seam: SampleLayer descriptors → SampleModulator + optional nature player OSC.

No Flask, no daemon, no Shaper. Intended for scripts and tests that want to
wire analysis to beacon modulation and optionally drive T3.2 nature routes
(``/beacon/nature/load|gain|stop``) through the same injectable transport.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from nature.sample_layer import SampleDescriptor, SampleLayer
from nature.sample_modulator import (
    ModulationTarget,
    OscTransport,
    PRESET_NAMES,
    SampleModulator,
    make_udp_transport,
)

log = logging.getLogger(__name__)


class SampleModulationManager:
    """Optional convenience wrapper around layer + modulator + nature player OSC."""

    def __init__(
        self,
        transport: Optional[OscTransport] = None,
        sc_host: str = "127.0.0.1",
        sc_port: int = 57120,
    ):
        if transport is None:
            transport = make_udp_transport(sc_host, sc_port)
        self.transport = transport
        self.modulator = SampleModulator(transport=transport)
        self.layer: Optional[SampleLayer] = None
        self.current_path: Optional[str] = None
        self._nature_gain: float = 1.0

    # ------------------------------------------------------------------
    # Analysis layer
    # ------------------------------------------------------------------

    def attach_layer(self, layer: SampleLayer) -> None:
        """Connect ``layer.on_descriptor`` to the modulator."""
        self.layer = layer
        layer.on_descriptor = self.modulator.on_descriptor

    def load_analysis(
        self,
        path: str,
        *,
        sr: int = 48000,
        chunk_s: float = 0.05,
        f0_beacon_hz: float = 40.4,
        start: bool = True,
    ) -> SampleLayer:
        """Load a sample into SampleLayer and wire descriptors to the modulator.

        Does not start SuperCollider nature playback; call ``nature_load`` for
        that. Stops any previous analysis layer first.
        """
        self.stop_analysis()
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"sample not found: {resolved}")
        layer = SampleLayer(
            str(resolved),
            sr=sr,
            chunk_s=chunk_s,
            f0_beacon_hz=f0_beacon_hz,
            on_descriptor=self.modulator.on_descriptor,
        )
        self.layer = layer
        self.current_path = str(resolved)
        if start:
            layer.start()
        log.info("SampleModulationManager analysis loaded: %s", self.current_path)
        return layer

    def stop_analysis(self) -> None:
        if self.layer is not None:
            self.layer.stop()
            self.layer = None
        self.current_path = None

    def feed_descriptor(self, desc: SampleDescriptor | Dict[str, float]) -> None:
        """Push one descriptor frame without a running SampleLayer (tests/scripts)."""
        self.modulator.on_descriptor(desc)

    def last_descriptor(self) -> Optional[Dict[str, float]]:
        if self.layer is None:
            return None
        d = self.layer.last_descriptor()
        return d.to_dict() if d else None

    # ------------------------------------------------------------------
    # Mapping / presets
    # ------------------------------------------------------------------

    def set_mapping(self, targets: Sequence[Dict[str, Any] | ModulationTarget]) -> None:
        resolved: List[ModulationTarget] = []
        for t in targets:
            if isinstance(t, ModulationTarget):
                resolved.append(t)
            else:
                resolved.append(ModulationTarget.from_dict(t))
        self.modulator.set_targets(resolved)

    def apply_preset(self, name: str) -> None:
        self.modulator.preset_mapping(name)

    def clear_mapping(self) -> None:
        self.modulator.set_targets([])

    def list_targets(self) -> List[Dict[str, Any]]:
        return self.modulator.mapping_to_dict()

    def list_presets(self) -> List[str]:
        return sorted(PRESET_NAMES)

    # ------------------------------------------------------------------
    # T3.2 nature player routes (same transport; no long-lived daemon)
    # ------------------------------------------------------------------

    def nature_load(self, path: str) -> None:
        """Send ``/beacon/nature/load`` with an absolute path string."""
        resolved = str(Path(path).expanduser().resolve())
        self.transport.send_message("/beacon/nature/load", [resolved])

    def nature_gain(self, gain: float) -> None:
        g = max(0.0, min(1.0, float(gain)))
        self._nature_gain = g
        self.transport.send_message("/beacon/nature/gain", [g])

    def nature_stop(self) -> None:
        self.transport.send_message("/beacon/nature/stop", [])

    def get_nature_gain(self) -> float:
        return self._nature_gain

    def stop(self) -> None:
        """Stop analysis and request nature player stop (OSC)."""
        self.stop_analysis()
        self.nature_stop()
        self.clear_mapping()
        log.info("SampleModulationManager stopped")
