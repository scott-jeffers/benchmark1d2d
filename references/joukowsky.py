"""Joukowsky (1900) instant valve-closure water-hammer solution.

Reference
---------
Joukowsky, N. (1900). "Über den hydraulischen Stoss in Wasserleitungsröhren."
*Mémoires de l'Académie Impériale des Sciences de St.-Pétersbourg*, Series 8,
9(5). English translation: Simin, O. (1904). "Water hammer."
*Proc. Am. Water Works Assoc.*, 24, 341–424.

For an instantaneous full closure in a frictionless pipe the pressure rise is
``Δp = ρ a V0`` (classic Joukowsky). Before the first reflection the closed-end
state propagates upstream as a sharp wave front at celerity ``a``.
"""

from __future__ import annotations

import numpy as np


def delta_p(a: float, V0: float, rho: float = 1000.0) -> float:
    """Joukowsky pressure rise for instantaneous valve closure.

    Parameters
    ----------
    a :
        Acoustic wave speed in the pipe [m/s].
    V0 :
        Steady pre-closure velocity toward the valve [m/s].
    rho :
        Fluid density [kg/m³].

    Returns
    -------
    float
        Pressure rise ``ρ a V0`` [Pa].
    """
    return float(rho * a * V0)


def pressure_wave(
    x,
    t: float,
    L: float,
    a: float,
    V0: float,
    rho: float = 1000.0,
    p0: float = 0.0,
) -> dict:
    """Frictionless pipe response before the first upstream reflection.

    Geometry: reservoir / open boundary at ``x = 0``, valve at ``x = L``.
    Valve closes instantaneously at ``t = 0``. Valid for ``0 ≤ t ≤ L/a``.

    Behind the front (``x > L - a t``): ``p = p0 + ρ a V0``, ``u = 0``.
    Ahead of the front (``x < L - a t``): ``p = p0``, ``u = V0``.

    Parameters
    ----------
    x :
        Array-like locations along the pipe [m], in ``[0, L]``.
    t :
        Time since closure [s].
    L, a, V0, rho, p0 :
        Pipe length [m], wave speed [m/s], initial velocity [m/s],
        density [kg/m³], background pressure [Pa].

    Returns
    -------
    dict
        ``{"p": ndarray, "u": ndarray, "delta_p": float}``.
    """
    x = np.asarray(x, dtype=float)
    t = float(t)
    if t < 0.0:
        raise ValueError("t must be non-negative")
    if t > L / a + 1e-15:
        raise ValueError("t exceeds first reflection time L/a; formula invalid")

    dp = delta_p(a, V0, rho=rho)
    p = np.full_like(x, p0, dtype=float)
    u = np.full_like(x, V0, dtype=float)

    if t == 0.0:
        # Only the valve face has closed; interior still undisturbed.
        at_valve = np.isclose(x, L)
        p[at_valve] = p0 + dp
        u[at_valve] = 0.0
        return {"p": p, "u": u, "delta_p": dp}

    front = L - a * t
    behind = x >= front
    p[behind] = p0 + dp
    u[behind] = 0.0

    return {"p": p, "u": u, "delta_p": dp}
