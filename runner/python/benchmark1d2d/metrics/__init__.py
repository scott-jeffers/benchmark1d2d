"""Scoring metrics for Track A (verification/validation) and Track B (parity)."""

from benchmark1d2d.metrics.hydro import (
    arrival_time_error,
    csi,
    front_position_error,
    global_mass_error,
    kge,
    nse,
    peak_error,
)
from benchmark1d2d.metrics.norms import L1, L2, Linf
from benchmark1d2d.metrics.parity import (
    continuity_error,
    relative_peak,
    relative_volume,
    timing_error,
)

__all__ = [
    "L1",
    "L2",
    "Linf",
    "global_mass_error",
    "nse",
    "kge",
    "peak_error",
    "arrival_time_error",
    "front_position_error",
    "csi",
    "relative_peak",
    "relative_volume",
    "timing_error",
    "continuity_error",
]
