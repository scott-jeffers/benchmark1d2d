"""Proposed scoring method (v2), computed alongside the current one for review.

Nothing here changes a verdict: the score card's ``passed`` stays the
current method's (``docs/methodology/tolerance_rationale.md``). This module
re-reads a score card under the rules proposed in
``docs/methodology/scoring_v2.md`` so reviewers can see what would move:

1. **Two verdicts.** *Accurate*: every gating check within its limit.
   *Converges*: the error falls at the expected rate on finer grids.
2. **Margins.** Every check reports how much of its limit it uses
   (``|observed| / limit``), so a near miss and a gross failure differ.
3. **Convergence with its uncertainty.** The order is the least-squares slope
   of log error against log grid spacing over *all* levels, with a two-sided
   90 % confidence interval (Student t, n − 2 degrees of freedom). It passes
   only if the whole interval is at or above the minimum order, fails only if
   the whole interval is below it, and is *inconclusive* otherwise. With
   three levels there is one degree of freedom and the interval is wide;
   that is the honest answer three grids give.
4. **Precision floor.** A solver that stores or reports values to a known
   precision (declared in ``PRECISION``) cannot show convergence below it.
   When the finest grid's error is within ``FLOOR_FACTOR`` times that
   precision, the order is reported but does not gate (``at_floor``).
   Errors at round-off on every grid still fail, as now.

Overall: *fail* if Accurate fails or Converges fails; *inconclusive* if
Accurate passes and Converges is inconclusive; otherwise *pass*.
"""

from __future__ import annotations

import math
import re
from typing import Any

METHOD = "2-proposed"
CONFIDENCE = 0.90
FLOOR_FACTOR = 3.0

# Student t, two-sided 90 % (one-sided 95 %), by degrees of freedom.
_T90 = {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833, 10: 1.812}

# Declared output precision, by solver name (regex) and convergence variable.
PRECISION: list[tuple[str, str, float, str]] = [
    (r"^HEC-RAS [0-9.]+$", "h", 0.001 * 0.3048,  # 1D only: the evidence is from its cross-sections
     "HEC-RAS 1D stores cross-section elevations to 0.001 ft (0.3 mm), even in SI projects (docs/hecras.md)"),
]


def margin(observed: float | None, threshold: dict) -> float | None:
    """|observed| / limit for an ``abs<=`` or ``<=`` check; None when it cannot be formed."""
    if observed is None or not isinstance(observed, (int, float)) or not math.isfinite(observed):
        return None
    op, v = threshold.get("op"), float(threshold.get("value", 0.0))
    if op in ("abs<=", "<=") and v > 0:
        return abs(float(observed)) / v
    if op == ">=" and observed > 0:
        return v / float(observed)
    return None


def fit_order(errors: list[float], spacings: list[float]) -> dict[str, Any]:
    """Least-squares order over all levels with its two-sided 90 % interval."""
    pts = [(math.log(h), math.log(abs(e))) for e, h in zip(errors, spacings) if e and h > 0]
    n = len(pts)
    if n < 2:
        return {"order": None, "ci": None, "levels": n}
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx == 0:
        return {"order": None, "ci": None, "levels": n}
    slope = sum((x - mx) * (y - my) for x, y in pts) / sxx
    if n == 2:
        return {"order": slope, "ci": None, "levels": n}
    resid = [y - (my + slope * (x - mx)) for x, y in pts]
    se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
    t = _T90.get(n - 2, 1.645)
    return {"order": slope, "ci": [slope - t * se, slope + t * se], "levels": n, "se": se}


def precision_for(solver_name: str, variable: str) -> tuple[float, str] | None:
    for pat, var, value, why in PRECISION:
        if var == variable and re.search(pat, solver_name or ""):
            return value, why
    return None


def converges(card: dict) -> dict[str, Any]:
    conv = card.get("convergence_result") or {}
    errors, spacings = conv.get("errors") or [], conv.get("spacings") or []
    if not errors:
        return {"verdict": "n/a"}
    pmin = float(conv.get("min_observed_order", 0.0))
    out: dict[str, Any] = {"min": pmin, "current_order": conv.get("observed_order")}
    if all(abs(e) < 1e-12 for e in errors):
        return {**out, "verdict": "fail", "why": "errors at round-off on every grid: the results are the reference itself"}
    fit = fit_order(errors, spacings)
    out.update(fit)
    fine = abs(errors[0]) if spacings[0] <= spacings[-1] else abs(errors[-1])
    prec = precision_for((card.get("solver") or {}).get("name", ""), conv.get("variable", "h"))
    if prec and fine <= FLOOR_FACTOR * prec[0]:
        return {**out, "verdict": "at_floor", "why": f"finest-grid error {fine:.3g} is within {FLOOR_FACTOR:g}× the solver's precision ({prec[1]})"}
    ci = fit.get("ci")
    if fit.get("order") is None:
        return {**out, "verdict": "inconclusive", "why": "the order cannot be fitted"}
    if ci is None:
        return {**out, "verdict": "inconclusive", "why": "two grids give an order but no interval"}
    lo, hi = ci
    if lo >= pmin:
        return {**out, "verdict": "pass", "why": f"order {fit['order']:.2f}, 90 % interval {lo:.2f} to {hi:.2f}, all at or above {pmin:g}"}
    if hi < pmin:
        return {**out, "verdict": "fail", "why": f"order {fit['order']:.2f}, 90 % interval {lo:.2f} to {hi:.2f}, all below {pmin:g}"}
    return {**out, "verdict": "inconclusive",
            "why": f"order {fit['order']:.2f}, 90 % interval {lo:.2f} to {hi:.2f} includes {pmin:g}"
                   + (f" ({fit['levels']} grids)" if fit["levels"] <= 3 else "")}


def assess(card: dict) -> dict[str, Any]:
    """The proposed method's reading of one score card."""
    checks = []
    for r in card.get("criteria_results", []):
        checks.append({"id": r["id"], "gating": bool(r.get("gating", True)), "passed": bool(r.get("passed")),
                       "margin": margin(r.get("observed"), r.get("threshold") or {})})
    gating = [c for c in checks if c["gating"]]
    accurate = "pass" if all(c["passed"] for c in gating) else "fail"
    ms = [c["margin"] for c in gating if c["margin"] is not None]
    conv = converges(card)
    if accurate == "fail" or conv["verdict"] == "fail":
        overall = "fail"
    elif conv["verdict"] == "inconclusive":
        overall = "inconclusive"
    else:
        overall = "pass"
    return {"method": METHOD, "checks": checks, "accurate": accurate, "worst_margin": max(ms) if ms else None,
            "converges": conv, "overall": overall, "current": "pass" if card.get("passed") else "fail"}
