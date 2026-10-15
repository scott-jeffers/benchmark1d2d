"""Pages of the OpenHydro Bench site in the plain-language design.

``build.py`` loads the catalog, score cards and corpus data and calls these
renderers; helpers that already lived in ``build.py`` (markdown, the
server-drawn figures, the inputs and criteria tables) are reached through
``H``, which ``build.main`` sets to the build module.
"""

from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from stories import CHECK_NAMES, GROUPS, STORIES, VAR_WORDS

H: Any = None  # the build module, set by build.main()

SITE_NAME = "OpenHydro Bench"
REPO_URL = "https://github.com/scott-jeffers/benchmark1d2d"
BLOB = REPO_URL + "/blob/master/"
TREE = REPO_URL + "/tree/master/"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


# ── solvers ─────────────────────────────────────────────────────────────────
# key, column title, sub-title, what it is (model cards), colour token, kind

SOLVERS: list[dict] = [
    dict(key="demo1d", name="Demo 1D", sub="suite example", kind="suite", color="var(--ink)",
         what="Worked example that ships with the suite: plain, well-understood schemes"),
    dict(key="demo2d", name="Demo 2D", sub="suite example", kind="suite", color="var(--ink)",
         what="Worked example that ships with the suite: first-order finite volume"),
    dict(key="epanet22", name="EPANET 2.2", sub="US EPA", kind="production", color="var(--cat-3)",
         what="EPA EPANET 2.2, the standard water-network solver"),
    dict(key="hecras", name="HEC-RAS 6.6", sub="1D · 2D SWE-ELM", kind="production", color="#7C6A2E",
         what="HEC-RAS 6.6 (US Army Corps of Engineers), built and run headless with its default settings; in 2D, its default full shallow-water option (SWE-ELM)"),
    dict(key="hecras-em", name="HEC-RAS 6.6", sub="2D · SWE-EM", kind="production", color="#A0522D",
         what="HEC-RAS 6.6 2D with its Eulerian shallow-water option (SWE-EM), which HEC recommends for dam breaks"),
    dict(key="telemac", name="TELEMAC-2D", sub="openTELEMAC 9.1", kind="production", color="#D9622B",
         what="openTELEMAC-2D 9.1.1, run with its default finite-volume settings"),
    dict(key="anuga", name="ANUGA", sub="4.0.1", kind="production", color="#5E548E",
         what="ANUGA 4.0.1 (Geoscience Australia / ANU), default settings on a triangular mesh"),
    dict(key="geoclaw", name="GeoClaw", sub="Clawpack 5.9", kind="production", color="#3D8F9F",
         what="GeoClaw 5.9.2 (Clawpack), with its stock example's settings on a uniform grid"),
    dict(key="lisflood-fv1", name="LISFLOOD-FP", sub="8.3 · FV1", kind="production", color="#155E3B",
         what="LISFLOOD-FP 8.3, first-order finite-volume solver (full shallow-water equations)"),
    dict(key="lisflood-dg2", name="LISFLOOD-FP", sub="8.3 · DG2", kind="production", color="#4F8A3C",
         what="LISFLOOD-FP 8.3, second-order discontinuous Galerkin solver"),
    dict(key="lisflood-acc", name="LISFLOOD-FP", sub="8.3 · ACC", kind="production", color="#B9783A",
         what="LISFLOOD-FP 8.3, the local-inertia solver it is best known for; it leaves out the advection term"),
    dict(key="swmm524", name="EPA SWMM 5.2.4", sub="dynamic wave", kind="production", color="#7A4FA0",
         what="EPA SWMM 5.2.4 with dynamic-wave routing, the channel written as one conduit per grid cell"),
    dict(key="openswmm-dw", name="OpenSWMM 6", sub="dynamic wave", kind="production", color="#2E8B8B",
         what="OpenSWMM Engine v6 (HydroCouple's SWMM 6, pre-release) with dynamic-wave routing"),
    dict(key="openswmm-fv", name="OpenSWMM 6", sub="finite volume", kind="production", color="#C2185B",
         what="OpenSWMM Engine v6 with its new explicit finite-volume routing (FLOW_ROUTING FV), one cell per conduit"),
    dict(key="swmm515", name="SWMM 5.1.15", sub="vs SWMM 5.2.4", kind="compat", color="var(--cat-2)",
         what="EPA SWMM 5.1.15, the previous release, compared with SWMM 5.2.4"),
    dict(key="openswmm6", name="OpenSWMM 6", sub="vs SWMM 5.2.4", kind="compat", color="var(--cat-5)",
         what="OpenSWMM Engine v6 (HydroCouple's SWMM 6, pre-release), compared with SWMM 5.2.4"),
    dict(key="epanet20", name="EPANET 2.0", sub="vs EPANET 2.2", kind="compat", color="var(--cat-2)",
         what="EPANET 2.0, compared with EPANET 2.2"),
]
SOLVER = {s["key"]: s for s in SOLVERS}
PRODUCTION_2D = ["hecras", "hecras-em", "telemac", "anuga", "geoclaw", "lisflood-fv1", "lisflood-dg2", "lisflood-acc"]
NOT_YET = ["TUFLOW", "MIKE 21", "Iber", "BASEMENT", "Delft3D FM"]


def solver_key(name: str) -> str | None:
    n = (name or "").lower()
    if n.startswith("demo-swe2d"):
        return "demo2d"
    if n.startswith("demo"):
        return "demo1d"
    if n.startswith("openswmm engine v6 dynamic wave"):
        return "openswmm-dw"
    if n.startswith("openswmm engine v6 finite volume"):
        return "openswmm-fv"
    if n.startswith("openswmm engine"):
        return "openswmm6"
    if n.startswith("epa swmm 5.2.4") and "official" not in n:
        return "swmm524"
    if "epanet 2.2" in n:
        return "epanet22"
    if "epanet 2.0" in n:
        return "epanet20"
    if "swmm 5.1" in n:
        return "swmm515"
    if "telemac" in n:
        return "telemac"
    if "hec-ras" in n:
        return "hecras-em" if "swe-em" in n else "hecras"
    if n.startswith("anuga"):
        return "anuga"
    if n.startswith("geoclaw"):
        return "geoclaw"
    if n.startswith("lisflood"):
        for k in ("fv1", "dg2", "acc"):
            if k in n:
                return f"lisflood-{k}"
    return None


def load_runs(dirs: list[Path]) -> dict[str, dict[str, dict]]:
    """test_id -> solver key -> score card (later directories win)."""
    runs: dict[str, dict[str, dict]] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.scorecard.json")):
            if "cross_build" in p.parts:
                continue
            try:
                c = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            k = solver_key((c.get("solver") or {}).get("name", ""))
            if k is None or "test_id" not in c:
                continue
            c["_path"] = p
            runs.setdefault(c["test_id"], {})[k] = c
    return runs


def sid_of(test_id: str) -> str:
    return test_id.split("_")[0]


def story(m: dict) -> dict:
    s = dict(STORIES.get(sid_of(m["test_id"]), {}))
    s.setdefault("name", m.get("title", m["test_id"]))
    s.setdefault("group", "compat" if m["track"] == "B" else "rivers")
    s.setdefault("question", m.get("description", ""))
    s.setdefault("what", m.get("description", ""))
    s.setdefault("why", "")
    s.setdefault("must", [])
    return s


# ── plain-language numbers ──────────────────────────────────────────────────


def nice(v: float, sig: int = 2) -> str:
    if v is None or not math.isfinite(v):
        return "n/a"
    a = abs(v)
    if a == 0:
        return "0"
    if a < 1e-4:
        return "< 0.0001"
    if a >= 100:
        return f"{v:,.0f}"
    digits = max(sig - 1 - int(math.floor(math.log10(a))), 0)
    s = f"{v:.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def length(v: float) -> str:
    a = abs(v)
    if a < 0.01:
        return f"{nice(v * 1000)} mm"
    if a < 1:
        return f"{nice(v * 100)} cm"
    return f"{nice(v, 3)} m"


def with_units(v: float, units: str) -> str:
    u = (units or "").strip()
    if u == "m":
        return length(v)
    if u == "%":
        return f"{nice(v)} %"
    if u in ("1", ""):
        return nice(v)
    return f"{nice(v, 3)} {u}"


