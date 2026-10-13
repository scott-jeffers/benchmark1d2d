"""Ritter (1892) dry-bed dam-break analytic solution.

Reference
---------
Ritter, A. (1892). "Die Fortpflanzung der Wasserwellen."
*Zeitschrift des Vereines Deutscher Ingenieure*, 36(33), 947–954.

Exact inviscid 1D shallow-water solution for an instantaneous dam break onto
a dry bed with still water of depth ``h0`` to the left of ``x0``.
"""

from __future__ import annotations

import numpy as np


def front_position(t: float, h0: float = 1.0, x0: float = 1000.0, g: float = 9.81) -> float:
    """Return the wet/dry front location at time ``t``.

    Parameters
    ----------
    t, h0, x0, g :
        Time [s], upstream depth [m], dam abscissa [m], gravity [m/s²].

    Returns
    -------
    float
        Front position ``x0 + 2 t sqrt(g h0)`` [m].
    """
    t = float(t)
    if t < 0.0:
        raise ValueError("t must be non-negative")
    return float(x0 + 2.0 * t * np.sqrt(g * h0))


def depth_velocity(
    x,
    t: float,
    h0: float = 1.0,
    x0: float = 1000.0,
    g: float = 9.81,
) -> dict:
    """Ritter dry-bed dam-break depth and velocity.

    Regions at time ``t > 0`` with ``c0 = sqrt(g h0)``:

    * ``x < x0 - t c0``: undisturbed left state ``h = h0``, ``u = 0``
    * rarefaction: ``h = (1/(9 g)) (2 c0 - (x-x0)/t)^2``,
      ``u = (2/3) ((x-x0)/t + c0)``
    * ``x > x0 + 2 t c0``: dry ``h = 0``, ``u = 0``

    Parameters
    ----------
    x :
        Array-like sample locations [m].
    t :
        Time since dam break [s].
    h0, x0, g :
        Upstream depth [m], dam location [m], gravity [m/s²].

    Returns
    -------
    dict
        ``{"h": ndarray, "u": ndarray}`` with the same shape as ``x``.
    """
    x = np.asarray(x, dtype=float)
    t = float(t)
    if t < 0.0:
        raise ValueError("t must be non-negative")

    c0 = np.sqrt(g * h0)
    h = np.empty_like(x, dtype=float)
    u = np.empty_like(x, dtype=float)

    if t == 0.0:
        left = x <= x0
        h[left] = h0
        u[left] = 0.0
        h[~left] = 0.0
        u[~left] = 0.0
        return {"h": h, "u": u}

    x_tail = x0 - t * c0
    x_front = x0 + 2.0 * t * c0

    left = x < x_tail
    dry = x > x_front
    rare = ~(left | dry)

    h[left] = h0
    u[left] = 0.0
    h[dry] = 0.0
    u[dry] = 0.0

    xi = (x[rare] - x0) / t
    h[rare] = (1.0 / (9.0 * g)) * (2.0 * c0 - xi) ** 2
    u[rare] = (2.0 / 3.0) * (xi + c0)

    return {"h": h, "u": u}
