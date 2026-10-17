"""Scores and rankings: how far each result is from the right answer, and where models stand.

The suite reports measurements, not verdicts (docs/methodology/ranking.md):

* **Percent difference** (a result's score): every check's error as a
  percentage of the quantity it is an error in (site/difference.py), the
  largest over a test's judged checks. 0.4 = 0.4 % off; lower is better.
  There is no limit and no pass or fail.
* **Rank within a test**: by percent difference. Two results tie when they are
  within 10 % of each other or both under 0.01 % (the solvers' own
  precision). A rank is 1 + the number of results clearly ahead.
* **Overall, two measures**: the *win rate* over head-to-head comparisons on
  the tests both models ran (a tie is half a win; HELM's method), and the
  *typical error against the field*: on each test, the model's difference over
  the median model's, geometric mean over its tests (SPEC's geometric mean,
  PMP's median-relative error). Models need ``MIN_TESTS`` tests to be ranked overall.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict

import difference

TIE_REL = 0.10      # within 10 % of each other
TIE_FLOOR = 0.01    # both under 0.01 % (percent difference)
MIN_TESTS = 5

GROUPS = [
    ("1d", "1D channels"),
    ("2d", "2D surface"),
    ("drainage", "Drainage networks"),
    ("water", "Water-supply networks"),
    ("coupled", "Coupled 1D/2D"),
    ("field", "Field data"),
    ("parity", "Parity with the reference engines"),
]
GROUP_NAME = dict(GROUPS)


def group_of(test_id: str) -> str:
    sid = test_id.split("_")[0]
    if sid.startswith("B-"):
        return "parity"
    if sid == "A1F-100":
        return "field"
    if sid.startswith("A12"):
        return "coupled"
    if sid.startswith("A1D"):
        return "drainage"
    if sid.startswith("A1P"):
        return "water"
    if sid.startswith("A2"):
        return "2d"
    return "1d"


def score(card: dict | None) -> float | None:
    """Percent difference from the right answer: the largest over the test's judged checks (None when none applies)."""
    return difference.result(card)


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
    """Compact form for tables and heat-map cells: '0.42 %', '12 %'."""
    if s is None:
        return "–"
    if not math.isfinite(s):
        return "∞"
    if s < 0.01:
        return "<0.01 %"
    return f"{_num(s)} %"


# colour bands of the percent difference (no band is a verdict)
BANDS = [(0.1, "s0", "under 0.1 %"), (1.0, "s1", "0.1–1 %"), (3.0, "s2", "1–3 %"), (10.0, "s3", "3–10 %"), (30.0, "s4", "10–30 %"), (math.inf, "s5", "over 30 %")]


def klass(s: float | None) -> str:
    """CSS class on a continuous-looking scale: s0 (closest) … s5 (furthest)."""
    if s is None:
        return "sn"
    for hi, k, _ in BANDS:
        if s < hi:
            return k
    return "s5"


def tied(a: float, b: float) -> bool:
    if not (math.isfinite(a) and math.isfinite(b)):
        return a == b
    if a < TIE_FLOOR and b < TIE_FLOOR:
        return True
    hi = max(a, b)
    return hi == 0 or abs(a - b) <= TIE_REL * hi


def rank_test(by: dict[str, dict], keep=None) -> list[dict]:
    """Rows sorted best first: key, score, rank (1 + clearly better), tie flag. ``keep`` filters keys."""
    rows = [{"key": k, "score": score(c)} for k, c in by.items() if keep is None or keep(k)]
    scored = sorted([r for r in rows if r["score"] is not None], key=lambda r: r["score"])
    for r in scored:
        r["rank"] = 1 + sum(1 for o in scored if o["score"] < r["score"] and not tied(o["score"], r["score"]))
    for r in scored:
        r["tie"] = sum(1 for o in scored if o["rank"] == r["rank"]) > 1
    return scored + [dict(r, rank=None, tie=False) for r in rows if r["score"] is None]


def overall(runs: dict[str, dict[str, dict]], keep=None, group: str | None = None) -> list[dict]:
    """Per model: tests, win rate, typical error vs the field, median percent difference, median run time, rank.

    ``runs``: test_id -> model key -> card. ``keep(key)`` filters models (e.g. production only);
    ``group`` limits to one test group.
    """
    per = defaultdict(lambda: {"tests": 0, "wins": 0.0, "comps": 0, "rel": [], "scores": [], "times": []})
    for tid, by in runs.items():
        if group and group_of(tid) != group:
            continue
        rows = [r for r in rank_test(by, keep) if r["score"] is not None]
        if not rows:
            continue
        med = statistics.median([r["score"] for r in rows if math.isfinite(r["score"])] or [1.0])
        for r in rows:
            p = per[r["key"]]
            p["tests"] += 1
            p["scores"].append(r["score"])
            if math.isfinite(r["score"]):  # errors under the solvers' precision count as that precision
                p["rel"].append(max(r["score"], TIE_FLOOR) / max(med, TIE_FLOOR))
            elif not math.isfinite(r["score"]):
                p["rel"].append(1e6)
            w = ((by[r["key"]].get("run") or {}).get("wall_seconds"))
            if w is not None:
                p["times"].append(float(w))
            for o in rows:
                if o is r:
                    continue
                p["comps"] += 1
                if tied(r["score"], o["score"]):
                    p["wins"] += 0.5
                elif r["score"] < o["score"]:
                    p["wins"] += 1
    out = []
    for k, p in per.items():
        out.append({
            "key": k, "tests": p["tests"], "comparisons": p["comps"],
            "win_rate": p["wins"] / p["comps"] if p["comps"] else None,
            "vs_field": math.exp(sum(math.log(v) for v in p["rel"]) / len(p["rel"])) if p["rel"] else None,
            "median_score": statistics.median(p["scores"]) if p["scores"] else None,
            "median_time": statistics.median(p["times"]) if p["times"] else None,
            "timed": len(p["times"]),
        })
    ranked = sorted([r for r in out if r["tests"] >= MIN_TESTS and r["win_rate"] is not None], key=lambda r: (-r["win_rate"], r["vs_field"] or 1e9))
    for i, r in enumerate(ranked):
        r["rank"] = 1 + sum(1 for o in ranked if o["win_rate"] > r["win_rate"] + 0.02)
    rest = sorted([r for r in out if r not in ranked], key=lambda r: (-(r["win_rate"] or 0), -r["tests"]))
    for r in rest:
        r["rank"] = None
    return ranked + rest


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