CHECK_LABELS = {
    "jump_profile": "Depth profile",
    "jump_stays_put": "Jump stays put",
    "final_level_p1": "Pond level, point 1",
    "final_level_p2": "Pond level, point 2",
    "peak_level": "Peak level",
    "final_volume": "Water stored",
    "mass_conservation": "Water conserved",
    "head_profile": "Heads along the pipe",
    "head_loss": "Head loss",
    "nodal_head": "Junction heads",
    "link_flow": "Pipe flows",
    "peak_pressure": "Peak pressure",
    "storage_balance": "Water stored by compression",
    "concentration_L1": "Concentration profile",
    "peak_depth": "Peak depths",
    "volume": "Volumes",
    "link_volume": "Volumes",
    "peak_timing": "Timing",
}


def check_label(c: dict) -> str:
    if c["id"] in CHECK_LABELS:
        return CHECK_LABELS[c["id"]]
    metric, var = c["metric"], c.get("variable", "h")
    if metric == "global_mass_error":
        return "Tracer conserved" if var == "c" else "Water conserved"
    if metric in ("L1", "L2", "Linf"):
        word = {"L1": "Average", "L2": "Typical", "Linf": "Worst"}[metric]
        return f"{word} {VAR_WORDS.get(var, var)} error"
    return CHECK_NAMES.get(metric, c["id"].replace("_", " ").capitalize())


def check_value(c: dict, observed: float | None) -> str:
    if observed is None:
        return "not computed"
    units = c["threshold"].get("units", "")
    metric = c["metric"]
    if metric == "front_position_error":
        return f"{with_units(abs(observed), units)} from exact"
    if metric == "volume_front_error":
        return f"{with_units(abs(observed), units)} {'behind' if observed < 0 else 'ahead of'} exact"
    if metric in ("global_mass_error", "storage_balance_error"):
        return f"{with_units(abs(observed), units)} error"
    if metric in ("L1", "L2", "Linf"):
        return f"{with_units(abs(observed), units)} off"
    if metric == "NSE":
        return f"NSE {nice(observed, 3)}"
    return f"{with_units(abs(observed), units)} off"


def check_limit(c: dict) -> str:
    thr = c["threshold"]
    op = thr["op"]
    v = with_units(float(thr["value"]), thr.get("units", ""))
    return {"abs<=": f"allowed: {v}", "<=": f"allowed: {v}", ">=": f"needed: at least {v}"}.get(op, f"{op} {v}")


def checks_for(m: dict, card: dict) -> list[dict]:
    """Every check of one run in plain words: label, value, limit, ok."""
    defs = {c["id"]: c for c in m["scoring"]["criteria"]}
    out = []
    for r in card.get("criteria_results", []):
        d = defs.get(r["id"], r)
        d = {**d, "threshold": r.get("threshold", d.get("threshold", {}))}
        out.append(dict(label=check_label(d), value=check_value(d, r.get("observed")), limit=check_limit(d),
                        ok=bool(r.get("passed")), gating=bool(r.get("gating", True))))
    conv = card.get("convergence_result") or {}
    if conv.get("errors"):
        p = conv.get("observed_order")
        out.append(dict(label="Improves with finer grids", value=f"rate {nice(p, 2)}" if p is not None else "no rate",
                        limit=f"needed: {nice(conv.get('min_observed_order'), 2)} or better", ok=bool(conv.get("passed")), gating=True))
    return out


def summary_line(m: dict, card: dict) -> str:
    """One plain sentence for the results panel."""
    parts = []
    for c in checks_for(m, card):
        parts.append(f"{c['label']}: {c['value']} ({c['limit']})")
    return ". ".join(parts) + "."


# Findings worth a sentence on a model card: (short id, solver key) -> text
NOTES = {
    ("A1F-010", "telemac"): "The front is 5.8 m behind the exact one (2.5 m allowed) and closes in on finer grids at order 0.71, just under the 0.8 required. The thin leading edge, 1 mm deep, lags further (39 m): it stays dry too long. HLLC and second-order settings did not change that.",
    ("A1F-001", "hecras"): "HEC-RAS stores input elevations to the nearest 0.001 ft (0.3 mm), even in a metric project. The depth error therefore stops at about 0.1 mm on every grid: far inside the limit, but it cannot shrink with the grid, so convergence cannot be shown.",
    ("A1F-010", "hecras"): "The flood advances as a steep bore and its front is 97 m behind the exact one; the error does not fall on finer grids. HEC-RAS 2D was built and run with no GUI step; the dam-break step was carried in by a restart file.",
    ("A1F-010", "hecras-em"): "SWE-EM, the option HEC recommends for dam breaks, gets 40 m closer than the default SWE-ELM (58 m behind) but does not converge.",
    ("A1F-011", "hecras"): "The bore is in about the right place (depth error 5 mm), but the error does not fall on finer grids.",
    ("A1F-011", "hecras-em"): "Error 8 mm, inside the limit, but it grows slightly on finer grids.",
    ("A1F-010", "swmm524"): "SWMM's dynamic-wave routing is built for sewer networks, not dam breaks: the front is 41 m behind and the error does not shrink on finer grids.",
    ("A1F-011", "swmm524"): "The bore smears and lags, and the stored water drifts 4 % above the exact volume: dynamic-wave routing is not built for moving shocks.",
    ("A1F-010", "openswmm-dw"): "Identical, number for number, to EPA SWMM 5.2.4: OpenSWMM 6 keeps the original dynamic-wave solver.",
    ("A1F-011", "openswmm-dw"): "Identical, number for number, to EPA SWMM 5.2.4: OpenSWMM 6 keeps the original dynamic-wave solver.",
    ("A1F-001", "openswmm-dw"): "Identical, number for number, to EPA SWMM 5.2.4.",
    ("A1F-011", "openswmm-fv"): "OpenSWMM 6's new finite-volume routing passes the test that SWMM's dynamic wave fails.",
    ("A1F-010", "openswmm-fv"): "Much closer than dynamic wave (3.3 m behind instead of 41 m) and conserves water; it misses the 2.5 m limit and converges at 0.73.",
    ("A1F-001", "openswmm-fv"): "Accurate (0.4 mm) but converges at 0.76, just under the 0.8 required, where dynamic wave reaches 1.7.",
    ("B-RTC-001", "openswmm6"): "Pumps switch the same 74 times, but one node peaks 50 % higher than in SWMM 5.2.4, at a different time; worth a look by the OpenSWMM developers.",
    ("A1F-010", "lisflood-acc"): "The local-inertia scheme leaves out the advection term, so it is not expected to get a dam break right; it is shown because it is what most LISFLOOD-FP users run.",
    ("A1F-011", "lisflood-acc"): "The local-inertia scheme leaves out the advection term, so it cannot form the right bore; it is shown because it is what most LISFLOOD-FP users run.",
    ("A2C-EA1", "lisflood-acc"): "The pond settles 5 mm above the sill (2 cm allowed). The stored volume is 2.7 % above the figure integrated on the EA's 2 m DEM; that check does not gate, because a 10 m grid samples the ground differently.",
    ("A2C-EA4", "lisflood-fv1"): "Run at the specification's 5 m grid (the demo solver uses the allowed 10 m alternative). The inflow enters as LISFLOOD-FP point sources on the cells the inflow line crosses.",
    ("A2A-020", "telemac"): "Run with TELEMAC's HLLC scheme: its default kinetic scheme goes unstable with this supercritical inflow. The depth is right (1 cm) and converges, but the stored water is 0.15 % above exact (0.1 % allowed), as with ANUGA (0.13 % below).",
    ("A2A-010", "telemac"): "Passes: 0.13 mm from the exact water level, converging at first order. The inflow discharge and outlet level are listed in the order TELEMAC numbers its open boundaries.",
    ("A2C-EA2", "telemac"): "Run with a 1 s largest step, as for the other codes: with TELEMAC's step left to the 5-minute output interval, the dry start took long first steps that undersampled the inflow and lost 6 % of the water.",
}
CASE_NOTES = {
    "A1F-010": "Since version 2 the front is measured by volume: the point beyond which the last 5 % of the released water lies. Version 1 used the 1 mm depth contour, which every production code failed by 12 to 211 m: on the thin tip a millimetre of depth moves that contour about 10 m, and production codes treat water shallower than about 1 mm as dry. The 1 mm edge is still reported, but no longer decides the result.",
}


# ── layout ──────────────────────────────────────────────────────────────────

NAV = [("results.html", "Tests &amp; results"), ("score.html", "Score your model"), ("how-it-works.html", "How it works")]
FOOT = [("corpus.html", "SWMM corpus"), ("reports.html", "Reports and audit"), ("downloads.html", "Downloads"),
        ("method.html", "Method"), ("get-started.html", "Command line")]
LOGO = ('<svg viewBox="0 0 34 22" aria-hidden="true"><path class="w" d="M1 8 C7 2 11 14 17 8 S27 2 33 8" fill="none" stroke-width="3" stroke-linecap="round"/>'
        '<path class="b" d="M1 18 H33" stroke-width="3" stroke-linecap="round"/></svg>')


