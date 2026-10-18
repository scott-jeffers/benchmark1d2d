"""Scores and rankings: how far each result is from the right answer, and where models stand.

The suite reports measurements, not verdicts (docs/methodology/ranking.md, scoring method 3.0):

* **Percent difference** (a result's score): each check's error as a percentage
  of the quantity it is an error in (site/difference.py), the largest over a
  test's accuracy checks. Lower is better. No limit, no pass or fail.
* **Rank within a test**: by percent difference. Two results tie when they are
  within 10 % of each other or both under 0.01 %. A run its own engine flags
  (unconverged, mass balance failed) is shown, not ranked.
* **The OpenHydro rating** (the leaderboard): a Bradley–Terry fit of the
  head-to-head results on shared tests, each test weighted equally, on the
  Elo scale with a 95 % bootstrap interval, physics groups only, rated within
  the largest group of models linked by shared tests; rank by LMArena's rule.
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


def flagged(card: dict | None) -> str | None:
    """Why the engine itself flags this run (it did not converge, its mass balance failed), or None.
    A flagged run is shown with its numbers but not ranked (review F1)."""
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


def rank_test(by: dict[str, dict], keep=None, hold=None) -> list[dict]:
    """Rows sorted best first: key, score, rank (1 + clearly better), tie flag. ``keep`` filters keys;
    ``hold(key)`` gives a reason to show a result unranked (a submission not yet reproduced)."""
    rows = [{"key": k, "score": score(c), "flag": flagged(c) or (hold(k) if hold else None)}
            for k, c in by.items() if keep is None or keep(k)]
    sid = next(iter(by.values()), {}).get("test_id", "").split("_")[0] if by else ""
    scored = sorted([r for r in rows if r["score"] is not None and not r["flag"]], key=lambda r: r["score"])
    for r in scored:
        r["rank"] = 1 + sum(1 for o in scored if o["score"] < r["score"] and not tied_on(sid, o["score"], r["score"]))
    for r in scored:
        r["tie"] = sum(1 for o in scored if o["rank"] == r["rank"]) > 1
    rest = sorted([r for r in rows if r["score"] is not None and r["flag"]], key=lambda r: r["score"])
    return scored + [dict(r, rank=None, tie=False) for r in rest] + [dict(r, rank=None, tie=False) for r in rows if r["score"] is None]


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
# or both under 0.01 %, or both inside the test's measured noise floor) is half a win each. Each test
# counts the same: its matches share one unit of weight, however many models ran it (review F2: by
# pair counting, the two dam breaks run by 16 models carried a third of the rating). A Bradley–Terry
# fit of the weighted matches gives one strength per model, shown on the Elo scale (1000 = the
# average model, +400 = ten times the odds of being closer). Its 95 % interval comes from re-drawing
# the tests with replacement and refitting. As on LMArena, a model's rank is 1 + the number of models
# whose whole interval lies above its own. Only models connected through shared tests to the
# largest group are rated together (review F8); the rest are listed unrated. ``static/rankings.js``
# repeats this exactly (same random numbers, same arithmetic).

BOOT = 200          # bootstrap draws
BOOT_SEED = 20261017
PRIOR = 0.05        # each model also plays a twentieth of a test as a draw against an average model
# The physics rating: Track A groups only. Parity with a reference engine (Track B) can only show a
# model is different, not wrong (README), and the Bellinge field test compares engines inside their
# own build-to-build noise (review F3, F10); both keep their own boards.
RATED_GROUPS = ("1d", "2d", "drainage", "water", "coupled")
NOISE_FLOOR: dict[str, float] = {}  # test short id -> percent difference two builds of the reference engine show (build.py)


def set_noise_floors(floors: dict[str, float]) -> None:
    NOISE_FLOOR.clear()
    NOISE_FLOOR.update({k: float(v) for k, v in floors.items() if v is not None})


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


def tied_on(sid: str, a: float, b: float) -> bool:
    """A draw on test ``sid``: ``tied``, or both inside the test's noise floor."""
    f = NOISE_FLOOR.get(sid)
    return tied(a, b) or (f is not None and a <= f and b <= f)


