"""Every result as a percent difference from the right answer.

A check in the catalogue measures an error in its own units (a depth error in
metres, a mass error in %, an NSE). The site reports each one as a percentage
of the quantity it is an error in, from ``test_catalog/difference_scales.json``:

* already in % (mass, relative profile errors, parity with a reference engine): as is;
* an NSE: 100 × (1 − NSE), the share of the measured variance the model misses;
* anything else: |error| ÷ the scale named for that check × 100 (a depth error
  over the exact mean depth, a front error over the distance the front travels).

A result's difference on a test is the largest over its judged checks (the
ones the catalogue marks informational are shown, not counted). There is no
limit and no verdict: results are ranked on this number (site/ranking.py).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

SCALES_FILE = Path(__file__).resolve().parents[1] / "test_catalog" / "difference_scales.json"


@lru_cache(maxsize=1)
def scales() -> dict:
    return {k: v for k, v in json.loads(SCALES_FILE.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def sid_of(test_id: str) -> str:
    return test_id.split("_")[0]


def scale_for(test_id: str, check_id: str) -> tuple[float, str, str] | None:
    s = scales().get(sid_of(test_id), {}).get(check_id)
    return (float(s[0]), s[1], s[2]) if s else None


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


def result(card: dict | None) -> float | None:
    """A result's difference on its test: the largest percent difference over its judged checks."""
    if not card:
        return None
    tid = card.get("test_id", "")
    vals = [percent(tid, r) for r in card.get("criteria_results", []) if counted(r)]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def worst_check(card: dict) -> dict | None:
    """The check that sets the result's difference."""
    tid = card.get("test_id", "")
    best, val = None, -1.0
    for r in card.get("criteria_results", []):
        if not counted(r):
            continue
        v = percent(tid, r)
        if v is not None and v > val:
            best, val = r, v
    return best


def missing() -> list[tuple[str, str]]:
    """Judged checks in the catalogue that have no scale and are not already a percentage (for the build log)."""
    root = SCALES_FILE.parent
    out = []
    for m in sorted(root.glob("*/*/*/manifest.json")) + sorted(root.glob("track_b/*/manifest.json")):
        d = json.loads(m.read_text(encoding="utf-8"))
        for c in (d.get("scoring") or {}).get("criteria", []):
            thr = c.get("threshold") or {}
            if thr.get("op") == ">=" or (thr.get("units") or "").strip() == "%" or c.get("metric") == "NSE":
                continue
            if scale_for(d["test_id"], c["id"]) is None:
                out.append((sid_of(d["test_id"]), c["id"]))
    return out
