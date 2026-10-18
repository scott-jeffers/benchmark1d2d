"""Every result as a percent difference from the right answer.

A check in the catalogue measures an error in its own units (a depth error in
metres, a mass error in %, an NSE). The site reports each one as a percentage
of the quantity it is an error in, from ``test_catalog/difference_scales.json``:

* already in % (mass, relative profile errors, parity with a reference engine): as is;
* an NSE: 100 × (1 − NSE), the share of the measured variance the model misses;
* anything else: |error| ÷ the scale named for that check × 100 (a depth error
  over the exact mean depth, a front error over the distance the front travels).

Checks are of four kinds (review F7: a mass error and a timing error are not
the same thing as a depth error, and should not be folded into one number):

* accuracy - how far the answer is from the right one (depth, velocity, peak, front);
* conservation - global mass, continuity and storage balance errors, in %;
* timing - arrival and peak-time errors, in seconds, never turned into a percent;
* skill - an NSE, reported as the NSE.

A result's score on a test is the largest percent difference over its judged
accuracy checks (the ones the catalogue marks informational are shown, not
counted). A test with no accuracy check is scored on its skill check as
100 x (1 - NSE), then on its conservation checks. Conservation and timing are
reported beside the score, in their own columns. There is no limit and no
verdict: results are ranked on the score (site/ranking.py).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

# The scoring method, frozen (review F5): any change to how a result's score is computed bumps this, and
# docs/methodology/scoring_v3.md says what each version did. Printed in every page's footer.
METHOD_VERSION = "3.0"
METHOD_DATE = "18 October 2026"
METHOD_DOC = "docs/methodology/scoring_v3.md"

SCALES_FILE = Path(__file__).resolve().parents[1] / "test_catalog" / "difference_scales.json"


@lru_cache(maxsize=1)
def scales() -> dict:
    return {k: v for k, v in json.loads(SCALES_FILE.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def sid_of(test_id: str) -> str:
    return test_id.split("_")[0]


def scale_for(test_id: str, check_id: str) -> tuple[float, str, str] | None:
    s = scales().get(sid_of(test_id), {}).get(check_id)
    return (float(s[0]), s[1], s[2]) if s else None


CONSERVATION = ("global_mass_error", "continuity_error", "storage_balance_error")
TIMING = ("timing_error", "arrival_time_error")
KINDS = ("accuracy", "conservation", "timing", "skill")


def kind(r: dict) -> str:
    m = r.get("metric") or ""
    if m in CONSERVATION:
        return "conservation"
    if m in TIMING or r.get("id", "").endswith("timing"):
        return "timing"
    if m == "NSE" or (r.get("threshold") or {}).get("op") == ">=":
        return "skill"
    return "accuracy"


def percent(test_id: str, r: dict) -> float | None:
    """One check's result as a percent difference (None when it can't be expressed as one)."""
    obs = r.get("observed")
    if obs is None:
        return None
    try:
        obs = float(obs)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(obs):
        return float("inf")
    thr = r.get("threshold") or {}
    units = (thr.get("units") or "").strip()
    if thr.get("op") == ">=" or r.get("metric") == "NSE":  # a skill score: 1 is perfect
        return max(0.0, 100.0 * (1.0 - obs))
    if units == "%":
        return abs(obs)
    if kind(r) == "timing":  # seconds stay seconds
        return None
    s = scale_for(test_id, r["id"])
    if s is None or s[0] == 0:
        return None
    return 100.0 * abs(obs) / s[0]


def of_what(test_id: str, r: dict) -> str:
    """What the percentage is of, in words."""
    thr = r.get("threshold") or {}
    if thr.get("op") == ">=" or r.get("metric") == "NSE":
        return "of the measured variance, missed (100 × (1 − NSE))"
    if (thr.get("units") or "").strip() == "%":
        return ""
    s = scale_for(test_id, r["id"])
    return f"of {s[2]}" if s else ""


def counted(r: dict) -> bool:
    return bool(r.get("gating", True))


def _scored(card: dict) -> list[tuple[dict, float]]:
    """The judged checks the score is taken over, with their percents: accuracy, else skill, else conservation."""
    tid = card.get("test_id", "")
    by: dict[str, list] = {}
    for r in card.get("criteria_results", []):
        if counted(r):
            v = percent(tid, r)
            if v is not None:
                by.setdefault(kind(r), []).append((r, v))
    for k in ("accuracy", "skill", "conservation"):
        if by.get(k):
            return by[k]
    return []


def result(card: dict | None) -> float | None:
    """A result's score on its test: the largest percent difference over its judged accuracy checks."""
    if not card:
        return None
    vals = [v for _, v in _scored(card)]
    return max(vals) if vals else None


def worst_check(card: dict) -> dict | None:
    """The check that sets the result's score."""
    sc = _scored(card)
    return max(sc, key=lambda x: x[1])[0] if sc else None


def side(card: dict | None) -> dict:
    """What is reported beside the score: the largest conservation error (%), the largest timing error (s),
    the lowest NSE. Each None when the test has no such check."""
    out = {"conservation": None, "timing": None, "nse": None}
    for r in (card or {}).get("criteria_results", []):
        try:
            v = float(r.get("observed"))
        except (TypeError, ValueError):
            continue
        k = kind(r)
        if k == "conservation":
            out["conservation"] = max(out["conservation"] or 0.0, abs(v))
        elif k == "timing":
            out["timing"] = max(out["timing"] or 0.0, abs(v))
        elif k == "skill":
            out["nse"] = v if out["nse"] is None else min(out["nse"], v)
    return out


def missing() -> list[tuple[str, str]]:
    """Judged checks in the catalogue that have no scale and are not already a percentage (for the build log)."""
    root = SCALES_FILE.parent
    out = []
    for m in sorted(root.glob("*/*/*/manifest.json")) + sorted(root.glob("track_b/*/manifest.json")):
        d = json.loads(m.read_text(encoding="utf-8"))
        for c in (d.get("scoring") or {}).get("criteria", []):
            thr = c.get("threshold") or {}
            if thr.get("op") == ">=" or (thr.get("units") or "").strip() == "%" or kind(c) in ("skill", "timing"):
                continue
            if scale_for(d["test_id"], c["id"]) is None:
                out.append((sid_of(d["test_id"]), c["id"]))
    return out