def _fit(keys: list[str], tests: list[tuple[str, list[tuple[str, float]]]], pick: list[int]) -> list[float]:
    """Bradley–Terry strengths (Hunter's MM algorithm) from the tests at indices ``pick``, each test's
    matches sharing one unit of weight; Elo-scale ratings."""
    n = len(keys)
    idx = {k: i for i, k in enumerate(keys)}
    wins = [PRIOR] * n
    games: dict[tuple[int, int], float] = {}
    for ti in pick:
        sid, rows = tests[ti]
        w = 2.0 / (len(rows) * (len(rows) - 1))
        for a in range(len(rows)):
            ka, sa = rows[a]
            for b in range(a + 1, len(rows)):
                kb, sb = rows[b]
                i, j = idx[ka], idx[kb]
                if tied_on(sid, sa, sb):
                    wins[i] += 0.5 * w
                    wins[j] += 0.5 * w
                elif sa < sb:
                    wins[i] += w
                else:
                    wins[j] += w
                key = (i, j) if i < j else (j, i)
                games[key] = games.get(key, 0.0) + w
    p = [1.0] * n
    pairs = sorted(games.items())
    for _ in range(200):
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


def _component(keys: list[str], tests: list[tuple[str, list]]) -> set[str]:
    """The largest set of models linked through shared tests (most models; then most tests; then name)."""
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for _, rows in tests:
        for r in rows[1:]:
            a, b = find(rows[0][0]), find(r[0])
            if a != b:
                parent[max(a, b)] = min(a, b)
    comps: dict[str, set] = defaultdict(set)
    for k in keys:
        comps[find(k)].add(k)

    def size(c):
        return (len(c), sum(1 for _, rows in tests if any(r[0] in c for r in rows)), "".join(sorted(c)))
    return max(comps.values(), key=size) if comps else set()


def rating_board(runs: dict[str, dict[str, dict]], keep=None, group: str | None = None) -> list[dict]:
    """The leaderboard: per model its rating, 95 % interval, rank (LMArena's rule), tests, per-group median
    difference, median run time. ``runs``: test_id -> model key -> card. Without ``group``, the physics
    groups (``RATED_GROUPS``) only."""
    tests, keys_set, times, by_group = [], set(), defaultdict(list), defaultdict(lambda: defaultdict(list))
    for tid in sorted(runs):
        g = group_of(tid)
        if (group and g != group) or (not group and g not in RATED_GROUPS):
            continue
        rows = []
        for k in sorted(runs[tid]):
            if keep is not None and not keep(k):
                continue
            s = score(runs[tid][k])
            if s is None or flagged(runs[tid][k]):
                continue
            s = s if math.isfinite(s) else 1e12
            rows.append((k, s))
            keys_set.add(k)
            by_group[k][g].append(s)
            w = (runs[tid][k].get("run") or {}).get("wall_seconds")
            if w is not None:
                times[k].append(float(w))
        if len(rows) >= 2:
            tests.append((tid.split("_")[0], rows))
    keys_all = sorted(keys_set)
    if not keys_all:
        return []
    main = _component(keys_all, tests)
    keys = sorted(main)
    mtests = [t for t in tests if t[1][0][0] in main]
    n_tests = {k: sum(1 for _, rows in tests if any(r[0] == k for r in rows)) for k in keys_all}
    point = _fit(keys, mtests, list(range(len(mtests)))) if keys else []
    rnd = _mulberry32(BOOT_SEED)
    draws = []
    for _ in range(BOOT if keys else 0):
        pick = [int(rnd() * len(mtests)) for _ in range(len(mtests))]
        draws.append(_fit(keys, mtests, pick))
    out = []
    for k in keys_all:
        r = {"key": k, "tests": n_tests[k], "groups": {g: statistics.median(v) for g, v in by_group[k].items()},
             "median_score": statistics.median([s for v in by_group[k].values() for s in v]),
             "median_time": statistics.median(times[k]) if times[k] else None, "timed": len(times[k]),
             "connected": k in main, "rating": None, "lo": None, "hi": None}
        if k in main:
            i = keys.index(k)
            col = sorted(d[i] for d in draws)
            r.update(rating=point[i], lo=col[int(0.025 * (BOOT - 1))], hi=col[int(math.ceil(0.975 * (BOOT - 1)))])
        out.append(r)
    for r in out:
        r["ranked"] = r["connected"] and r["tests"] >= MIN_TESTS
    ranked = [r for r in out if r["ranked"]]
    for r in out:
        r["rank"] = 1 + sum(1 for o in ranked if o["lo"] > r["hi"]) if r["ranked"] else None
    for r in ranked:
        r["tie"] = sum(1 for o in ranked if o["rank"] == r["rank"]) > 1
    # ranked models first, by rank (LMArena's order), then rating; unranked ones by their tests
    out.sort(key=lambda r: (not r["ranked"], r["rank"] or 0, -(r["rating"] or -1e9) if r["ranked"] else -r["tests"]))
    return out
