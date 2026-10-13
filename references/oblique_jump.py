"""Oblique hydraulic jump at a wall deflection (supercritical shallow-water flow).

References
----------
Ippen, A. T. (1951). "Mechanics of supercritical flow." *Trans. ASCE*, 116,
268–295.
Chow, V. T. (1959). *Open-Channel Hydraulics*, §17-5. McGraw-Hill.

Geometry (wall frame): a straight slip wall along ``y = 0`` for ``x ≥ 0``.
Uniform supercritical flow ``(h1, V1 = Fr1·√(g h1))`` arrives at angle ``θ``
towards the wall. The wall turns it parallel to itself through a straight
oblique jump from the origin at angle ``β − θ`` to the wall, where ``β`` is
the jump angle measured from the upstream flow. Above the jump the flow is
upstream; between the jump and the wall it is uniform downstream.

The jump conditions are the exact shallow-water Rankine–Hugoniot relations:
normal component as a hydraulic jump with ``Fr1n = Fr1 sin β``, so
``h2/h1 = ½(√(1 + 8 Fr1n²) − 1)``; tangential velocity continuous; mass
``h1 V1 sin β = h2 V2 sin(β − θ)``. Together they give
``tan θ = tan β (√(1 + 8 Fr1² sin²β) − 3) / (2 tan²β + √(1 + 8 Fr1² sin²β) − 1)``,
solved here on the weak branch (smaller β).

Case history: before 2.0.0 the module used the gas-dynamics θ–β–M relation,
which puts the jump at 34.0° instead of 39.6° for Fr1 = 2.5, θ = 15°, and it
labelled the region between the wall and the jump as upstream.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

DEFAULT_PARAMS = {"Fr1": 2.5, "theta_deg": 15.0, "h1": 1.0, "g": 9.81}


def _deflection(beta: float, Fr1: float) -> float:
    """Wall deflection θ [rad] produced by a jump at angle β [rad]."""
    r = conjugate_depth_ratio(Fr1, np.rad2deg(beta))
    return float(beta - np.arctan(np.tan(beta) / r))


def shock_angle(Fr1: float, theta_deg: float) -> float:
    """Weak-branch jump angle β [degrees] for upstream ``Fr1`` and deflection ``θ``."""
    Fr1, theta = float(Fr1), np.deg2rad(float(theta_deg))
    if Fr1 <= 1.0:
        raise ValueError("an oblique jump needs Fr1 > 1")
    lo = np.arcsin(1.0 / Fr1) + 1e-9  # Mach angle: zero-strength wave
    grid = np.linspace(lo, 0.5 * np.pi - 1e-9, 4001)
    th = np.array([_deflection(b, Fr1) for b in grid])
    k = int(np.argmax(th))
    if theta <= 0.0 or theta > th[k]:
        raise ValueError(f"no attached jump: theta_deg must be in (0, {np.rad2deg(th[k]):.2f}] for Fr1 = {Fr1}")
    return float(np.rad2deg(brentq(lambda b: _deflection(b, Fr1) - theta, lo, grid[k])))


def conjugate_depth_ratio(Fr1: float, beta_deg: float) -> float:
    """``h2/h1 = ½ (√(1 + 8 Fr1² sin²β) − 1)``."""
    Frn = float(Fr1) * np.sin(np.deg2rad(float(beta_deg)))
    return float(0.5 * (np.sqrt(1.0 + 8.0 * Frn * Frn) - 1.0))


def states(Fr1: float = 2.5, theta_deg: float = 15.0, h1: float = 1.0, g: float = 9.81) -> dict:
    """Upstream and downstream states in the wall frame."""
    beta = np.deg2rad(shock_angle(Fr1, theta_deg))
    theta = np.deg2rad(theta_deg)
    V1 = Fr1 * np.sqrt(g * h1)
    h2 = h1 * conjugate_depth_ratio(Fr1, np.rad2deg(beta))
    V2 = V1 * np.cos(beta) / np.cos(beta - theta)
    return {
        "beta_deg": float(np.rad2deg(beta)),
        "jump_to_wall_deg": float(np.rad2deg(beta - theta)),
        "h1": float(h1), "u1": float(V1 * np.cos(theta)), "v1": float(-V1 * np.sin(theta)),
        "h2": float(h2), "u2": float(V2), "v2": 0.0,
        "Fr2": float(V2 / np.sqrt(g * h2)),
    }


def depth_velocity(x, y, t: float = 0.0, *, Fr1: float = 2.5, theta_deg: float = 15.0, h1: float = 1.0, g: float = 9.81) -> dict:
    """Exact steady field on any sample with ``y ≥ 0`` (``t`` ignored)."""
    del t
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    s = states(Fr1, theta_deg, h1, g)
    downstream = (x > 0.0) & (y < x * np.tan(np.deg2rad(s["jump_to_wall_deg"])))
    return {
        "h": np.where(downstream, s["h2"], s["h1"]),
        "u": np.where(downstream, s["u2"], s["u1"]),
        "v": np.where(downstream, s["v2"], s["v1"]),
        **{k: s[k] for k in ("beta_deg", "h2", "Fr2")},
    }
