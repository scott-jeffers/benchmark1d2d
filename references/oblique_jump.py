"""Oblique hydraulic jump (Ippen) for supercritical shallow-water flow.

Reference
---------
Ippen, A. T. (1951). "Mechanics of supercritical flow." *Trans. ASCE*, 116,
268–295.

Delestre, O., et al. (2013). "SWASHES: a compilation of shallow water analytic
solutions…" *Int. J. Numer. Methods Fluids*, 72(3), 269–300.

An upstream supercritical state ``(h1, Fr1)`` is deflected by a wall angle
``θ``. The oblique jump lies at wave angle ``β`` to the upstream flow; the
conjugate depth and velocity follow the shallow-water Rankine–Hugoniot
relations. The analytic field is piecewise constant on either side of the
straight shock through the origin.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

DEFAULT_PARAMS = {
    "Fr1": 2.5,
    "theta_deg": 15.0,
    "h1": 1.0,
    "g": 9.81,
}


def _ippen_residual(beta: float, Fr1: float, theta: float) -> float:
    """Residual of the Ippen oblique-jump relation (angles in radians).

    ``tan θ = 2 cot(β) (Fr₁² sin²β − 1) / (Fr₁² (1 + cos 2β) + 2)``.
    """
    s2 = np.sin(beta) ** 2
    num = 2.0 * (1.0 / np.tan(beta)) * (Fr1**2 * s2 - 1.0)
    den = Fr1**2 * (1.0 + np.cos(2.0 * beta)) + 2.0
    return num / den - np.tan(theta)


def shock_angle(Fr1: float, theta_deg: float) -> float:
    """Wave angle ``β`` [degrees] for upstream Froude ``Fr1`` and deflection ``θ``.

    Solves the shallow-water Ippen relation on ``(θ, 90°)`` (degrees).
    """
    Fr1 = float(Fr1)
    theta = np.deg2rad(float(theta_deg))
    if Fr1 <= 1.0:
        raise ValueError("oblique jump requires Fr1 > 1")
    if theta <= 0.0 or theta >= 0.5 * np.pi:
        raise ValueError("theta_deg must be in (0, 90)")

    # β must exceed θ and admit a supercritical normal component.
    lo = theta + 1e-6
    hi = 0.5 * np.pi - 1e-6
    # Ensure a sign change; if Fr is barely supercritical the physical root
    # may sit near the lower bound.
    f_lo = _ippen_residual(lo, Fr1, theta)
    f_hi = _ippen_residual(hi, Fr1, theta)
    if f_lo * f_hi > 0.0:
        # Scan for a bracket.
        grid = np.linspace(lo, hi, 64)
        vals = [_ippen_residual(b, Fr1, theta) for b in grid]
        found = False
        for i in range(len(grid) - 1):
            if vals[i] * vals[i + 1] <= 0.0:
                lo, hi = float(grid[i]), float(grid[i + 1])
                found = True
                break
        if not found:
            raise ValueError(
                f"no Ippen root for Fr1={Fr1}, theta_deg={theta_deg}"
            )
    beta = brentq(lambda b: _ippen_residual(b, Fr1, theta), lo, hi)
    return float(np.rad2deg(beta))


def conjugate_depth_ratio(Fr1: float, beta_deg: float) -> float:
    """``h2/h1 = ½ (√(1 + 8 Fr₁² sin²β) − 1)``."""
    beta = np.deg2rad(float(beta_deg))
    Frn2 = float(Fr1) ** 2 * np.sin(beta) ** 2
    return float(0.5 * (np.sqrt(1.0 + 8.0 * Frn2) - 1.0))


def depth_velocity(
    x,
    y,
    t: float = 0.0,  # noqa: ARG001 — steady
    *,
    Fr1: float = 2.5,
    theta_deg: float = 15.0,
    h1: float = 1.0,
    g: float = 9.81,
    beta_deg: float | None = None,
) -> dict:
    """Piecewise-constant oblique jump field on a Cartesian sample.

    Upstream state occupies the half-plane below the shock line
    ``y = x tan(β)`` (flow in +x). Downstream state is uniform with depth
    ``h2`` and velocity magnitude/direction consistent with deflection ``θ``.

    Returns
    -------
    dict
        ``h``, ``u``, ``v``, ``beta_deg``, ``h2``, ``Fr1``.
    """
    del t
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if beta_deg is None:
        beta_deg = shock_angle(Fr1, theta_deg)
    beta = np.deg2rad(float(beta_deg))
    theta = np.deg2rad(float(theta_deg))
    h1 = float(h1)
    g = float(g)
    Fr1 = float(Fr1)

    ratio = conjugate_depth_ratio(Fr1, beta_deg)
    h2 = h1 * ratio
    c1 = np.sqrt(g * h1)
    u1 = Fr1 * c1
    v1 = 0.0

    # Tangential continuity: V1 cos(β) = V2 cos(β − θ); normal mass flux
    # closes the jump. Downstream flow is aligned with the deflected wall (θ).
    V1 = u1
    V2 = V1 * np.cos(beta) / np.cos(beta - theta)
    u2 = V2 * np.cos(theta)
    v2 = V2 * np.sin(theta)

    # Upstream half-plane: below the ray y = x tan(β).
    side = y * np.cos(beta) - x * np.sin(beta)
    upstream = side <= 0.0

    h = np.where(upstream, h1, h2)
    u = np.where(upstream, u1, u2)
    v = np.where(upstream, v1, v2)

    return {
        "h": h,
        "u": u,
        "v": v,
        "beta_deg": float(beta_deg),
        "theta_deg": float(theta_deg),
        "h1": h1,
        "h2": h2,
        "Fr1": Fr1,
        "u1": u1,
        "u2": float(u2),
        "v2": float(v2),
    }
