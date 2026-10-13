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


def angular_frequency(h0: float, L: float, g: float = 9.81) -> float:
    """Natural frequency ``ω = sqrt(8 g h0) / L`` [rad/s]."""
    return float(np.sqrt(8.0 * g * h0) / L)


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
    """Thacker planar free-surface oscillation in a parabolic bowl.

    Free surface (planar)::

        zs(x, y, t) = (η / L) x cos(ω t)

    Depth::

        h = max(0, zs - zb),  zb = h0 ((x² + y²)/L² - 1)

    Spatially uniform velocity (exact nonlinear solution)::

        u(t) = -(g η / (ω L)) sin(ω t),  v = 0

    with ``ω = sqrt(8 g h0)/L`` when ``omega`` is omitted.

    Parameters
    ----------
    x, y :
        Array-like horizontal coordinates [m] (broadcastable).
    t :
        Time [s].
    h0, L, eta :
        Still-water centre depth [m], still shoreline radius [m],
        free-surface amplitude parameter [m].
    omega :
        Angular frequency [rad/s]; default ``sqrt(8 g h0)/L``.
    g :
        Gravity [m/s²].

    Returns
    -------
    dict
        ``{"h", "u", "v", "zb", "omega"}`` arrays (``omega`` is float).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    t = float(t)

    if omega is None:
        omega = angular_frequency(h0, L, g=g)
    else:
        omega = float(omega)

    zb = bed_elevation(x, y, h0=h0, L=L)
    zs = (eta / L) * x * np.cos(omega * t)
    h = np.maximum(0.0, zs - zb)

    # du/dt = -g ∂zs/∂x = -g (η/L) cos(ω t)  =>  u = -(g η/(ω L)) sin(ω t)
    u_scalar = -(g * eta / (omega * L)) * np.sin(omega * t)
    u = np.full_like(h, u_scalar, dtype=float)
    # Dry cells: set velocity to zero for convenience.
    dry = h <= 0.0
    u = np.where(dry, 0.0, u)
    v = np.zeros_like(h)

    return {"h": h, "u": u, "v": v, "zb": zb, "omega": omega}
