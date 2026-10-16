"""Scoring method 2 (adopted 16 October 2026; ``docs/methodology/scoring_v2.md``).

The scorer writes these verdicts into every new score card (``verdict``,
``judgement``, a ``margin`` per check; ``passed`` is true only for *pass*).
Cards from method 1 are re-judged with ``assess`` when they are read, so the
whole site uses one method. The rules:

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

Overall (method 2.1, 16 October 2026): the result *passes* when it is
*Accurate*. *Converges* is its own verdict, shown with every result, and a
result carries the *Verified* label only when it passes **and** converges
(or has no grid study, or is at its declared precision). Method 2.0 (the
morning of 16 October) also failed results whose rate was below the minimum
and called those whose range straddled it inconclusive.
"""

from __future__ import annotations

import math
import re
from typing import Any

METHOD = "2.1"
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
        return {**out, "verdict": "fail", "roundoff": True,
                "why": "errors at round-off on every grid: the results are the reference itself"}
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
    # Results at round-off on every grid are the reference itself, not a solution: they fail outright.
    overall = "fail" if conv.get("roundoff") else accurate
    verified = accurate == "pass" and conv["verdict"] in ("pass", "n/a", "at_floor")
    return {"method": METHOD, "checks": checks, "accurate": accurate, "worst_margin": max(ms) if ms else None,
            "converges": conv, "overall": overall, "verified": verified, "method1": _method1(card, accurate)}


def _method1(card: dict, accurate: str) -> str:
    """The verdict method 1 gave (or would give): every gating check, and the averaged rate at its minimum."""
    if card.get("scoring_method") != METHOD:
        return "pass" if card.get("method1_passed", card.get("passed")) else "fail"
    conv = card.get("convergence_result") or {}
    conv_ok = bool(conv.get("passed", True)) if conv.get("errors") else True
    return "pass" if accurate == "pass" and conv_ok else "fail"


def judgement(a: dict) -> dict[str, Any]:
    """The part of ``assess`` that goes into a score card."""
    conv = {k: v for k, v in a["converges"].items() if k != "current_order"}
    return {"accurate": a["accurate"], "converges": conv, "verified": a["verified"], "worst_margin": a["worst_margin"]}


def apply(card: dict) -> dict:
    """Give a card read from disk its method-2 verdict (in place); method-1 cards keep theirs as ``method1_passed``."""
    if "_judged" in card:
        return card
    if card.get("scoring_method") == METHOD and "verdict" in card:
        a = assess(card)
        a["overall"] = card["verdict"]
    else:
        card.setdefault("method1_passed", bool(card.get("passed")))
        a = assess(card)
        card["verdict"] = a["overall"]
        card["passed"] = a["overall"] == "pass"
    card["_judged"] = a
    return card
