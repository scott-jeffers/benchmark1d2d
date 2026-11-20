"""Per-result measures: how far each result is from the right answer (protocol 4.0).

The suite reports measurements, not verdicts or standings
(docs/methodology/evidence.md):

* **Percent difference**: each check's error as a percentage of the quantity
  it is an error in (site/difference.py), the largest over a test's accuracy
  checks. It is shown beside the error in its own units.
* **No ranks and no rating.** Results on a test are listed by configuration
  tier and then in the model registry's order, never by score. Models are
  never combined into one number across tests.
* A run its own engine flags (unconverged, mass balance failed) is shown with
  that flag.
"""

from __future__ import annotations

import math

import difference


def score(card: dict | None) -> float | None:
    """Percent difference from the right answer: the largest over the test's judged checks (None when none applies)."""
    return difference.result(card)


def flagged(card: dict | None) -> str | None:
    """Why the engine itself flags this run (it did not converge, its mass balance failed), or None."""
    rep = ((card or {}).get("run") or {}).get("engine") or {}
    return rep.get("flag_reason") if rep.get("flagged") else None


def _num(s: float) -> str:
    if s < 1:
        return f"{s:.2g}"
    if s < 10:
        return f"{s:.1f}"
    if s < 1e4:
        return f"{s:.0f}"
    return f"{s:.0e}".replace("e+0", "e").replace("e+", "e")


def label(s: float | None) -> str:
    if s is None:
        return "no score"
    if not math.isfinite(s):
        return "no result"
    if s < 0.01:
        return "under 0.01 % off"
    return f"{_num(s)} % off"


def short(s: float | None) -> str:
    """Compact form for tables and cells: '0.42 %', '12 %'."""
    if s is None:
        return "–"
    if not math.isfinite(s):
        return "∞"
    if s < 0.01:
        return "<0.01 %"
    return f"{_num(s)} %"


# Shading of the percent difference, for reading a table at a glance. The
# shades are not verdicts and carry no engineering meaning. Where a check
# carries an engineering-significance value from a cited source (manifest
# ``significance``), the site also says whether the result meets it.
BANDS = [(0.1, "s0", "under 0.1 %"), (1.0, "s1", "0.1–1 %"), (3.0, "s2", "1–3 %"), (10.0, "s3", "3–10 %"), (30.0, "s4", "10–30 %"), (math.inf, "s5", "over 30 %")]


def klass(s: float | None) -> str:
    """CSS shade: s0 (closest) … s5 (furthest), sn for no score."""
    if s is None:
        return "sn"
    for hi, k, _ in BANDS:
        if s < hi:
            return k
    return "s5"


TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2}


def rows_for_test(by: dict[str, dict], order: list[str], tier_of=None, keep=None, hold=None) -> list[dict]:
    """One row per result on a test: key, score, flag. Listed by configuration tier, then in ``order``
    (the model registry's order); never by score. ``hold(key)`` gives a reason a result is labelled
    (a submission not yet reproduced by CI)."""
    pos = {k: i for i, k in enumerate(order)}
    rows = [{"key": k, "score": score(c), "flag": flagged(c) or (hold(k) if hold else None),
             "tier": tier_of(k) if tier_of else None}
            for k, c in by.items() if keep is None or keep(k)]
    return sorted(rows, key=lambda r: (TIER_ORDER.get(r["tier"], 3), pos.get(r["key"], len(pos)), r["key"]))


def fmt_time(s: float | None) -> str:
    if s is None:
        return "–"
    if s < 1:
        return f"{s:.2f} s"
    if s < 60:
        return f"{s:.1f} s"
    if s < 3600:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.1f} h"
