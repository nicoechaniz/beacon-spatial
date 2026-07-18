"""Nature sample analysis: resonant harmonic filter + sample layer + beacon modulation.

Migrated from digital-beacon (T3.1–T3.3). The nh_analysis.mask.harmonic_mask
dependency is vendorized under nature._vendor — no packages/ coupling remains.
Beacon-only descriptor modulation lives in sample_modulator (no Shaper path).
"""

from nature.resonant_filter import ResonantFilter
from nature.sample_layer import SampleDescriptor, SampleLayer
from nature.sample_modulation_manager import SampleModulationManager
from nature.sample_modulator import (
    BEACON_PARAMS,
    EXCLUDED_LEGACY_TARGETS,
    N_BEACON_BANDS,
    PRESET_NAMES,
    ModulationTarget,
    RecordingOscTransport,
    SampleModulator,
    build_preset,
)

__all__ = [
    "ResonantFilter",
    "SampleDescriptor",
    "SampleLayer",
    "SampleModulator",
    "SampleModulationManager",
    "ModulationTarget",
    "RecordingOscTransport",
    "build_preset",
    "BEACON_PARAMS",
    "EXCLUDED_LEGACY_TARGETS",
    "N_BEACON_BANDS",
    "PRESET_NAMES",
]
