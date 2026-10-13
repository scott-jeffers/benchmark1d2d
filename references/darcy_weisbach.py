"""Darcy–Weisbach head loss in a single pipe (steady, pressurized).

References
----------
Colebrook, C. F. (1939). "Turbulent flow in pipes, with particular reference to
the transition region between the smooth and rough pipe laws." *J. Inst. Civ.
Eng.*, 11(4), 133–156. https://doi.org/10.1680/ijoti.1939.13150

Rossman, L. A., et al. (2020). *EPANET 2.2 User Manual*. EPA/600/R-20/133, §3.

For steady flow between an upstream reservoir (head ``H0`` at ``x = 0``) and a
pipe of length ``L`` and diameter ``D``, piezometric head falls linearly:
``H(x) = H0 - f (x / D) V² / (2 g)``. With a fixed friction factor ``f`` the
solution is exact; with ``f=None`` it is found from Colebrook–White (solved to
machine precision), the closure EPANET uses for its D-W option.
"""

from __future__ import annotations

import numpy as np


def colebrook_white(Re: float, rel_roughness: float, tol: float = 1e-14) -> float:
    """Darcy friction factor from Colebrook–White by fixed-point iteration."""
    if Re <= 0:
        raise ValueError("Re must be positive")
    if Re < 2000.0:
        return 64.0 / Re
    inv = -2.0 * np.log10(rel_roughness / 3.7 + 2.51 / (Re * 0.02 ** 0.5))
    for _ in range(100):
        new = -2.0 * np.log10(rel_roughness / 3.7 + 2.51 * inv / Re)
        if abs(new - inv) < tol:
            inv = new
            break
        inv = new
    return float(1.0 / inv**2)


def head_loss(
    x,
    t: float = 0.0,
    L: float = 1000.0,
    D: float = 0.3,
    V: float = 1.0,
    f: float | None = 0.02,
    H0: float = 100.0,
    roughness: float = 0.0,
    nu: float = 1.0e-6,
    g: float = 9.81,
) -> dict:
    """Steady head and pressure along the pipe; ``t`` is ignored (steady)."""
    x = np.asarray(x, dtype=float)
    if f is None:
        f = colebrook_white(V * D / nu, roughness / D)
    slope = f / D * V**2 / (2.0 * g)
    H = H0 - slope * x
    rho = 1000.0
    return {
        "H": H,
        "h": H,  # results contract: piezometric head in h for pressurized networks
        "p": rho * g * H,  # pressure head referenced to a horizontal pipe at z = 0
        "u": np.full_like(x, V),
        "Q": np.full_like(x, V * np.pi * D**2 / 4.0),
        "head_loss_total": float(slope * L),
        "friction_factor": float(f),
    }
