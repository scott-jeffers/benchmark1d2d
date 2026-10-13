"""Scoring metrics for Track A (verification/validation) and Track B (parity)."""

from hydrobench.metrics.hydro import (
    arrival_time_error,
    csi,
    front_position_error,
    global_mass_error,
    kge,
    nse,
    peak_error,
)
from hydrobench.metrics.norms import L1, L2, Linf
from hydrobench.metrics.parity import (
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
