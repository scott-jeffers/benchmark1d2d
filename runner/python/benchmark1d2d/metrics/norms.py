"""Discrete L1 / L2 / L∞ error norms for field comparisons.

All norms are *domain-normalised*: on a uniform grid they approximate

    L1 = (1/|Ω|) ∫ |e| dΩ,   L2 = sqrt((1/|Ω|) ∫ e² dΩ),   L∞ = max |e|

so they carry the units of the field and do not depend on how many cells
there are. That is what makes the observed order of accuracy meaningful:
for a scheme of order p, L1 ∝ dx^p.

Earlier versions multiplied the *mean* by the cell size, which added an extra
power of dx and inflated every observed order by exactly 1 (L1) or 0.5 (L2).
The ``dx`` argument is accepted for backwards compatibility and ignored.
"""

from __future__ import annotations

import numpy as np


def _err(sim, ref) -> np.ndarray:
    err = np.asarray(sim, dtype=float) - np.asarray(ref, dtype=float)
    err = err[np.isfinite(err)]
    if err.size == 0:
        raise ValueError("no finite points to compare")
    return err


def L1(sim, ref, dx: float | None = None) -> float:
    """Domain-normalised L1 error ``mean(|sim - ref|)`` (``dx`` ignored)."""
    return float(np.mean(np.abs(_err(sim, ref))))


def L2(sim, ref, dx: float | None = None) -> float:
    """Domain-normalised L2 error ``sqrt(mean((sim - ref)^2))`` (``dx`` ignored)."""
    return float(np.sqrt(np.mean(_err(sim, ref) ** 2)))


def Linf(sim, ref) -> float:
    """L∞ error ``max(|sim - ref|)``."""
    return float(np.max(np.abs(_err(sim, ref))))
