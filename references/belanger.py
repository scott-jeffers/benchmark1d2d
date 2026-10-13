"""Bélanger sequent-depth relation for a hydraulic jump in a rectangular channel.

References
----------
Bélanger, J.-B. (1828). *Essai sur la solution numérique de quelques problèmes
relatifs au mouvement permanent des eaux courantes*. Carilian-Goeury, Paris.
Chanson, H. (2009). "Development of the Bélanger equation and backwater equation
by Jean-Baptiste Bélanger (1828)." *J. Hydraul. Eng.*, 135(3), 159–163.
https://doi.org/10.1061/(ASCE)0733-9429(2009)135:3(159)

Momentum conservation across a stationary jump on a horizontal, frictionless
bed gives ``h2 / h1 = (sqrt(1 + 8 Fr1²) - 1) / 2``. On such a bed the jump
position is neutral (any position satisfies the equations), so scoring compares
the supercritical and subcritical plateau depths and the unit discharge, not the
jump location: ``depth_velocity`` takes an assumed ``x_jump`` only so that a
full profile can be drawn.
"""

from __future__ import annotations

import numpy as np


def sequent_depth_ratio(Fr1: float) -> float:
    if Fr1 <= 1.0:
        raise ValueError("a hydraulic jump needs supercritical inflow (Fr1 > 1)")
    return float(0.5 * (np.sqrt(1.0 + 8.0 * Fr1**2) - 1.0))


def sequent_depths(x, t: float = 0.0, Fr1: float = 2.5, h1: float = 0.2, g: float = 9.81, x_jump: float | None = None, L: float = 100.0) -> dict:
    """Conjugate states and an illustrative step profile (steady; ``t`` ignored)."""
    x = np.asarray(x, dtype=float)
    u1 = Fr1 * np.sqrt(g * h1)
    q = u1 * h1
    h2 = h1 * sequent_depth_ratio(Fr1)
    xj = L / 2.0 if x_jump is None else float(x_jump)
    h = np.where(x < xj, h1, h2)
    head_loss = (h2 - h1) ** 3 / (4.0 * h1 * h2)
    return {
        "h": h,
        "u": q / h,
        "Q": np.full_like(x, q),
        "h1": float(h1),
        "h2": float(h2),
        "q": float(q),
        "Fr2": float((q / h2) / np.sqrt(g * h2)),
        "energy_loss": float(head_loss),
    }
