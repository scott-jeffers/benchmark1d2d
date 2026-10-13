"""MacDonald-style 2D manufactured steady free surface over a known bed.

Reference
---------
MacDonald, I., Baines, M. J., Nichols, N. K., and Samuels, P. G. (1997).
"Analytic benchmark solutions for open-channel flows."
*J. Hydraul. Eng.*, 123(11), 1041–1045.
https://doi.org/10.1061/(ASCE)0733-9429(1997)123:11(1041)

This module provides a **simple 2D manufactured** steady state for Phase 5 MVP
verification (not a literal reprint of a published 2D MacDonald table):

* Prescribed positive depth ``h(x, y)`` with a streamwise Gaussian bump and a
  mild spanwise cosine modulation.
* Constant unit discharges ``(qx, qy)`` with ``u = qx/h``, ``v = qy/h``.
* Analytic bed ``zb(x, y)`` chosen so that a constant free-surface elevation
  ``zs = zb + h`` is consistent with the prescribed depth (still-water style
  topography under the manufactured free surface). Friction is omitted; the
  field is an exact analytic target for depth/velocity L1 scoring.

Solvers that only reproduce the prescribed fields (analytic writers) pass
gating; full SW residual satisfaction with friction is left to later phases.
"""

from __future__ import annotations

import numpy as np

DEFAULT_PARAMS = {
    "L": 1000.0,  # streamwise length [m]
    "W": 100.0,  # spanwise width [m]
    "amp": 0.25,  # relative streamwise bump amplitude [-]
    "k": 16.0,  # Gaussian sharpness [-]
    "span_amp": 0.05,  # spanwise modulation amplitude [-]
    "qx": 0.2,  # unit discharge x [m²/s]
    "qy": 0.0,  # unit discharge y [m²/s]
    "g": 9.81,
}


def _h_ref(g: float) -> float:
    return (4.0 / float(g)) ** (1.0 / 3.0)


def depth_profile(
    x,
    y,
    *,
    L: float = 1000.0,
    W: float = 100.0,
    amp: float = 0.25,
    k: float = 16.0,
    span_amp: float = 0.05,
    g: float = 9.81,
) -> np.ndarray:
    """Manufactured steady depth ``h(x, y)`` [m]."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    href = _h_ref(g)
    stream = 1.0 + amp * np.exp(-k * ((x / L) - 0.5) ** 2)
    span = 1.0 + span_amp * np.cos(2.0 * np.pi * y / W)
    return href * stream * span


def bed_elevation(
    x,
    y,
    *,
    L: float = 1000.0,
    W: float = 100.0,
    amp: float = 0.25,
    k: float = 16.0,
    span_amp: float = 0.05,
    g: float = 9.81,
    zs0: float | None = None,
) -> np.ndarray:
    """Bed ``zb = zs0 - h`` with constant free-surface datum ``zs0``.

    Default ``zs0`` is chosen so that ``zb`` is negative under the deepest
    water (``zs0 = max(h)`` on a dense sample is not required; we use
    ``zs0 = 2 * href`` which keeps ``zb < 0`` for default amplitudes).
    """
    h = depth_profile(
        x, y, L=L, W=W, amp=amp, k=k, span_amp=span_amp, g=g
    )
    if zs0 is None:
        zs0 = 2.0 * _h_ref(g)
    return float(zs0) - h


def depth_velocity(
    x,
    y,
    t: float = 0.0,  # noqa: ARG001 — steady; kept for scorer (x,y,t) API
    *,
    L: float = 1000.0,
    W: float = 100.0,
    amp: float = 0.25,
    k: float = 16.0,
    span_amp: float = 0.05,
    qx: float = 0.2,
    qy: float = 0.0,
    g: float = 9.81,
    zs0: float | None = None,
) -> dict:
    """Steady manufactured 2D depth and velocity fields.

    Returns
    -------
    dict
        ``h``, ``u``, ``v``, ``zb``, ``zs``.
    """
    del t  # steady
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    h = depth_profile(
        x, y, L=L, W=W, amp=amp, k=k, span_amp=span_amp, g=g
    )
    zb = bed_elevation(
        x, y, L=L, W=W, amp=amp, k=k, span_amp=span_amp, g=g, zs0=zs0
    )
    zs = zb + h
    u = float(qx) / h
    if abs(float(qy)) < 1e-15:
        v = np.zeros_like(h)
    else:
        v = float(qy) / h
    return {"h": h, "u": u, "v": v, "zb": zb, "zs": zs}


# Alias matching draft manifest wording.
depth_2d = depth_velocity