def layout(title: str, body: str, active: str, depth: int = 0, description: str = "", scripts: str = "", math: bool = False) -> str:
    up = "../" * depth
    nav = "".join(f'<a href="{up}{href}"{" aria-current=\"page\"" if href == active else ""}>{label}</a>' for href, label in NAV)
    foot = "".join(f'<a href="{up}{href}">{label}</a>' for href, label in FOOT)
    built = datetime.now(timezone.utc).strftime("%d %b %Y")
    full_title = SITE_NAME if title == SITE_NAME else f"{title} · {SITE_NAME}"
    katex = ""
    if math:
        katex = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">'
                 '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>'
                 '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description or 'Open benchmarks for flood, river, drainage and water-network models. Every test has a known right answer.')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}static/style.css">
<link rel="icon" href="{up}static/favicon.svg" type="image/svg+xml">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="{up}index.html">{LOGO}{SITE_NAME}</a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
    <nav class="site-nav" id="site-nav" aria-label="Main">{nav}<a class="gh" href="{REPO_URL}">GitHub</a></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <span>{SITE_NAME} · open source (Apache-2.0) · data under each test's own <a href="{BLOB}DATA_LICENSES.md">licence</a> · built {built}</span>
    <nav aria-label="More">{foot}<a href="{REPO_URL}">Source on GitHub</a></nav>
  </div>
</footer>
<script src="{up}static/site.js" defer></script>
{scripts}
{katex}
</body>
</html>
"""


def badge(card: dict | None) -> str:
    if card is None:
        return '<span class="badge none">Not run</span>'
    return '<span class="badge pass">✓ Passes</span>' if card.get("passed") else '<span class="badge fail">✗ Fails</span>'


def json_script(id_: str, data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="{id_}">{text}</script>'


# ── home ────────────────────────────────────────────────────────────────────


def _ritter_hero() -> str:
    return """<svg viewBox="0 0 600 250" role="img" aria-label="Animated exact solution of a dam break: a wall of water collapses and spreads over dry ground" id="hero-svg">
  <rect x="20" y="220" width="560" height="14" fill="var(--bed-soft)"></rect>
  <path id="hero-water" d="M20,220 L20,60 L300,60 L300,220 Z" fill="var(--water)" fill-opacity="0.22" stroke="var(--water)" stroke-width="2.5" stroke-linejoin="round"></path>
  <line x1="300" x2="300" y1="40" y2="220" stroke="#8796A0" stroke-dasharray="4 5" stroke-width="1.5"></line>
  <text x="306" y="52" font-size="13" fill="var(--ink-2)" font-family="IBM Plex Mono, monospace">dam removed at t = 0</text>
  <text x="560" y="30" text-anchor="end" font-size="15" fill="var(--ink)" font-family="IBM Plex Mono, monospace" id="hero-t">t = 0 s</text>
</svg>"""


def home_page(manifests: list[dict], runs: dict, census, parity, evidence: dict) -> str:
    n_tests = len(manifests)
    solvers_seen = {k for r in runs.values() for k in r}
    families = {SOLVER[k]["name"].split(" ")[0] for k in solvers_seen if k in SOLVER}
    prod = [SOLVER[k]["name"] for k in SOLVERS_ORDER(solvers_seen) if SOLVER[k]["kind"] == "production"]
    prod_names = sorted({p.split(" ")[0] for p in prod}, key=lambda s: [x["name"].split(" ")[0] for x in SOLVERS].index(s))
    n_models = len(census) if census is not None else 0
    # findings
    fronts = {}
    for k, c in (runs.get("A1F-010_ritter_dry_bed_dambreak") or {}).items():
        if SOLVER.get(k, {}).get("kind") != "production":
            continue
        for r in c.get("criteria_results", []):
            if r["id"] == "volume_front" and r.get("observed") is not None:
                fronts[k] = abs(r["observed"])
    cards = []
    if fronts:
        ok = [k for k, v in fronts.items() if v <= 2.5]
        near = sorted(v for v in fronts.values() if 2.5 < v <= 10)
        far = sorted(v for v in fronts.values() if v > 10)
        who = ", ".join(SOLVER[k]["name"].split(" ")[0] for k in ok) or "none"
        cards.append(f"""<a class="finding" href="tests/A1F-010.html">
  <div class="num">{len(ok)} of {len(fronts)}</div>
  <b>Few production models place the flood front</b>
  <p>In the classic dam break, {len(ok)} of {len(fronts)} production runs put the front within 2.5 m after one minute ({esc(who)}). {len(near)} more are {nice(near[0], 2) if near else '–'}–{nice(near[-1], 2) if near else '–'} m behind; {len(far)} are {nice(far[0], 2) if far else '–'}–{nice(far[-1], 3) if far else '–'} m behind.</p>
</a>""")
    if "hecras" in (runs.get("A1F-001_macdonald_m1_backwater") or {}):
        cards.append("""<a class="finding" href="tests/A1F-001.html">
  <div class="num">0.001 ft</div>
  <b>HEC-RAS rounds its inputs</b>
  <p>HEC-RAS 6.6 stores elevations to the nearest thousandth of a foot, even in a metric model. Its backwater error is tiny (0.1 mm) but cannot shrink on finer grids.</p>
</a>""")
    for summ, df in parity or []:
        if summ.get("tier") == "nightly" and summ.get("candidate") == "swmm-5.1.15":
            sc = df[df["status"] == "scored"]
            same = int((sc["worst_pct"].abs() == 0).sum())
            pct = 100 * same / max(len(sc), 1)
            cards.append(f"""<a class="finding" href="corpus.html">
  <div class="num cool">{pct:.0f} %</div>
  <b>SWMM 5.1 and 5.2 mostly agree</b>
  <p>{same} of {len(sc)} real models give identical results. Pumps, green roofs and groundwater are where the versions part ways.</p>
</a>""")
    xb = [c for v in evidence.values() for c in v if not c.get("passed")]
    if xb:
        worst = max((abs(r["observed"]) for c in xb for r in c["criteria_results"] if r.get("observed") is not None and r["threshold"].get("units") == "%"), default=None)
        if worst:
            cards.append(f"""<a class="finding" href="tests/B-RTC-001.html">
  <div class="num">{nice(worst, 2)} %</div>
  <b>Two builds of SWMM 5.2.4 disagree</b>
  <p>The official Windows release and the Python build give different peak depths on a pump station run by control rules.</p>
</a>""")
    fv = (runs.get("A1F-011_stoker_wet_bed_dambreak") or {})
    if fv.get("openswmm-fv", {}).get("passed") and not fv.get("swmm524", {"passed": True}).get("passed"):
        cards.insert(1, """<a class="finding" href="tests/A1F-011.html">
  <div class="num cool">SWMM 6</div>
  <b>OpenSWMM 6's new routing passes where SWMM 5 fails</b>
  <p>On a dam break into shallow water, HydroCouple's finite-volume routing gets the bore right and converges; SWMM's classic dynamic wave, in both 5.2.4 and 6, does not.</p>
</a>""")
    findings = "".join(cards[:4])
    featured = [
        ("A1F-010", '<rect x="0" y="100" width="280" height="20" fill="var(--bed-soft)"/><path d="M0 40 H110 C150 40 170 92 280 98 V100 H0 Z" fill="var(--water)" fill-opacity="0.35"/><path d="M0 40 H110 C150 40 170 92 280 98" fill="none" stroke="var(--water)" stroke-width="2.5"/>'),
        ("A1P-020", '<rect x="20" y="50" width="240" height="24" rx="4" fill="none" stroke="var(--ink-2)" stroke-width="2"/><rect x="22" y="52" width="140" height="20" fill="var(--water)" fill-opacity="0.3"/><rect x="162" y="52" width="96" height="20" fill="#C2501C" fill-opacity="0.35"/><rect x="252" y="36" width="10" height="52" fill="var(--ink)"/>'),
        ("A2C-EA4", '<ellipse cx="60" cy="62" rx="56" ry="40" fill="var(--water)" fill-opacity="0.4"/><ellipse cx="72" cy="62" rx="92" ry="54" fill="var(--water)" fill-opacity="0.18"/><rect x="0" y="52" width="10" height="20" fill="#C2501C"/>'),
        ("B-RTC-001", '<path d="M30 30 V96 H110 V30" fill="none" stroke="var(--ink-2)" stroke-width="2"/><rect x="32" y="62" width="76" height="32" fill="var(--water)" fill-opacity="0.35"/><circle cx="150" cy="80" r="14" fill="none" stroke="var(--ink)" stroke-width="2"/><path d="M164 80 H250 V40" fill="none" stroke="var(--water)" stroke-width="3"/>'),
    ]
    tcards = "".join(
        f'<a class="card test-card" href="tests/{s}.html"><svg viewBox="0 0 280 120" aria-hidden="true">{svg}</svg>'
        f'<div class="body"><h3>{esc(STORIES[s]["name"])}</h3><p>{esc(STORIES[s]["question"])}</p></div></a>'
        for s, svg in featured if s in STORIES)
    body = f"""
