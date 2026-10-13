"""MacDonald et al. (1997) analytic bed construction for steady 1D flow.

Reference
---------
MacDonald, I., Baines, M. J., Nichols, N. K., and Samuels, P. G. (1997).
"Analytic benchmark solutions for open-channel flows."
*J. Hydraul. Eng.*, 123(11), 1041–1045.
https://doi.org/10.1061/(ASCE)0733-9429(1997)123:11(1041)

Given a prescribed smooth depth profile ``h(x)`` and constant discharge ``Q``,
the bed ``zb(x)`` is constructed so that the steady shallow-water equations
with Manning friction hold exactly (manufactured topography).
"""

from __future__ import annotations

from typing import Callable

import numpy as np

# Default M1 case parameters (MacDonald-style subcritical backwater).
M1_PARAMS = {
    "L": 1000.0,  # channel length [m]
    "B": 10.0,  # rectangular width [m]
    "Q": 2.0,  # discharge [m³/s]
    "n_manning": 0.03,  # Manning n [s/m^(1/3)]
    "g": 9.81,
    # Depth: h(x) = h_ref * (1 + amp * exp(-k * ((x/L) - 0.5)^2))
    # with h_ref = (4/g)^{1/3} so that Fr is O(0.1–0.5) subcritical.
    "amp": 0.5,
    "k": 16.0,
}


def _h_ref(g: float) -> float:
    return (4.0 / g) ** (1.0 / 3.0)


def depth_profile(x, case: str = "m1", g: float = 9.81) -> np.ndarray:
    """Prescribed analytic depth for a named MacDonald-style case.

    Case ``'m1'`` (default)
        Subcritical M1-like backwater on ``[0, L]`` with
        ``h(x) = (4/g)^{1/3} (1 + 0.5 exp(-16 ((x/L) - 1/2)^2))``,
        ``L = 1000`` m. Smooth Gaussian bump about mid-channel; entirely
        subcritical for the default ``Q``, ``B``, ``n`` in :data:`M1_PARAMS`.

    Parameters
    ----------
    x :
        Array-like streamwise coordinates [m].
    case :
        Profile name (currently only ``'m1'``).
    g :
        Gravity [m/s²] (enters the reference depth scale).

    Returns
    -------
    ndarray
        Depth ``h(x)`` [m].
    """
    x = np.asarray(x, dtype=float)
    case = case.lower()
    if case != "m1":
        raise ValueError(f"unknown case {case!r}; supported: 'm1'")

    L = M1_PARAMS["L"]
    amp = M1_PARAMS["amp"]
    k = M1_PARAMS["k"]
    href = _h_ref(g)
    return href * (1.0 + amp * np.exp(-k * ((x / L) - 0.5) ** 2))


def _dh_dx_m1(x, g: float = 9.81) -> np.ndarray:
    """Analytic derivative of the M1 depth profile."""
    x = np.asarray(x, dtype=float)
    L = M1_PARAMS["L"]
    amp = M1_PARAMS["amp"]
    k = M1_PARAMS["k"]
    href = _h_ref(g)
    xi = (x / L) - 0.5
    return href * amp * np.exp(-k * xi**2) * (-2.0 * k * xi / L)


def manning_friction(
    h,
    Q: float,
    B: float,
    n_manning: float,
) -> np.ndarray:
    """Manning friction slope for a wide rectangular channel (``R ≈ h``)."""
    h = np.asarray(h, dtype=float)
    # Sf = n² u² / h^{4/3}, u = Q/(B h)  =>  Sf = n² Q² / (B² h^{10/3})
    return (n_manning**2 * Q**2) / (B**2 * np.power(h, 10.0 / 3.0))


def bed_slope_from_depth(
    h,
    dh_dx,
    Q: float,
    B: float,
    n_manning: float,
    g: float = 9.81,
) -> np.ndarray:
    """Steady GVF bed slope ``dzb/dx`` for prescribed ``h`` and ``Q``.

    From ``dh/dx = (S0 - Sf)/(1 - Fr²)`` with ``S0 = -dzb/dx``::

        dzb/dx = -(1 - Fr²) dh/dx - Sf
    """
    h = np.asarray(h, dtype=float)
    dh_dx = np.asarray(dh_dx, dtype=float)
    Fr2 = Q**2 / (g * B**2 * h**3)
    Sf = manning_friction(h, Q, B, n_manning)
    return -(1.0 - Fr2) * dh_dx - Sf


def bed_elevation(
    x,
    case: str = "m1",
    Q: float | None = None,
    n_manning: float | None = None,
    g: float = 9.81,
    B: float | None = None,
    zb0: float = 0.0,
    depth_fn: Callable | None = None,
) -> np.ndarray:
    """Construct ``zb(x)`` so steady SWE + Manning hold for prescribed ``h(x)``.

    Integrates ``dzb/dx`` with a cumulative trapezoidal rule, anchoring
    ``zb(x[0]) = zb0``.

    Parameters
    ----------
    x :
        Strictly increasing sample locations [m].
    case :
        Named depth profile (``'m1'``) unless ``depth_fn`` is supplied.
    Q, n_manning, B :
        Discharge [m³/s], Manning ``n``, width [m]. Defaults from
        :data:`M1_PARAMS` when ``case='m1'``.
    g :
        Gravity [m/s²].
    zb0 :
        Bed elevation at ``x[0]`` [m].
    depth_fn :
        Optional callable ``depth_fn(x) -> h`` overriding ``case``.

    Returns
    -------
    ndarray
        Bed elevation ``zb`` [m], same shape as ``x``.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x must be a 1D array with at least two points")
    if np.any(np.diff(x) <= 0):
        raise ValueError("x must be strictly increasing")

    if case.lower() == "m1":
        Q = M1_PARAMS["Q"] if Q is None else Q
        n_manning = M1_PARAMS["n_manning"] if n_manning is None else n_manning
        B = M1_PARAMS["B"] if B is None else B
    else:
        if Q is None or n_manning is None or B is None:
            raise ValueError("Q, n_manning, and B are required for non-m1 cases")

    if depth_fn is not None:
        h = np.asarray(depth_fn(x), dtype=float)
        # Central differences for custom profiles.
        dh_dx = np.gradient(h, x, edge_order=2)
    elif case.lower() == "m1":
        h = depth_profile(x, case="m1", g=g)
        dh_dx = _dh_dx_m1(x, g=g)
    else:
        raise ValueError(f"unknown case {case!r}")

    dzb_dx = bed_slope_from_depth(h, dh_dx, Q=Q, B=B, n_manning=n_manning, g=g)
    zb = np.empty_like(x)
    zb[0] = zb0
    zb[1:] = zb0 + np.cumsum(0.5 * (dzb_dx[1:] + dzb_dx[:-1]) * np.diff(x))
    return zb


def gvf_residual(
    x,
    h,
    zb,
    Q: float,
    B: float,
    n_manning: float,
    g: float = 9.81,
) -> np.ndarray:
    """Pointwise residual of the steady GVF equation (should be ~0)."""
    x = np.asarray(x, dtype=float)
    h = np.asarray(h, dtype=float)
    zb = np.asarray(zb, dtype=float)
    dh_dx = np.gradient(h, x, edge_order=2)
    dzb_dx = np.gradient(zb, x, edge_order=2)
    S0 = -dzb_dx
    Fr2 = Q**2 / (g * B**2 * h**3)
    Sf = manning_friction(h, Q, B, n_manning)
    # (1 - Fr²) dh/dx - (S0 - Sf) == 0
    return (1.0 - Fr2) * dh_dx - (S0 - Sf)
