"""Steady flows over a bump and a lake at rest, from SWASHES.

References
----------
Delestre, O., Lucas, C., Ksinant, P.-A., Darboux, F., Laguerre, C., Vo, T. N. T.,
James, F., and Cordier, S. (2013). "SWASHES: a compilation of shallow water
analytic solutions for hydraulic and environmental studies." *Int. J. Numer.
Meth. Fluids*, 72(3), 269–300. https://doi.org/10.1002/fld.3741
Goutal, N., and Maurel, F. (1997). *Proceedings of the 2nd workshop on dam-break
wave simulation*. EDF report HE-43/97/016/B.

The channel is 25 m long and frictionless, with a parabolic bump
``z = 0.2 − 0.05 (x − 10)²`` on 8 < x < 12 (zero elsewhere). In steady flow
the discharge ``q`` is constant and the Bernoulli head
``H = q²/(2 g h²) + h + z`` is constant between shocks, so the depth is a
root of a cubic at every x:

* ``subcritical``  q = 4.42 m²/s, h = 2 m downstream; subcritical everywhere.
* ``transcritical`` q = 1.53 m²/s; critical at the bump crest, subcritical
  upstream and supercritical downstream (no shock).
* ``shock``  q = 0.18 m²/s, h = 0.33 m downstream; critical at the crest,
  supercritical beyond it until a hydraulic jump, whose position satisfies
  the Rankine–Hugoniot condition ``q²/h₁ + g h₁²/2 = q²/h₂ + g h₂²/2``
  (solved to 1e-12 m), then subcritical to the outlet.
* ``lake_at_rest``  still water at level 0.1 m over the same bump, whose top
  (0.2 m) stands out of the water: h = max(0.1 − z, 0), u = 0.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

G = 9.81
CASES = {
    "subcritical": dict(q=4.42, h_out=2.0),
    "transcritical": dict(q=1.53, h_out=None),
    "shock": dict(q=0.18, h_out=0.33),
}


def bed(x, L: float = 25.0):
    x = np.asarray(x, dtype=float)
    return np.where((x > 8.0) & (x < 12.0), 0.2 - 0.05 * (x - 10.0) ** 2, 0.0)


def _root(q: float, head: float, z: float, branch: str, g: float) -> float:
    """Depth with Bernoulli head ``head`` over bed ``z`` on one branch of the cubic."""
    hc = (q * q / g) ** (1.0 / 3.0)
    f = lambda h: q * q / (2 * g * h * h) + h + z - head  # noqa: E731
    if abs(f(hc)) < 1e-14:
        return hc
    if branch == "sub":
        return brentq(f, hc, head - z + 1.0, xtol=1e-14, rtol=1e-15)
    return brentq(f, 1e-9, hc, xtol=1e-14, rtol=1e-15)


def _momentum(q, h, g):
    return q * q / h + 0.5 * g * h * h


def shock_position(q: float = 0.18, h_out: float = 0.33, g: float = G) -> float:
    zm = 0.2
    hc = (q * q / g) ** (1.0 / 3.0)
    H1 = 1.5 * hc + zm
    H2 = q * q / (2 * g * h_out * h_out) + h_out

    def rh(x):
        z = float(bed(x))
        return _momentum(q, _root(q, H1, z, "super", g), g) - _momentum(q, _root(q, H2, z, "sub", g), g)

    # the subcritical branch of H2 exists only where z <= H2 - 1.5 hc
    x_lo = 10.0 + np.sqrt((0.2 - (H2 - 1.5 * hc)) / 0.05) + 1e-9
    return brentq(rh, x_lo, 12.0 - 1e-9, xtol=1e-12)


def steady_bump(x, t: float = 0.0, case: str = "subcritical", g: float = G) -> dict:
    """Depth and velocity of steady flow over the bump (``t`` is ignored)."""
    x = np.asarray(x, dtype=float)
    p = CASES[case]
    q = p["q"]
    z = bed(x)
    hc = (q * q / g) ** (1.0 / 3.0)
    h = np.empty_like(x)
    if case == "subcritical":
        H = q * q / (2 * g * p["h_out"] ** 2) + p["h_out"]
        h[:] = [_root(q, H, zi, "sub", g) for zi in z]
    elif case == "transcritical":
        H = 1.5 * hc + 0.2
        h[:] = [_root(q, H, zi, "sub" if xi <= 10.0 else "super", g) for xi, zi in zip(x, z)]
    elif case == "shock":
        xs = shock_position(q, p["h_out"], g)
        H1, H2 = 1.5 * hc + 0.2, q * q / (2 * g * p["h_out"] ** 2) + p["h_out"]
        h[:] = [_root(q, H1, zi, "sub" if xi <= 10.0 else "super", g) if xi < xs else _root(q, H2, zi, "sub", g)
                for xi, zi in zip(x, z)]
    else:
        raise ValueError(case)
    return {"h": h, "u": q / h, "Q": np.full_like(x, q), "z": z}


def lake_at_rest(x, t: float = 0.0, level: float = 0.1) -> dict:
    """Still water at ``level`` over the bump; dry where the bump stands out."""
    z = bed(x)
    h = np.maximum(level - z, 0.0)
    return {"h": h, "u": np.zeros_like(h), "Q": np.zeros_like(h), "z": z}