<div class="wrap">
<section class="hero">
  <div>
    <p class="eyebrow">Open benchmarks for water models</p>
    <h1>Does your flood model get the water right?</h1>
    <p class="lede">Every test here has a known right answer. Run your model, compare, and get a result anyone can check.</p>
    <div class="btns"><a class="btn primary" href="results.html">See how models score</a><a class="btn ghost" href="score.html">Score your model</a></div>
  </div>
  <figure>
    {_ritter_hero()}
    <figcaption>A dam vanishes and the water floods dry ground. This is the exact answer, worked out by Ritter in 1892. <a href="tests/A1F-010.html">See how real models do on it →</a></figcaption>
  </figure>
</section>
<section class="section tight" aria-label="At a glance">
  <div class="stats">
    <div><b>{n_tests}</b><span>tests, from pipes to floodplains</span></div>
    <div><b>{len(families)}</b><span>models scored, including {esc(', '.join(prod_names[:4]))}</span></div>
    <div><b>{n_models:,}</b><span>real SWMM models checked</span></div>
    <div><b>Every</b><span>result re-run from scratch on each change</span></div>
  </div>
</section>
<section class="section">
  <h2>Start where you are</h2>
  <div class="grid">
    <a class="card" href="results.html"><div class="kicker">I use flood or drainage models</div><h3>Compare models on the same tests</h3><p>See which models pass, which fail, and by how much — in plain numbers.</p></a>
    <a class="card" href="score.html"><div class="kicker">I build a solver</div><h3>Score your code</h3><p>Download the inputs, run them, and check your results in the browser before you submit.</p></a>
    <a class="card" href="how-it-works.html"><div class="kicker">I review model results</div><h3>Check why a result can be trusted</h3><p>Fixed inputs, pinned software versions, every result reproducible.</p></a>
  </div>
</section>
</div>
<section class="dark section">
  <div class="wrap">
    <div class="head-row"><h2>What the tests found</h2><a href="results.html">All results →</a></div>
    <div class="grid">{findings}</div>
  </div>
</section>
<div class="wrap">
<section class="section">
  <h2>Tests built from real engineering questions</h2>
  <p class="muted">Each one isolates something a model has to get right on a real project.</p>
  <div class="grid narrow">{tcards}</div>
</section>
<section class="section" id="how">
  <h2>How it works</h2>
  <div class="grid how">
    <div class="card"><div class="label">01 — Same inputs</div><p>Every model gets identical terrain, flows and settings, each file fixed by a fingerprint so nobody can quietly change it.</p></div>
    <div class="card"><div class="label">02 — A known right answer</div><p>An exact mathematical solution, laboratory measurements, or — for compatibility — the output of a pinned SWMM or EPANET release.</p></div>
    <div class="card"><div class="label">03 — A result anyone can check</div><p>Pass or fail, with the number that decided it and the limit it was held to. Every result is re-run automatically and signed.</p></div>
  </div>
  <p class="muted" style="margin-top:24px">Want the full method — convergence rates, how limits are chosen, the audit log? <a href="how-it-works.html">Read how it works</a>.</p>
</section>
</div>"""
    script = """<script>
(function(){var p=document.getElementById('hero-water'),tl=document.getElementById('hero-t');if(!p)return;
var g=9.81,h0=1,x0=1000,c0=Math.sqrt(g*h0),t=0,red=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function depth(x,t){if(t<=0)return x<=x0?h0:0;if(x<=x0-c0*t)return h0;if(x>=x0+2*c0*t)return 0;var a=2*c0-(x-x0)/t;return a*a/(9*g);}
function draw(){var tt=Math.min(t,60),d='M20,220 ';for(var x=400;x<=1600;x+=6){d+='L'+(20+(x-400)/1200*560).toFixed(1)+','+(220-depth(x,tt)*160).toFixed(1)+' ';}
p.setAttribute('d',d+'L580,220 Z');tl.textContent='t = '+tt.toFixed(0)+' s';}
if(red){t=40;draw();return;}
setInterval(function(){t=t>=72?0:t+0.4;draw();},50);draw();})();
</script>"""
    return layout(SITE_NAME, body, "index.html", scripts=script)


def SOLVERS_ORDER(keys) -> list[str]:
    return [s["key"] for s in SOLVERS if s["key"] in keys]


# ── tests and results ───────────────────────────────────────────────────────


def results_page(manifests: list[dict], runs: dict, parity, census) -> str:
    shown = [m for m in manifests if m["status"] != "draft" or runs.get(m["test_id"])]
    drafts = [m for m in manifests if m not in shown]
    cols = SOLVERS_ORDER({k for m in shown for k in (runs.get(m["test_id"]) or {})})
    head = "".join(f'<th scope="col">{esc(SOLVER[k]["name"])}<small>{esc(SOLVER[k]["sub"])}</small></th>' for k in cols)
    cells: dict[str, dict] = {}
    rows = []
    for gkey, gname in GROUPS.items():
        group = [m for m in shown if story(m)["group"] == gkey]
        if not group:
            continue
        rows.append(f'<tr class="group-row" data-group="{gkey}"><th colspan="{len(cols) + 1}">{esc(gname)}</th></tr>')
        for m in group:
            sid = sid_of(m["test_id"])
            st = story(m)
            tds = []
            for k in cols:
                c = (runs.get(m["test_id"]) or {}).get(k)
                if c is None:
                    tds.append('<td><span class="notrun" aria-label="not run">—</span></td>')
                    continue
                cid = f"{sid}|{k}"
                ok = bool(c.get("passed"))
                cells[cid] = dict(test=st["name"], sid=sid, solver=f'{SOLVER[k]["name"]} · {SOLVER[k]["sub"]}', passed=ok,
                                  checks=checks_for(m, c), note=NOTES.get((sid, k), ""))
                label = f'{st["name"]}, {SOLVER[k]["name"]} {SOLVER[k]["sub"]}: {"passes" if ok else "fails"}'
                tds.append(f'<td><button type="button" class="cellbtn {"pass" if ok else "fail"}" data-cell="{esc(cid)}" aria-pressed="false" aria-label="{esc(label)}">{"✓" if ok else "✗"}</button></td>')
            rows.append(f'<tr data-group="{gkey}"><th scope="row"><a href="tests/{sid}.html">{esc(st["name"])}</a><small>{esc(sid)}</small></th>{"".join(tds)}</tr>')
    filters = '<button type="button" class="pill" data-filter="all" aria-pressed="true">All tests</button>' + "".join(
        f'<button type="button" class="pill" data-filter="{k}" aria-pressed="false">{esc(v)}</button>' for k, v in GROUPS.items()
        if any(story(m)["group"] == k for m in shown))
    first = "A1F-010|telemac" if "A1F-010|telemac" in cells else next(iter(cells), None)
    panel = _panel_html(cells.get(first)) if first else ""
    # corpus parity bars, one per candidate engine
    corpus = ""
    bars_html = []
    n_models = 0
    labels = {"swmm-5.1.15": "SWMM 5.1.15", "openswmm-6": "OpenSWMM Engine v6"}
    for summ, df in sorted(parity or [], key=lambda p: p[0].get("candidate") != "swmm-5.1.15"):
        if summ.get("tier") != "nightly":
            continue
        n_models = max(n_models, int(summ["models"]))
        sc = df[df["status"] == "scored"]
        w = sc["worst_pct"].abs()
        parts = [(int((w == 0).sum()), "#155E3B", "identical"), (int(((w > 0) & (w <= 1)).sum()), "#0B6FB8", "within 1 %"),
                 (int(((w > 1) & (w <= 5)).sum()), "#7FB2D9", "1–5 %"), (int((w > 5).sum()), "#D9622B", "over 5 %"),
                 (int(len(df) - len(sc)), "#C9D3D9", "could not run or nothing to compare")]
        bar = "".join(f'<div style="flex:{n} 1 0;background:{col}">{n if n > 40 else ""}</div>' for n, col, _ in parts if n)
        key = "".join(f'<span><span class="sw" style="background:{col}"></span>{lab}</span>' for _, col, lab in parts)
        aria = ", ".join(f"{n} {lab}" for n, _, lab in parts)
        name = labels.get(summ["candidate"], summ["candidate"])
        bars_html.append(f'<p style="margin:14px 0 6px"><b>{esc(name)}</b></p><div class="bar" role="img" aria-label="{esc(name)}: {esc(aria)}">{bar}</div>')
    if bars_html:
        corpus = f"""<div class="card" style="flex:1 1 520px;min-width:0">
  <h2 style="font-size:22px">SWMM compatibility across real models</h2>
  <p class="muted">Other SWMM engines compared with EPA SWMM 5.2.4 on {n_models} models from the HydroCouple collection, node by node and pipe by pipe.</p>
  {''.join(bars_html)}
  <div class="keyrow">{key}</div>
  <p style="margin:16px 0 0">Biggest differences are in pump models, green roofs and groundwater: real changes between engines, not noise. <a href="corpus.html#parity">See the corpus →</a></p>
