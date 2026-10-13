"""Grid Convergence Index (GCI) and observed-order estimation.

References
----------
Roache, P. J. (1994). "Perspective: A method for uniform reporting of grid
refinement studies." *J. Fluids Eng.*, 116(3), 405–413.

ASME (2009). *V&V 20-2009: Standard for Verification and Validation in
Computational Fluid Dynamics and Heat Transfer*. American Society of
Mechanical Engineers, New York.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def _as_float_list(values: Sequence[float]) -> list[float]:
    out = [float(v) for v in values]
    if len(out) < 2:
        raise ValueError("need at least two values")
    return out


def observed_order(*args, **kwargs) -> float:
    """Estimate observed order of accuracy ``p``.

    Two calling conventions are supported:

    1. ``observed_order(errors, spacings)`` — sequences of the same length
       (≥ 2). For constant refinement ratio ``r = h_{i+1}/h_i`` and exact
       (or norm) errors that scale as ``h^p``::

           p = ln(e_{i+1}/e_i) / ln(r)

       When three or more levels are given, the mean of successive pairwise
       estimates is returned. For non-constant ``r`` the three-grid Roache
       formula is used when possible.

    2. ``observed_order(h1, h2, h3, e1, e2, e3=None)`` — fine → coarse
       spacings and corresponding errors (``e3`` optional). With constant
       refinement ratio ``r``::

           p = ln(e2 / e1) / ln(r)

       (Roache: with solution differences ``E21 = |φ1-φ2|``,
       ``E32 = |φ2-φ3|``, pass ``[E21, E32]`` so that
       ``p = ln(E32/E21)/ln(r)``.)

    Returns
    -------
    float
        Observed order ``p``.
    """
    if len(args) == 2 and not kwargs:
        errors = _as_float_list(args[0])
        spacings = _as_float_list(args[1])
        if len(errors) != len(spacings):
            raise ValueError("errors and spacings must have the same length")
        return _observed_order_from_sequences(errors, spacings)

    if len(args) >= 5:
        h1, h2, h3, e1, e2 = (float(args[i]) for i in range(5))
        e3 = float(args[5]) if len(args) > 5 else kwargs.get("e3")
        if e3 is None and "e3" in kwargs:
            e3 = kwargs["e3"]
        spacings = [h1, h2, h3]
        if e3 is None:
            errors = [e1, e2]
            spacings = [h1, h2]
        else:
            errors = [e1, e2, float(e3)]
        return _observed_order_from_sequences(errors, spacings)

    raise TypeError(
        "observed_order(errors, spacings) or "
        "observed_order(h1, h2, h3, e1, e2, e3=None)"
    )


def _observed_order_from_sequences(errors: list[float], spacings: list[float]) -> float:
    abs_e = [abs(e) for e in errors]
    if any(e == 0.0 for e in abs_e):
        raise ValueError("errors must be non-zero to estimate order")
    if any(h <= 0.0 for h in spacings):
        raise ValueError("spacings must be positive")

    # Pairwise: p_i = ln(e_{i+1}/e_i) / ln(h_{i+1}/h_i).
    # For constant r and e ∝ h^p this recovers p. With solution differences
    # ε21 = |φ1-φ2|, ε32 = |φ2-φ3| Roache's form is p = ln(ε32/ε21)/ln(r),
    # which is the same algebra when those differences are passed as `errors`
    # ordered fine→coarse (then e1=ε21, e2=ε32 ⇒ ln(e2/e1)/ln(r)).
    orders: list[float] = []
    for i in range(len(errors) - 1):
        r = spacings[i + 1] / spacings[i]
        if abs(r - 1.0) < 1e-15:
            raise ValueError("refinement ratio must differ from 1")
        orders.append(float(np.log(abs_e[i + 1] / abs_e[i]) / np.log(r)))

    if len(errors) >= 3:
        r12 = spacings[1] / spacings[0]
        r23 = spacings[2] / spacings[1]
        if abs(r12 - r23) / max(abs(r12), abs(r23)) < 1e-9:
            # Constant r: use fine/medium and medium/coarse mean (both ≈ p).
            return float(np.mean(orders[:2]))

    return float(np.mean(orders))


def richardson_extrapolation(f1: float, f2: float, r: float, p: float) -> float:
    """Richardson extrapolation estimate of the continuum value.

    ``f_exact ≈ f1 + (f1 - f2) / (r^p - 1)`` with ``f1`` on the finer grid.
    """
    r = float(r)
    p = float(p)
    denom = r**p - 1.0
    if abs(denom) < 1e-15:
        raise ValueError("r^p - 1 is zero; cannot extrapolate")
    f1 = float(f1)
    f2 = float(f2)
    return f1 + (f1 - f2) / denom


def gci(f1: float, f2: float, r: float, p: float, Fs: float = 1.25) -> float:
    """Relative Grid Convergence Index (Roache 1994 / ASME V&V 20).

    ``GCI = Fs * |f1 - f2| / (r^p - 1) / |f1|``.

    Parameters
    ----------
    f1, f2 :
        Fine and next-coarser solution functionals.
    r :
        Refinement ratio ``h_coarse / h_fine`` (> 1).
    p :
        Observed (or formal) order.
    Fs :
        Factor of safety (1.25 for three-grid studies).
    """
    f1 = float(f1)
    f2 = float(f2)
    r = float(r)
    p = float(p)
    Fs = float(Fs)
    if f1 == 0.0:
        raise ValueError("f1 must be non-zero for relative GCI")
    denom = r**p - 1.0
    if abs(denom) < 1e-15:
        raise ValueError("r^p - 1 is zero; cannot compute GCI")
    return float(Fs * abs(f1 - f2) / denom / abs(f1))


def assess_convergence(
    spacings: Sequence[float],
    errors: Sequence[float],
    expected_order: float,
    min_observed_order: float,
    Fs: float = 1.25,
) -> dict:
    """Assess mesh convergence from successive error norms.

    Parameters
    ----------
    spacings :
        Grid spacings fine → coarse (length ≥ 2).
    errors :
        Corresponding error norms (e.g. L1 vs. exact).
    expected_order :
        Formal / design order (recorded for reporting).
    min_observed_order :
        Pass threshold on observed ``p``.
    Fs :
        GCI factor of safety.

    Returns
    -------
    dict
        ``observed_order``, ``gci_fine``, ``passed_order``,
        ``expected_order``, ``min_observed_order``.
    """
    spacings_l = _as_float_list(spacings)
    errors_l = _as_float_list(errors)
    if len(spacings_l) != len(errors_l):
        raise ValueError("spacings and errors must have the same length")

    # Round-off-level errors on every mesh cannot come from a discretisation:
    # the solver returned the reference instead of computing it. Refuse to
    # report an order (it would be invented) and do not pass.
    if all(abs(e) < 1e-12 for e in errors_l):
        return {
            "observed_order": None,
            "gci_fine": None,
            "passed_order": False,
            "expected_order": float(expected_order),
            "min_observed_order": float(min_observed_order),
            "note": "errors are at round-off on every mesh; a discretised solution always carries "
            "truncation error, so the results appear to be the reference itself",
        }

    p = observed_order(errors_l, spacings_l)
    r = spacings_l[1] / spacings_l[0]
    e1, e2 = abs(errors_l[0]), abs(errors_l[1])

    # When only error norms (vs. exact) are available, form a positive fine-grid
    # GCI from the two finest levels. Prefer the relative Roache form treating
    # successive norms as solution differences; fall back to Fs*|e1|/(r^p-1).
    denom = r**p - 1.0
    if abs(denom) < 1e-15:
        gci_fine = float("inf")
    elif e1 == 0.0:
        gci_fine = 0.0
    else:
        gci_fine = float(Fs * abs(e1 - e2) / denom / e1)
        if gci_fine <= 0.0:
            gci_fine = float(Fs * e1 / denom)

    passed = bool(p >= float(min_observed_order))
    return {
        "observed_order": float(p),
        "gci_fine": float(gci_fine),
        "passed_order": passed,
        "expected_order": float(expected_order),
        "min_observed_order": float(min_observed_order),
    }
