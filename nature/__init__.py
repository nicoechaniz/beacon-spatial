"""Nature sample analysis: resonant harmonic filter + sample layer.

Migrated from digital-beacon (T3.1). The nh_analysis.mask.harmonic_mask
dependency is vendorized under nature._vendor — no packages/ coupling remains.
"""

from nature.resonant_filter import ResonantFilter
from nature.sample_layer import SampleDescriptor, SampleLayer

__all__ = [
    "ResonantFilter",
    "SampleDescriptor",
    "SampleLayer",
]