</div>"""
    waits = "".join(f'<li><a href="tests/{sid_of(m["test_id"])}.html"><b>{esc(story(m)["name"])}</b></a><br><span>{esc(_need(m))}</span></li>' for m in drafts[:6])
    more = f'<li class="muted">…and {len(drafts) - 6} more</li>' if len(drafts) > 6 else ""
    wait = f"""<div class="card" style="flex:1 1 340px;min-width:0">
  <h2 style="font-size:22px">Waiting on data</h2>
  <p class="muted">{len(drafts)} more tests are defined but need data their owners have to release. Can you help?</p>
  <ul class="waitlist">{waits}{more}</ul>
</div>""" if drafts else ""
    prod_list = ", ".join(SOLVER[k]["name"] + (" " + SOLVER[k]["sub"].split("·")[-1].strip() if k.startswith("lisflood") else "") for k in cols if SOLVER[k]["kind"] == "production")
    body = f"""
<div class="wrap">
<section class="page-head">
  <h1>Tests and results</h1>
  <p class="lede">Every model runs the same inputs against a known right answer. Click any result to see the numbers behind it.</p>
</section>
<div class="filters" role="group" aria-label="Filter tests">{filters}</div>
<aside class="card panel" aria-live="polite" id="panel">{panel}</aside>
<div class="matrix-wrap">
  <table class="matrix" id="matrix">
    <thead><tr><th scope="col" class="test-col">Test</th>{head}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<p class="small" style="margin-top:14px;max-width:90ch">The demo solvers are simple worked examples that ship with the suite. {esc(prod_list)} are production software, each run as a black box with its own default settings. SWMM 5.1.15 and EPANET 2.0 are scored for compatibility with the current releases, not for physics.</p>
<section class="section" style="display:flex;flex-wrap:wrap;gap:20px;align-items:stretch">{corpus}{wait}</section>
</div>
{json_script("cells", cells)}"""
    script = """<script>
(function(){var data=JSON.parse(document.getElementById('cells').textContent),panel=document.getElementById('panel');
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function render(id){var c=data[id];if(!c)return;var h='<div class="kicker">Selected result</div><div class="title">'+esc(c.test)+'</div><div class="solver">'+esc(c.solver)+'</div>'+
(c.passed?'<span class="badge pass">✓ Passes</span>':'<span class="badge fail">✗ Fails</span>')+'<ul class="checks">';
c.checks.forEach(function(k){h+='<li><span class="'+(k.ok?'ok':'no')+'" aria-label="'+(k.ok?'met':'not met')+'">'+(k.ok?'✓':'✗')+'</span><span><b>'+esc(k.label)+':</b> '+esc(k.value)+' <span class="muted">('+esc(k.limit)+')</span></span></li>';});
h+='</ul>'+(c.note?'<p class="small">'+esc(c.note)+'</p>':'')+'<a href="tests/'+esc(c.sid)+'.html#m-'+esc(id.split('|')[1])+'" style="font-weight:600">Open the test →</a>'+
'<div class="legend-mini"><span><b class="ok">✓</b> passes every check</span><span><b class="no">✗</b> fails at least one check</span><span><b style="color:#A7B4BC">—</b> not run yet</span></div>';
panel.innerHTML=h;var rc=panel.getBoundingClientRect();if(rc.top<60||rc.top>innerHeight-80)panel.scrollIntoView({behavior:'smooth',block:'start'});document.querySelectorAll('.cellbtn').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.cell===id?'true':'false');});}
document.querySelectorAll('.cellbtn').forEach(function(b){b.addEventListener('click',function(){render(b.dataset.cell);});});
var first=document.querySelector('.cellbtn[data-cell="'+(%FIRST%)+'"]');if(first)first.setAttribute('aria-pressed','true');
document.querySelectorAll('[data-filter]').forEach(function(f){f.addEventListener('click',function(){var g=f.dataset.filter;
document.querySelectorAll('[data-filter]').forEach(function(o){o.setAttribute('aria-pressed',o===f?'true':'false');});
document.querySelectorAll('#matrix tbody tr').forEach(function(r){r.hidden=!(g==='all'||r.dataset.group===g);});});});})();
</script>""".replace("%FIRST%", json.dumps(first or ""))
    return layout("Tests and results", body, "results.html", scripts=script,
                  description="Which flood, river, drainage and network models pass which tests, and by how much.")


def _panel_html(c: dict | None) -> str:
    if not c:
        return ""
    checks = "".join(f'<li><span class="{"ok" if k["ok"] else "no"}" aria-label="{"met" if k["ok"] else "not met"}">{"✓" if k["ok"] else "✗"}</span>'
                     f'<span><b>{esc(k["label"])}:</b> {esc(k["value"])} <span class="muted">({esc(k["limit"])})</span></span></li>' for k in c["checks"])
    return (f'<div class="kicker">Selected result</div><div class="title">{esc(c["test"])}</div><div class="solver">{esc(c["solver"])}</div>'
            f'{"<span class=\"badge pass\">✓ Passes</span>" if c["passed"] else "<span class=\"badge fail\">✗ Fails</span>"}'
            f'<ul class="checks">{checks}</ul>' + (f'<p class="small">{esc(c["note"])}</p>' if c["note"] else "")
            + f'<a href="tests/{esc(c["sid"])}.html" style="font-weight:600">Open the test →</a>'
            '<div class="legend-mini"><span><b class="ok">✓</b> passes every check</span><span><b class="no">✗</b> fails at least one check</span>'
            '<span><b style="color:#A7B4BC">—</b> not run yet</span></div>')


def _need(m: dict) -> str:
    pend = [e for e in m["inputs"] if e.get("pending")]
    if pend:
        return pend[0]["pending"]["reason"].split(". ")[0].rstrip(".")
    ref = m.get("reference") or {}
    if ref.get("kind") == "measured" and ref.get("availability") != "available":
        return "Measured data not yet released"
    return "Inputs being prepared"


# ── case pages ──────────────────────────────────────────────────────────────


def _tags(m: dict) -> str:
    kind = (m.get("reference") or {}).get("kind")
    first = {"analytic": ("Exact answer known", "blue"), "measured": ("Measured in a lab or the field", "blue"),
             "intercomparison": ("Benchmark with known end states", "blue"), "pinned_engine": ("Compared with a pinned engine", "blue")}.get(kind, (kind, ""))
    dim = m["physics"]["dimensionality"]
    flow = m["physics"]["flow_type"].replace("_", " ")
    status = {"frozen": "Frozen: counts toward certification", "candidate": "Candidate", "draft": "Draft: needs data"}.get(m["status"], m["status"])
    return (f'<span class="tag {first[1]}">{esc(first[0])}</span><span class="tag">{esc(dim)} · {esc(flow)}</span>'
            f'<span class="tag">{esc(status)}</span>')


def _source_short(m: dict) -> str:
    cites = m["provenance"].get("citations") or []
    if not cites:
        return ""
    c = cites[0]
    a = (c.get("authors") or ["?"])[0].split(",")[0]
    return f"{a} ({c.get('year', 'n.d.')})"


def compare_chart(m: dict, runs: dict, exact: dict | None, profiles: dict) -> tuple[str, str]:
    """The interactive chart (exact answer + model curves, optional replay). Returns (html, data script)."""
    from profiles import CHART

    sid = sid_of(m["test_id"])
    spec = CHART.get(sid)
    if spec is None or (exact is None and not profiles):
        return "", ""
    series = []
    for k in SOLVERS_ORDER(set(profiles)):
        if k in profiles:
            s = SOLVER[k]
            label = s["name"] if not k.startswith("lisflood") else f'{s["name"]} {s["sub"].split("·")[-1].strip()}'
            series.append(dict(key=k, label=label, color=s["color"], x=profiles[k]["x"], y=profiles[k]["y"],
                               dots=s["kind"] == "suite", dx=profiles[k].get("dx")))
    fronts = {}
    for k, c in runs.items():
        for r in c.get("criteria_results", []):
            if r.get("metric") == "volume_front_error" and r.get("observed") is not None:
                fronts[k] = round(r["observed"], 1)
    front_exact = None
    if sid == "A1F-010":
        from references.ritter import volume_front_position

        prm = m["reference"]["generator"]["parameters"]
        front_exact = volume_front_position(float(m["simulation"]["t_end"]), 0.05, h0=prm["h0"], x0=prm["x0"], g=prm["g"])
    data = dict(sid=sid, xlabel=spec["x"], ylabel=spec["y"], exact=exact, series=series, fronts=fronts,
                front=sid == "A1F-010" and bool(fronts), front_exact=front_exact, dam=(1000 if sid == "A1F-010" else 0 if sid == "A1F-011" else None))
    toggles = '<button type="button" class="pill" data-series="exact" aria-pressed="true"><span class="sw" style="background:var(--water)"></span>Exact answer</button>' if exact else ""
    for s in series:
        sw = f'<span class="sw dot" style="color:{s["color"]}"></span>' if s["dots"] else f'<span class="sw" style="background:{s["color"]}"></span>'
        on = "false" if s["key"] == "lisflood-acc" and len(series) > 1 else "true"
        toggles += f'<button type="button" class="pill" data-series="{s["key"]}" aria-pressed="{on}">{sw}{esc(s["label"])}</button>'
    replay = bool(exact and exact.get("frames"))
    t_end = float(m["simulation"]["t_end"])
    controls = ""
    if replay:
        controls = f"""<div class="controls">
  <button type="button" class="play" id="play" aria-label="Play"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg></button>
  <label>Time since the start<input type="range" id="scrub" min="0" max="{len(exact['times']) - 1}" step="1" value="{len(exact['times']) - 1}"></label>
  <div class="readout" id="readout">Press play, or drag the slider, to watch the exact answer unfold. Models are compared at the end, t = {nice(t_end, 3)} s.</div>
