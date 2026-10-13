"""Stoker (1957) wet-bed dam-break analytic solution.

Reference
---------
Stoker, J. J. (1957). *Water Waves: The Mathematical Theory with Applications*.
Interscience, New York.

Exact inviscid 1D shallow-water Riemann problem for a dam break onto a wet
bed (``hl > hr > 0``, initially at rest). The intermediate (star) state is
obtained by solving a scalar nonlinear equation; the left wave is a
rarefaction and the right wave is a shock.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def _star_residual(h_star: float, hl: float, hr: float, g: float) -> float:
    """Residual equating rarefaction and shock expressions for ``u*``."""
    c_l = np.sqrt(g * hl)
    c_star = np.sqrt(g * h_star)
    u_from_rarefaction = 2.0 * (c_l - c_star)
    u_from_shock = (h_star - hr) * np.sqrt(
        g * (h_star + hr) / (2.0 * h_star * hr)
    )
    return u_from_rarefaction - u_from_shock


def intermediate_state(
    hl: float,
    hr: float,
    g: float = 9.81,
) -> dict:
    """Solve for the constant intermediate state ``(h*, u*)``.

    Parameters
    ----------
    hl, hr :
        Left and right initial depths [m], with ``hl > hr > 0``.
    g :
        Gravity [m/s²].

    Returns
    -------
    dict
        ``{"h_star", "u_star", "shock_speed"}``.
    """
    hl = float(hl)
    hr = float(hr)
    g = float(g)
    if not (hl > hr > 0.0):
        raise ValueError("require hl > hr > 0")

    h_star = brentq(
        lambda h: _star_residual(h, hl, hr, g),
        hr * (1.0 + 1e-12),
        hl * (1.0 - 1e-12),
    )
    u_star = 2.0 * (np.sqrt(g * hl) - np.sqrt(g * h_star))
    shock_speed = u_star * h_star / (h_star - hr)
    return {
        "h_star": float(h_star),
        "u_star": float(u_star),
        "shock_speed": float(shock_speed),
    }


def depth_velocity(
    x,
    t: float,
    hl: float,
    hr: float,
    x0: float = 0.0,
    g: float = 9.81,
) -> dict:
    """Stoker wet-bed dam-break depth and velocity.

    Parameters
    ----------
    x :
        Array-like sample locations [m].
    t :
        Time since dam break [s].
    hl, hr :
        Left / right initial depths [m].
    x0, g :
        Dam location [m], gravity [m/s²].

    Returns
    -------
    dict
        ``{"h": ndarray, "u": ndarray}``.
    """
    x = np.asarray(x, dtype=float)
    t = float(t)
    if t < 0.0:
        raise ValueError("t must be non-negative")

    h = np.empty_like(x, dtype=float)
    u = np.empty_like(x, dtype=float)

    if t == 0.0:
        left = x <= x0
        h[left] = hl
        u[left] = 0.0
        h[~left] = hr
        u[~left] = 0.0
        return {"h": h, "u": u}

    star = intermediate_state(hl, hr, g=g)
    h_star = star["h_star"]
    u_star = star["u_star"]
    S = star["shock_speed"]

    c_l = np.sqrt(g * hl)
    c_star = np.sqrt(g * h_star)

    x_head = x0 - c_l * t
    x_tail = x0 + (u_star - c_star) * t
    x_shock = x0 + S * t

    left = x < x_head
    rare = (x >= x_head) & (x < x_tail)
    star_region = (x >= x_tail) & (x < x_shock)
    right = x >= x_shock

    h[left] = hl
    u[left] = 0.0

    xi = (x[rare] - x0) / t
    c = (2.0 * c_l - xi) / 3.0
    h[rare] = c**2 / g
    u[rare] = (2.0 / 3.0) * (xi + c_l)

    h[star_region] = h_star
    u[star_region] = u_star

    h[right] = hr
    u[right] = 0.0

    return {"h": h, "u": u}
