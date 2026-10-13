"""MacDonald-type steady channel flow, posed on a 2D grid.

Reference
---------
MacDonald, I., Baines, M. J., Nichols, N. K., and Samuels, P. G. (1997).
"Analytic benchmark solutions for open-channel flows."
*J. Hydraul. Eng.*, 123(11), 1041–1045.
https://doi.org/10.1061/(ASCE)0733-9429(1997)123:11(1041)

MacDonald's method: prescribe a smooth depth ``h(x)`` and a discharge, then
build the bed so the steady equations hold exactly. Here the 1D M1 profile of
:mod:`references.macdonald` (A1F-001) is placed in a 2D rectangular channel
with slip walls, unit discharge ``q`` and Manning friction. The flow is uniform
across the channel, so the exact 2D solution is ``h = h(x)``, ``u = q/h``,
``v = 0`` over the bed ``zb(x)`` with ``dzb/dx = -(1 - Fr²) dh/dx - n² q²/h^{10/3}``.

A 2D solver must balance pressure, bed slope and friction on its own grid
to reproduce it; nothing is imposed except the inflow discharge and the
outlet depth.

Case history: before 2.0.0 this module held the free surface flat while water
flowed without friction, which is not a solution of the shallow-water
equations; any solver that merely copied the field passed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from references.macdonald import M1_PARAMS, _dh_dx_m1, depth_profile as _h_m1

DEFAULT_PARAMS = {"L": 1000.0, "W": 100.0, "q": M1_PARAMS["Q"] / M1_PARAMS["B"], "n_manning": M1_PARAMS["n_manning"], "g": 9.81}


def depth_profile(x, y=None, *, g: float = 9.81, **_: object) -> np.ndarray:
    """Exact depth ``h(x)`` [m] (independent of ``y``)."""
    return _h_m1(np.asarray(x, dtype=float), g=g)


@lru_cache(maxsize=8)
def _bed_table(L: float, q: float, n_manning: float, g: float) -> tuple[np.ndarray, np.ndarray]:
    xs = np.linspace(-0.1 * L, 1.1 * L, 120_001)
    h = _h_m1(xs, g=g)
    dzdx = -(1.0 - q * q / (g * h**3)) * _dh_dx_m1(xs, g=g) - n_manning**2 * q * q / h ** (10.0 / 3.0)
    z = np.concatenate(([0.0], np.cumsum(0.5 * (dzdx[1:] + dzdx[:-1]) * np.diff(xs))))
    return xs, z - np.interp(L, xs, z)  # anchor zb(L) = 0


def bed_elevation(x, y=None, *, L: float = 1000.0, q: float = 0.2, n_manning: float = 0.03, g: float = 9.81, **_: object) -> np.ndarray:
    """Bed ``zb(x)`` [m] that makes ``h(x)`` an exact steady solution; ``zb(L) = 0``."""
    xs, z = _bed_table(float(L), float(q), float(n_manning), float(g))
    return np.interp(np.asarray(x, dtype=float), xs, z)


def depth_velocity(x, y, t: float = 0.0, *, L: float = 1000.0, W: float = 100.0, q: float = 0.2,
                   n_manning: float = 0.03, g: float = 9.81) -> dict:
    """Exact steady fields on any sample of the channel (``t`` ignored)."""
    del t, W
    x = np.asarray(x, dtype=float)
    h = depth_profile(x, g=g)
    zb = bed_elevation(x, L=L, q=q, n_manning=n_manning, g=g)
    return {"h": h, "u": q / h, "v": np.zeros_like(h), "zb": zb, "zs": zb + h}


depth_2d = depth_velocity