</div>"""
    elif series:
        controls = '<div class="controls"><div class="readout" id="readout"></div></div>'
    html_ = f"""<section class="replay" aria-label="Exact answer and model results">
  <div class="replay-top"><div class="toggles" role="group" aria-label="Show on the chart">{toggles}</div><div class="tlabel" id="tlabel" aria-live="polite"></div></div>
  <svg viewBox="0 0 1000 380" role="img" aria-label="{esc(spec['y'])} against {esc(spec['x'].lower())}: exact answer and model results" id="chart"></svg>
  {controls}
</section>"""
    return html_, json_script("chart-data", data)


def conv_chart(m: dict, runs: dict) -> str:
    """Server-drawn log–log chart of error against grid size, one line per model."""
    pts = []
    for k in SOLVERS_ORDER(set(runs)):
        c = (runs[k].get("convergence_result") or {})
        if c.get("errors") and c.get("spacings") and all(e > 0 for e in c["errors"]):
            pts.append((k, c["spacings"], c["errors"], c.get("observed_order")))
    if not pts:
        return ""
    allx = [x for _, xs, _, _ in pts for x in xs]
    ally = [y for _, _, ys, _ in pts for y in ys]
    x0, x1 = math.log10(min(allx)) - 0.08, math.log10(max(allx)) + 0.08
    y0, y1 = math.log10(min(ally)) - 0.15, math.log10(max(ally)) + 0.15
    W, Hh, L, R, T, B = 560, 300, 74, 20, 16, 44
    px = lambda v: L + (math.log10(v) - x0) / (x1 - x0) * (W - L - R)  # noqa: E731
    py = lambda v: T + (y1 - math.log10(v)) / (y1 - y0) * (Hh - T - B)  # noqa: E731
    units = "m" if m["scoring"]["convergence"].get("variable") in ("h",) else ""
    out = []
    for e in range(int(math.floor(y0)), int(math.ceil(y1)) + 1):
        for mult in (1, 3):
            v = mult * 10 ** e
            if y0 <= math.log10(v) <= y1:
                lab = length(v) if units == "m" else nice(v)
                out.append(f'<line x1="{L}" x2="{W - R}" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="var(--rule-2)"/>'
                           f'<text x="{L - 8}" y="{py(v) + 4:.1f}" text-anchor="end" font-size="12" fill="var(--ink-2)" font-family="IBM Plex Mono, monospace">{lab}</text>')
    for v in sorted(set(allx)):
        out.append(f'<text x="{px(v):.1f}" y="{Hh - 22}" text-anchor="middle" font-size="12" fill="var(--ink-2)" font-family="IBM Plex Mono, monospace">{nice(v, 3)}</text>')
    out.append(f'<text x="{(L + W - R) / 2}" y="{Hh - 4}" text-anchor="middle" font-size="12" fill="var(--ink-2)">grid cell size</text>')
    legend = []
    for k, xs, ys, p in pts:
        s = SOLVER[k]
        col = s["color"]
        d = " ".join(f'{"M" if i == 0 else "L"}{px(x):.1f},{py(y):.1f}' for i, (x, y) in enumerate(zip(xs, ys)))
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.5"><title>{esc(s["name"])} {esc(s["sub"])}: rate {nice(p, 2) if p is not None else "n/a"}</title></path>')
        for x, y in zip(xs, ys):
            fill = "var(--sheet)" if s["kind"] == "suite" else col
            out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4" fill="{fill}" stroke="{col}" stroke-width="2"/>')
        name = s["name"] if not k.startswith("lisflood") else f'{s["name"]} {s["sub"].split("·")[-1].strip()}'
        legend.append(f'<span><span class="sw" style="background:{col};width:14px;height:4px"></span>{esc(name)} · rate {nice(p, 2) if p is not None else "n/a"}</span>')
    svg = f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Average error against grid size for each model, on log scales" style="width:100%;height:auto;display:block">{"".join(out)}</svg>'
    return svg + f'<div class="keyrow">{"".join(legend)}</div>'


def case_page(m: dict, runs: dict, exact: dict | None, profiles: dict, legacy_figs: str, evidence: list[dict]) -> str:
    from benchmark1d2d.catalog.promotion import checklist, next_stage

    sid = sid_of(m["test_id"])
    st = story(m)
    group = GROUPS.get(st["group"], "")
    chart_html, chart_data = compare_chart(m, runs, exact, profiles)
    figure = chart_html or (f'<section class="card">{legacy_figs}</section>' if legacy_figs.strip() else "")
    must = "".join(f"<li>{esc(x)}</li>" for x in st["must"])
    story_cards = f"""<section class="story grid">
  <div class="card"><h2>What happens</h2><p>{esc(st['what'])}</p></div>
  <div class="card"><h2>Why it matters</h2><p>{esc(st['why'])}</p></div>
  <div class="card"><h2>A good model must</h2><ul>{must}</ul></div>
</section>"""
    # model cards
    mcards = []
    for k in SOLVERS_ORDER(set(runs)):
        c = runs[k]
        s = SOLVER[k]
        checks = "".join(f'<div class="check{"" if ck["ok"] else " bad"}"><div class="k">{esc(ck["label"])}</div>'
                         f'<div class="v">{"✓" if ck["ok"] else "✗"} {esc(ck["value"])}</div><div class="lim">{esc(ck["limit"])}</div></div>'
                         for ck in checks_for(m, c))
        note = NOTES.get((sid, k), "")
        name = s["name"] if not k.startswith("lisflood") else f'{s["name"]} {s["sub"].split("·")[-1].strip()}'
        mcards.append(f"""<article class="model-card" id="m-{k}">
  <div class="top"><div><div class="name"><span class="sw" style="background:{s['color']}"></span>{esc(name)}</div><div class="what">{esc(s['what'])}</div></div>{badge(c)}</div>
  <div class="checks-grid">{checks}</div>
  {f'<p class="note">{esc(note)}</p>' if note else ''}
  <p class="note small">Signed score card: <a href="../data/scorecards/{k}/{esc(c['_path'].name)}" download>{esc((c.get('solver') or {}).get('name', ''))}</a></p>
