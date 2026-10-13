"""Thacker (1981) parabolic-bowl planar free-surface oscillation.

Reference
---------
Thacker, W. C. (1981). "Some exact solutions to the nonlinear shallow-water
wave equations." *J. Fluid Mech.*, 107, 499–508.
https://doi.org/10.1017/S0022112081001882

Exact nonlinear 2D shallow-water solution in a circular parabolic basin with
an oscillating planar free surface.
"""

from __future__ import annotations

import numpy as np

# Default A2A-001 parameters (nondimensional bowl, mild amplitude).
DEFAULT_PARAMS = {
    "h0": 0.1,
    "L": 1.0,
    "eta": 0.05,
    "g": 9.81,
}


def angular_frequency(h0: float, L: float, g: float = 9.81) -> float:
    """Natural frequency ``ω = sqrt(2 g h0) / L`` [rad/s] (Thacker 1981; SWASHES §4.2.2)."""
    return float(np.sqrt(2.0 * g * h0) / L)


def bed_elevation(x, y, h0: float, L: float) -> np.ndarray:
    """Parabolic bed ``zb = h0 ((x² + y²)/L² - 1)``.

    Still-water depth at the origin is ``h0``; the still shoreline is the
    circle ``x² + y² = L²``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return h0 * ((x**2 + y**2) / L**2 - 1.0)


def depth_velocity(
    x,
    y,
    t: float,
    h0: float,
    L: float,
    eta: float,
    omega: float | None = None,
    g: float = 9.81,
) -> dict:
    """Thacker (1981) planar free-surface oscillation in a parabolic bowl.

    Bed ``zb = h0 ((x² + y²)/L² - 1)``. The free surface stays planar and
    tilts back and forth along x; velocity is uniform over the wet region::

        zs(x, t) = (η h0 / L²) (2 x cos ωt - η cos² ωt)
        u(t)     = -η ω sin ωt,   v = 0
        h        = max(0, zs - zb),   ω = sqrt(2 g h0) / L

    ``η`` is the horizontal excursion of the shoreline [m]. The cos² term is
    required by continuity: without it ∂h/∂t + ∂(hu)/∂x ≠ 0. (Versions of this
    module before case v2.0.0 omitted it and used ω = sqrt(8 g h0)/L, which
    satisfied momentum but not mass conservation.)

    Derivation: with u uniform, continuity gives ∂h/∂t + u ∂h/∂x = 0 and
    momentum gives du/dt = -g ∂zs/∂x. Writing zs = S(t) x + Z(t) yields
    S'' = -(2 g h0 / L²) S, so S = S0 cos ωt with S0 = 2 η h0 / L², and
    Z' = -u S, so Z = -(η² h0 / L²) cos² ωt.

    Returns ``{"h", "u", "v", "zb", "omega"}``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    t = float(t)

    if omega is None:
        omega = angular_frequency(h0, L, g=g)
    else:
        omega = float(omega)

    zb = bed_elevation(x, y, h0=h0, L=L)
    c = np.cos(omega * t)
    zs = (eta * h0 / L**2) * (2.0 * x * c - eta * c**2)
    h = np.maximum(0.0, zs - zb)
    u_scalar = -eta * omega * np.sin(omega * t)
    u = np.where(h <= 0.0, 0.0, np.full_like(h, u_scalar, dtype=float))
    v = np.zeros_like(h)

    return {"h": h, "u": u, "v": v, "zb": zb, "omega": omega}


# Catalog / draft alias used in A2A-001 manifests and READMEs.
planar_oscillation = depth_velocity