# ── the rating: Bradley–Terry from head-to-head results, as LMArena rates chat models ──────────────
# Every test two models both ran is a match between them: the closer one wins, a tie (within 10 %,
# or both under 0.01 %) is half a win each. A Bradley–Terry fit turns all the matches into one
# strength per model, shown on the Elo scale (1000 = the average model, +400 = ten times the odds of
# winning). Its 95 % interval comes from re-drawing the tests with replacement (bootstrap) and
# refitting. As on LMArena, a model's rank is 1 + the number of models whose whole interval lies
# above its own. ``static/rankings.js`` repeats this exactly (same random numbers, same arithmetic).

BOOT = 200          # bootstrap draws
BOOT_SEED = 20261017
PRIOR = 0.5         # each model also plays one virtual draw against an average model (keeps zero-win models finite)


def _mulberry32(seed: int):
    """The browser's small seeded generator (mulberry32), bit for bit."""
    a = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    return nxt


def _fit(keys: list[str], tests: list[list[tuple[str, float]]], pick: list[int]) -> list[float]:
    """Bradley–Terry strengths (Hunter's MM algorithm) from the tests at indices ``pick``; Elo-scale ratings."""
    n = len(keys)
    idx = {k: i for i, k in enumerate(keys)}
    wins = [PRIOR] * n
    games: dict[tuple[int, int], float] = {}
    for ti in pick:
        rows = tests[ti]
        for a in range(len(rows)):
            ka, sa = rows[a]
            for b in range(a + 1, len(rows)):
                kb, sb = rows[b]
                i, j = idx[ka], idx[kb]
                if tied(sa, sb):
                    wins[i] += 0.5
                    wins[j] += 0.5
                elif sa < sb:
                    wins[i] += 1.0
                else:
                    wins[j] += 1.0
                key = (i, j) if i < j else (j, i)
                games[key] = games.get(key, 0.0) + 1.0
    p = [1.0] * n
    pairs = sorted(games.items())
    for _ in range(100):
        den = [2 * PRIOR / (pi + 1.0) for pi in p]  # the virtual draw against strength 1
        for (i, j), g in pairs:
            s = g / (p[i] + p[j])
            den[i] += s
            den[j] += s
        new = [wins[i] / den[i] for i in range(n)]
        lg = sum(math.log(x) for x in new) / n
        new = [x / math.exp(lg) for x in new]
        if max(abs(math.log(new[i] / p[i])) for i in range(n)) < 1e-9:
            p = new
            break
        p = new
    return [1000.0 + 400.0 * math.log10(x) for x in p]


def rating_board(runs: dict[str, dict[str, dict]], keep=None, group: str | None = None) -> list[dict]:
    """The leaderboard: per model its rating, 95 % interval, rank (LMArena's rule), tests, per-group median
    difference, median run time. ``runs``: test_id -> model key -> card."""
    tests, keys_set, times, by_group = [], set(), defaultdict(list), defaultdict(lambda: defaultdict(list))
    for tid in sorted(runs):
        if group and group_of(tid) != group:
            continue
        rows = []
        for k in sorted(runs[tid]):
            if keep is not None and not keep(k):
                continue
            s = score(runs[tid][k])
            if s is None:
                continue
            s = s if math.isfinite(s) else 1e12
            rows.append((k, s))
            keys_set.add(k)
            by_group[k][group_of(tid)].append(s)
            w = (runs[tid][k].get("run") or {}).get("wall_seconds")
            if w is not None:
                times[k].append(float(w))
        if len(rows) >= 2:
            tests.append(rows)
    keys = sorted(keys_set)
    if not keys:
        return []
    n_tests = {k: sum(1 for t in tests if any(r[0] == k for r in t)) for k in keys}
    point = _fit(keys, tests, list(range(len(tests))))
    rnd = _mulberry32(BOOT_SEED)
    draws = []
    for _ in range(BOOT):
        pick = [int(rnd() * len(tests)) for _ in range(len(tests))]
        draws.append(_fit(keys, tests, pick))
    out = []
    for i, k in enumerate(keys):
        col = sorted(d[i] for d in draws)
        lo, hi = col[int(0.025 * (BOOT - 1))], col[int(math.ceil(0.975 * (BOOT - 1)))]
        out.append({"key": k, "rating": point[i], "lo": lo, "hi": hi, "tests": n_tests[k],
                    "groups": {g: statistics.median(v) for g, v in by_group[k].items()},
                    "median_score": statistics.median([s for v in by_group[k].values() for s in v]),
                    "median_time": statistics.median(times[k]) if times[k] else None, "timed": len(times[k])})
    for r in out:
        r["rank"] = 1 + sum(1 for o in out if o["lo"] > r["hi"])
        r["ranked"] = r["tests"] >= MIN_TESTS
    # ranked models first, by rank (LMArena's order), then rating; a model with no head-to-head result has no rating
    out.sort(key=lambda r: (not r["ranked"], r["rank"] if r["ranked"] else 0, -r["rating"] if r["tests"] else 1e9))
    return out