</article>""")
    levels = (m["simulation"].get("mesh_refinement") or {}).get("levels") or []
    grid_txt = (f"Each model runs the same inputs on {len(levels)} grids, from {nice(max(levels), 3)} m down to {nice(min(levels), 3)} m cells."
                if len(levels) > 1 else "Each model runs the same inputs.")
    case_note = CASE_NOTES.get(sid)
    not_yet = ""
    if m["track"] == "A" and m["physics"]["dimensionality"] in ("1D", "2D") and m["status"] != "draft":
        missing = [SOLVER[k]["name"] for k in PRODUCTION_2D if k not in runs and not k.startswith("lisflood-")]
        if not any(k.startswith("lisflood") for k in runs):
            missing.append("LISFLOOD-FP")
        missing = list(dict.fromkeys(missing)) + NOT_YET
        not_yet = (f'<div class="notyet"><div><b>Not run yet:</b> {esc(", ".join(missing))}</div>'
                   f'<a href="../score.html" style="font-weight:600">Run it and add yours →</a></div>')
    if mcards:
        models = f"""<section class="section" style="padding-bottom:0">
  <h2>How models did</h2>
  <p class="muted">{esc(grid_txt)}</p>
  {f'<p class="callout">{esc(case_note)}</p>' if case_note else ''}
  <div class="models">{''.join(mcards)}{not_yet}</div>
</section>"""
    else:
        models = f"""<section class="section" style="padding-bottom:0"><h2>How models did</h2>
  <p>No model has been scored on this test yet.</p>{not_yet}</section>"""
    # convergence + status
    conv = conv_chart(m, runs)
    cards_for = list(runs.values()) + list(evidence or [])
    items = checklist(m, cards_for)
    nxt = next_stage(m, cards_for)
    if m["status"] == "frozen":
        status_txt = "<b>Frozen.</b> Inputs, answer and limits are fixed; results count toward certification."
    elif nxt["next"]:
        need = [b["label"].lower() for b in nxt["blockers"]]
        status_txt = (f"<b>{esc(m['status'].capitalize())}.</b> " + (f"To become {esc(nxt['next'])} it needs: {esc('; '.join(need))}." if need else
                                                                         f"Ready to become {esc(nxt['next'])}, pending a maintainer's review."))
    else:
        status_txt = f"<b>{esc(m['status'].capitalize())}.</b>"
    downloads = [f'<a href="../data/cases/{sid}.zip" download>Download inputs (.zip)</a>']
    if (H.DIST / "data" / "check" / f"{sid}.json").exists():
        downloads.append(f'<a href="../score.html#{sid}">Check your results in the browser</a>')
    downloads.append(f'<a href="#details">Cite this test</a>')
    downloads.append(f'<a href="{TREE}{esc(m["_rel"])}">View on GitHub</a>')
    status_card = f"""<div class="card"><h2>Status of this test</h2><p>{status_txt}</p><div class="links-col">{''.join(downloads)}</div></div>"""
    split = (f'<section class="section split-row" style="padding-bottom:0"><div class="card"><h2>Error shrinks as the grid gets finer</h2>'
             f'<p class="small">Average error on each grid. A steeper line means the model converges faster.</p>{conv}</div>{status_card}</section>'
             if conv else f'<section class="section split-row" style="padding-bottom:0">{status_card}</section>')
    # technical details
    kind = m["reference"]["kind"]
    ref_desc = {
        "analytic": f"Exact solution from <code>{esc(m['reference'].get('generator', {}).get('module', ''))}.{esc(m['reference'].get('generator', {}).get('function', ''))}</code>.",
        "intercomparison": "No exact or measured answer exists. The test is scored on states that follow from the inputs alone; published package results are context only.",
        "measured": f"Measured data at <code>{esc(m['reference'].get('data_path', ''))}</code>; availability: <b>{esc(str(m['reference'].get('availability', 'unknown')).replace('_', ' '))}</b>.",
        "pinned_engine": f"{esc(m['reference'].get('engine'))} {esc(m['reference'].get('version'))}, run on the test's own input.",
    }.get(kind, "")
    states = ""
    if kind == "intercomparison":
        states = '<div class="table-scroll"><table class="data"><thead><tr><th>Expected state</th><th class=num>Value</th><th>Why it must hold</th></tr></thead><tbody>' + "".join(
            f"<tr><td><b>{esc(s['id'])}</b><div class=muted>{esc(s['variable'])}{(' at ' + esc(s['where'])) if s.get('where') else ''}</div></td>"
            f"<td class=num>{H.fmt(s['value'])} {esc(s['units'])}</td><td>{esc(s['derivation'])}</td></tr>"
            for s in m["reference"]["expected_states"]) + "</tbody></table></div>"
    pending = [e for e in m["inputs"] if e.get("pending")]
    missing = ""
    if pending or (kind == "measured" and m["reference"].get("availability") != "available"):
        items_ = "".join(f"<li><b>{esc(e['path'])}</b>: {esc(e['pending']['reason'])} <span class=muted>Source: {esc(e['pending'].get('obtain_from', ''))}</span></li>" for e in pending)
        if kind == "measured" and m["reference"].get("availability") != "available":
            items_ += f"<li><b>Reference data</b>: {esc(str(m['reference'].get('availability', '')).replace('_', ' '))}.</li>"
        missing = f'<div class="callout warn"><h2>What this test still needs</h2><ul>{items_}</ul></div>'
    readme = m["_case_dir"] / "README.md"
    readme_html = H.md(readme.read_text(encoding="utf-8")) if readme.is_file() else ""
    notes = m["provenance"].get("adaptation_notes", "")
    readme_html = H._dedupe_paragraphs(readme_html, [m.get("description", ""), notes]).strip()
    cites = "".join(f"<li>{H.citation_text(c)}</li>" for c in m["provenance"]["citations"])
    xb = ""
    rb = [c for c in (evidence or []) if "official" in str(c.get("solver", {}).get("name", ""))]
    if rb:
        c = rb[0]
        worst = "; ".join(f"{check_label(r)} {with_units(abs(r['observed']), r['threshold']['units'])}" for r in c["criteria_results"] if r.get("observed") is not None)
        xb = (f'<p class="callout{"" if c["passed"] else " warn"}"><b>Second build of the reference.</b> The official EPA {esc(c["solver"]["name"].replace("EPA ", ""))} binaries, '
              f'run on this input and scored against the reference: {"pass" if c["passed"] else "fail"} ({esc(worst)}). '
              + ("Both builds agree, so the reference does not depend on the compiler." if c["passed"] else
                 "The two builds of the same version disagree beyond this test's limits.") + "</p>")
    legacy = f'<h3>More figures</h3><div class="figs-legacy">{legacy_figs}</div>' if (chart_html and legacy_figs.strip()) else ""
    tech = f"""<details class="tech" id="details">
  <summary>Technical details for reviewers <span>Checks, reference, inputs, sources</span></summary>
  <div class="tech-body">
    {missing}
    <h3>Checks and why each limit was chosen</h3>
    {H.criteria_table(m, None)}
    {xb}
    <h3>Reference</h3><p>{ref_desc}</p>{states}
    {legacy}
    <h3>Promotion checklist</h3>
    <p class="small">Only frozen tests count toward certification. This list is computed from the manifest and the published score cards; the rules are in the <a href="../method.html">method</a>.</p>
    {H.checklist_html(items)}
    <h3>Inputs</h3>{H.inputs_table(m)}
    {f'<h3>About this test</h3><div class="prose">{readme_html}</div>' if readme_html else ''}
    <h3>Sources</h3><ul class="cites">{cites}</ul>
    <p class="small">Test {esc(m['test_id'])} · version {esc(m['case_version'])} · data licence {esc(m['provenance']['license'])}</p>
  </div>
</details>"""
    head = f"""<nav class="crumbs" aria-label="Breadcrumb"><a href="../results.html">Tests &amp; results</a> / {esc(group)}</nav>
<header class="case-head">
  <div>
    <div class="chip-row">{_tags(m)}</div>
    <h1>{esc(st['name'])}</h1>
    <p class="lede">{esc(st['question'])}</p>
  </div>
  <div class="case-id">Test {esc(sid)}<br>{esc(_source_short(m))}<br>Version {esc(m['case_version'])}</div>
