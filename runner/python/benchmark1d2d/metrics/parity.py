"""Track B industry-parity metrics (relative peak, volume, timing, continuity)."""

from __future__ import annotations

import numpy as np


def relative_peak(sim, ref) -> float:
    """Relative peak difference: ``(max(sim) - max(ref)) / max(ref)``."""
    sim = np.asarray(sim, dtype=float)
    ref = np.asarray(ref, dtype=float)
    ref_max = float(np.max(ref))
    if ref_max == 0.0:
        raise ValueError("ref peak must be non-zero")
    return float((float(np.max(sim)) - ref_max) / ref_max)


def relative_volume(sim, ref) -> float:
    """Relative volume difference: ``(sum(sim) - sum(ref)) / sum(ref)``.

    For uniformly spaced series this is proportional to the integrated
    volume error; callers may pass already-integrated totals as length-1
    arrays or scalars.
    """
    sim = np.asarray(sim, dtype=float)
    ref = np.asarray(ref, dtype=float)
    ref_vol = float(np.sum(ref))
    if ref_vol == 0.0:
        raise ValueError("ref volume must be non-zero")
    return float((float(np.sum(sim)) - ref_vol) / ref_vol)


def timing_error(t_sim_peak: float, t_ref_peak: float) -> float:
    """Peak-timing error: ``t_sim_peak - t_ref_peak``."""
    return float(t_sim_peak) - float(t_ref_peak)


def continuity_error(continuity_pct: float) -> float:
    """Absolute continuity error (pass-through of engine % imbalance)."""
    return float(abs(continuity_pct))
