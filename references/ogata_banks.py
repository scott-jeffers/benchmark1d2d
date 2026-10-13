"""Ogata–Banks (1961) advection–dispersion solution for a continuous source.

Reference
---------
Ogata, A., and Banks, R. B. (1961). *A Solution of the Differential Equation of
Longitudinal Dispersion in Porous Media*. Professional Paper 411-A,
U.S. Geological Survey. https://doi.org/10.3133/pp411A

Semi-infinite domain ``x ≥ 0``, constant velocity ``u`` and dispersion ``D``,
initially clean, concentration held at ``c0`` at ``x = 0`` from ``t = 0``:

    c(x,t) = c0/2 [ erfc((x - u t) / (2 sqrt(D t)))
                   + exp(u x / D) erfc((x + u t) / (2 sqrt(D t))) ]

The second term is evaluated with ``scipy.special.erfcx`` to avoid overflow of
``exp(u x / D)`` at high Péclet number.
"""

from __future__ import annotations

import numpy as np
from scipy.special import erfc, erfcx


def concentration(x, t: float, u: float = 0.1, D: float = 0.01, c0: float = 1.0) -> dict:
    x = np.asarray(x, dtype=float)
    t = float(t)
    if t < 0:
        raise ValueError("t must be non-negative")
    if t == 0.0:
        c = np.where(x <= 0.0, c0, 0.0)
        return {"c": c.astype(float), "u": np.full_like(x, u)}
    s = 2.0 * np.sqrt(D * t)
    a = (x - u * t) / s
    b = (x + u * t) / s
    # exp(u x / D) * erfc(b) = exp(u x / D - b^2) * erfcx(b)
    second = np.exp(u * x / D - b**2) * erfcx(b)
    c = 0.5 * c0 * (erfc(a) + second)
    return {"c": np.clip(c, 0.0, c0), "u": np.full_like(x, u)}