</header>"""
    body = f'<div class="wrap">{head}{figure}{story_cards}{models}{split}{tech}</div>{chart_data}'
    scripts = '<script src="../static/chart.js" defer></script>' if chart_html else ""
    return layout(st["name"], body, "results.html", depth=1, description=st["question"], scripts=scripts, math=True)


# ── score your model ────────────────────────────────────────────────────────


def score_page(manifests: list[dict], checkable: list[dict]) -> str:
    checkable = sorted(checkable, key=lambda c: c["sid"])
    opts = "".join(f'<option value="{esc(c["sid"])}">{esc(c["sid"])} — {esc(c["name"])}</option>' for c in checkable)
    rows = "".join(
        f'<tr id="{esc(c["sid"])}"><td><a href="tests/{esc(c["sid"])}.html"><b>{esc(c["name"])}</b></a><div class="muted small">{esc(c["sid"])}</div></td>'
        f'<td><a href="data/cases/{esc(c["sid"])}.zip" download>Inputs (.zip)</a></td>'
        f'<td>{" · ".join(f"<a href=\"data/check/{esc(c["sid"])}_dx{esc(lv)}_template.csv\" download>{esc(lv)}</a>" for lv in c["level_names"])}</td></tr>'
        for c in checkable)
    others = [m for m in manifests if sid_of(m["test_id"]) not in {c["sid"] for c in checkable} and m["status"] != "draft"]
    other_rows = "".join(f'<li><a href="tests/{sid_of(m["test_id"])}.html">{esc(story(m)["name"])}</a> <span class="muted">({esc(sid_of(m["test_id"]))})</span></li>' for m in others)
    body = f"""
<div class="wrap">
<section class="page-head">
  <h1>Score your model</h1>
  <p class="lede">Download a test's inputs, run them in your own software, and check your results here. Nothing is uploaded: the check runs in your browser.</p>
</section>
<section class="section tight">
  <div class="card" style="display:flex;flex-wrap:wrap;gap:40px;align-items:center;padding:36px">
    <div style="flex:1 1 380px;min-width:0">
      <h2>Three steps</h2>
      <ol class="steps">
        <li><span class="n">1</span><span><b>Pick a test</b> and download its inputs, plus a results template for each grid size.</span></li>
        <li><span class="n">2</span><span><b>Run it</b> in your own model — any software, any language — and fill in the template.</span></li>
        <li><span class="n">3</span><span><b>Drop your results here</b> to see how they score. Drop all the grid sizes at once to see the convergence rate too.</span></li>
      </ol>
    </div>
    <div class="drop" id="drop">
      <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="var(--water)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></svg>
      <b>Drop results files</b>
      <label class="small" for="case">Test</label>
      <select id="case">{opts}</select>
      <label class="small" for="files">CSV files, one per grid size</label>
      <input type="file" id="files" accept=".csv,text/csv" multiple>
      <span class="small">Checked in your browser, never uploaded</span>
    </div>
  </div>
  <div class="report" id="report" aria-live="polite"></div>
</section>
<section class="section tight">
  <h2>Tests you can check here</h2>
  <p class="muted">These tests have exact answers, so your results can be compared point by point. Templates list the points to report at, one file per grid size.</p>
  <div class="table-scroll"><table class="data"><thead><tr><th>Test</th><th>Inputs</th><th>Results templates (grid size)</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>
<section class="section tight">
  <h2>Getting an official score card</h2>
  <p>The browser check uses the same formulas as the scorer, but an official result is a signed score card made by the command-line tool, which also reads Parquet, network results and the other tests:</p>
<pre><code>pip install -e ".[dev]"
benchmark1d2d score A1F-010 --results mine_dx1.25.csv \\
  --refinement mine_dx10.csv mine_dx5.csv mine_dx2.5.csv mine_dx1.25.csv \\
  --solver-name my-solver --solver-version 1.0</code></pre>
  <p>Then open a pull request adding your score cards, or <a href="{REPO_URL}/issues/new">open an issue</a> and attach them. The <a href="get-started.html">command-line guide</a> covers network and compatibility tests.</p>
  {f'<h3>Tests scored with the command line only</h3><ul class="small">{other_rows}</ul>' if other_rows else ''}
</section>
</div>"""
    return layout("Score your model", body, "score.html", scripts='<script src="static/check.js" defer></script>',
                  description="Check your model's results against the exact answers, in your browser.")


# ── how it works ────────────────────────────────────────────────────────────


def how_page(manifests: list[dict], runs: dict) -> str:
    n = len(manifests)
    by_status = {s: sum(1 for m in manifests if m["status"] == s) for s in ("frozen", "candidate", "draft")}
    body = f"""
<div class="wrap">
<section class="page-head">
  <h1>How it works</h1>
  <p class="lede">A benchmark is only useful if its answers are right and its results can be repeated. Here is how this one makes sure of both.</p>
</section>
<section class="section tight">
  <div class="grid how">
    <div class="card"><div class="label">01 — Same inputs</div><p>Every model gets identical terrain, flows and settings. Each file is fixed by a SHA-256 fingerprint, so nobody can quietly change it, and large files are fetched and checked against that fingerprint.</p></div>
    <div class="card"><div class="label">02 — A known right answer</div><p>Exact mathematical solutions (dam breaks, backwater, water hammer), laboratory and field measurements, or — for compatibility — the output of a pinned SWMM or EPANET release.</p></div>
    <div class="card"><div class="label">03 — A result anyone can check</div><p>Pass or fail, with the number that decided it and the limit it was held to. Score cards are hashed and signed; every one shown here is re-run by CI on each change.</p></div>
  </div>
</section>
<section class="section tight">
  <h2>What "passes" means</h2>
  <div class="grid">
    <div class="card"><h3>Every check, not an average</h3><p>A model passes a test only if it meets every check: how close it gets to the answer, whether it conserves water, and — where there is a grid — whether it gets steadily more accurate as the grid gets finer.</p></div>
    <div class="card"><h3>Getting better on finer grids</h3><p>A model that is close by luck on one grid is not verified. Each test is run on four grids; the error must shrink at the rate the method promises (the "observed order", as in ASME V&amp;V 20).</p></div>
    <div class="card"><h3>Limits with reasons</h3><p>Every limit is written down with why it was chosen — a measurement uncertainty, a published accuracy, or the size of two grid cells. Open any test's technical details to read them.</p></div>
  </div>
</section>
<section class="section tight">
  <h2>Production software, run fairly</h2>
  <p>Production models are installed from their official sources by automated jobs and run as black boxes with their own default settings. Only the inputs, the run length, the boundaries and the output format are set. When a model fails, its card says so and why, and the run can be reproduced from the repository.</p>
  <div class="grid narrow">
    <div class="card"><h3>HEC-RAS 6.6</h3><p>Installed silently on a Windows runner from HEC's release (installer fingerprint pinned), projects written as plain text, run headless with ras-commander.</p></div>
    <div class="card"><h3>TELEMAC-2D 9.1</h3><p>openTELEMAC from conda-forge, finite-volume settings by default.</p></div>
    <div class="card"><h3>ANUGA, GeoClaw, LISFLOOD-FP</h3><p>Built from their official releases weekly; LISFLOOD-FP's three CPU solvers are scored separately.</p></div>
    <div class="card"><h3>SWMM and EPANET</h3><p>Pinned releases (SWMM 5.2.4, EPANET 2.2) define the compatibility answers; a second build of each checks the answer does not depend on the compiler.</p></div>
  </div>
</section>
<section class="section tight">
  <h2>How tests grow up</h2>
  <div class="grid narrow">
    <div class="card"><h3>Draft · {by_status['draft']}</h3><p>Defined, but waiting on data or a verified answer.</p></div>
    <div class="card"><h3>Candidate · {by_status['candidate']}</h3><p>Inputs, answer and limits published, and at least one model scored.</p></div>
    <div class="card"><h3>Frozen · {by_status['frozen']}</h3><p>Reviewed, passed by independent models, and fixed: only frozen tests count toward certification.</p></div>
  </div>
  <p class="muted" style="margin-top:16px">{n} tests in all. The rules for each step are in the <a href="method.html">method</a>.</p>
</section>
<section class="section tight">
  <h2>Go deeper</h2>
  <div class="grid">
    <a class="card" href="method.html"><div class="kicker">Method</div><h3>Verification and validation plan</h3><p>Convergence, tolerances, promotion rules and the literature behind every test.</p></a>
    <a class="card" href="reports.html"><div class="kicker">Audit</div><h3>Reports and fixes</h3><p>Every problem found in the suite itself, and what was done about it.</p></a>
    <a class="card" href="corpus.html"><div class="kicker">Real models</div><h3>The SWMM corpus</h3><p>1,400 real SWMM models used to compare engine versions.</p></a>
    <a class="card" href="downloads.html"><div class="kicker">Data</div><h3>Downloads</h3><p>Every input, score card and schema, with fingerprints.</p></a>
  </div>
</section>
</div>"""
    return layout("How it works", body, "how-it-works.html", description="How the benchmark keeps its answers right and its results repeatable.")


def redirect(to: str) -> str:
    return (f'<!doctype html><meta charset="utf-8"><title>Moved</title><meta http-equiv="refresh" content="0; url={esc(to)}">'
            f'<link rel="canonical" href="{esc(to)}"><p>This page moved to <a href="{esc(to)}">{esc(to)}</a>.</p>')
