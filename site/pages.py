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

import review
from benchmark1d2d.scoring import method_v2
from stories import CHECK_NAMES, GROUP_BLURBS, GROUPS, STORIES, VAR_WORDS
from tiles import tile_svg

H: Any = None  # the build module, set by build.main()

SITE_NAME = "OpenHydro Bench"
REPO_URL = "https://github.com/scott-jeffers/benchmark1d2d"
SITE_URL = "https://scott-jeffers.github.io/benchmark1d2d/"
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
         what="EPA SWMM 5.2.4 with dynamic-wave routing; on the channel tests, the channel is written as one conduit per grid cell"),
    dict(key="openswmm-dw", name="OpenSWMM 6", sub="dynamic wave", kind="production", color="#2E8B8B",
         what="OpenSWMM Engine v6 (HydroCouple's SWMM 6, pre-release) with dynamic-wave routing"),
    dict(key="openswmm-fv", name="OpenSWMM 6", sub="finite volume", kind="production", color="#C2185B",
         what="OpenSWMM Engine v6 with its new explicit finite-volume routing (FLOW_ROUTING FV): one cell per conduit on the channel tests, its default cells per pipe on the drainage networks"),
    dict(key="hydra-uds", name="Hydra", sub="urban drainage", kind="production", color="#1F6F8B",
         what="Hydra 17 (NEER AI, Rust): its urban-drainage engine on the SWMM data model, run through its CLI with default settings"),
    dict(key="hydra-wds", name="Hydra", sub="water distribution", kind="production", color="#4A90A4",
         what="Hydra 17 (NEER AI, Rust): its water-distribution engine on the EPANET data model, run through its CLI with default settings"),
    dict(key="hydronet-fvm", name="HydroNet", sub="finite volume", kind="research", color="#8E3B46",
         what="HydroNet (Penn State) — its differentiable Roe finite-volume solver (Heun RK2, CFL 0.3), the engine inside its FVM-PINN"),
    dict(key="hydronet-pinn", name="HydroNet", sub="FVM-PINN", kind="research", color="#C46B7A",
         what="HydroNet's FVM-PINN neural network, trained per grid with the recipe of its own dam-break example (64×5 network, 5000 Adam epochs)"),
    dict(key="swmm-anuga", name="SWMM + ANUGA", sub="coupled 1D/2D", kind="suite", color="#6B4E9B",
         what="EPA SWMM 5.2.4 pipes coupled to an ANUGA 4.0.1 surface by the suite's own explicit coupler (1 s weir/orifice exchange at the manholes): a worked example of a 1D/2D model, not a product"),
    dict(key="openswmm-2d", name="OpenSWMM 6", sub="coupled 1D/2D", kind="production", color="#0E7C66",
         what="OpenSWMM Engine v6 (pre-release) with its own 1D/2D coupling: a local-inertial 2D surface with each manhole tied to a mesh vertex, run with its defaults; the surface is the case's grid with each square cut into two triangles"),
    dict(key="openswmm-2d-x", name="OpenSWMM 6", sub="coupled 1D/2D · cross mesh", kind="production", color="#5FB3A1",
         what="The same OpenSWMM 6 1D/2D model on a finer-cut mesh: each grid square cut into four triangles by both diagonals (the mesh the suite's ANUGA surface uses)"),
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
NOT_YET_COUPLED = ["TUFLOW", "InfoWorks ICM", "MIKE+", "HEC-RAS 6.6 (pipe networks)", "PCSWMM 2D", "Flood Modeller"]
NOT_YET_DRAINAGE = ["InfoWorks ICM", "MIKE+ (MOUSE)", "PCSWMM", "XPSWMM", "Flood Modeller", "HEC-RAS"]


def solver_key(name: str) -> str | None:
    n = (name or "").lower()
    if n.startswith("demo-swe2d"):
        return "demo2d"
    if n.startswith("demo"):
        return "demo1d"
    if n.startswith("openswmm engine v6 1d/2d"):
        return "openswmm-2d-x" if "four triangles" in n else "openswmm-2d"
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
    if n.startswith("swmm–anuga coupled") or n.startswith("swmm-anuga coupled"):
        return "swmm-anuga"
    if n.startswith("hydra "):
        return "hydra-wds" if "water distribution" in n else "hydra-uds"
    if n.startswith("hydronet"):
        return "hydronet-pinn" if "pinn" in n else "hydronet-fvm"
    if n.startswith("lisflood"):
        for k in ("fv1", "dg2", "acc"):
            if k in n:
                return f"lisflood-{k}"
    return None


SUBMITTED_COLORS = ["#8C564B", "#17807E", "#B8860B", "#5D6D7E", "#A23B72", "#3B7A57"]


def register_submitted(solver: dict) -> str:
    """A column for results a solver's developer or user ran and submitted."""
    import re as _re

    key = "sub-" + _re.sub(r"[^a-z0-9]+", "-", f"{solver['name']}".lower()).strip("-")
    if key not in SOLVER:
        n = sum(1 for s in SOLVERS if s["kind"] == "submitted")
        entry = dict(key=key, name=solver["name"], sub=f"submitted by {solver['submitted_by']}", kind="submitted",
                     color=SUBMITTED_COLORS[n % len(SUBMITTED_COLORS)],
                     what=(f"{solver['name']}, run by {solver['submitted_by']} and submitted as results files; "
                           "scored by the suite with the same scorer and limits as every other run"))
        SOLVERS.append(entry)
        SOLVER[key] = entry
    return key


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
            if (c.get("solver") or {}).get("submitted_by"):
                if any(part.startswith("_") for part in p.parts[-3:]):
                    continue  # worked examples are scored in CI, not shown
                k = register_submitted(c["solver"])
            else:
                k = solver_key((c.get("solver") or {}).get("name", ""))
            if k is None or "test_id" not in c:
                continue
            c["_path"] = p
            method_v2.apply(c)
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


STATE_LABELS = {
    "exchange_flow": "Manhole outflow", "street_depth": "Street depth", "final_level": "Final level",
    "discharged_volume": "Water discharged", "surface_empty": "Left on the surface", "final_level_p1": "Final level at P1",
    "final_level_p2": "Final level at P2", "peak_level": "Peak level", "final_volume": "Water stored at the end",
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
    if metric == "expected_state_error":
        return STATE_LABELS.get(c["id"], c["id"].replace("_", " ").capitalize())
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


def _margin_span(ck: dict) -> str:
    t = review.margin_text(ck.get("margin"))
    if ck.get("state") == "info":
        t = t.replace("the limit", "the guide")
    return f' · <span class="mg">{esc(t)}</span>' if t else ""


def checks_for(m: dict, card: dict) -> list[dict]:
    """Every check of one run in plain words: label, value, limit, ok."""
    defs = {c["id"]: c for c in m["scoring"]["criteria"]}
    out = []
    for r in card.get("criteria_results", []):
        d = defs.get(r["id"], r)
        d = {**d, "threshold": r.get("threshold", d.get("threshold", {}))}
        mg = method_v2.margin(r.get("observed"), d.get("threshold") or {})
        ok = bool(r.get("passed"))
        gating = bool(r.get("gating", True))
        out.append(dict(label=check_label(d), value=check_value(d, r.get("observed")),
                        limit=check_limit(d) if gating else f"reported, not judged · {check_limit(d).replace('allowed', 'guide')}",
                        ok=ok, state="ok" if ok else ("no" if gating else "info"), gating=gating, margin=mg))
    conv = card.get("convergence_result") or {}
    if conv.get("errors"):
        cv = (card.get("_judged") or method_v2.assess(card))["converges"]
        p, ci, v = cv.get("order"), cv.get("ci"), cv["verdict"]
        value = (f"rate {p:.2f}" + (f" (90 % range {ci[0]:.2f} to {ci[1]:.2f})" if ci else "")).replace("-", "−") if p is not None else "no rate"
        need = f"needed: {nice(cv.get('min'), 2)} or better across the whole range"
        if v == "at_floor":
            need = "at the solver's own precision: reported, not judged"
        state = {"pass": "ok", "at_floor": "ok", "fail": "no"}.get(v, "unsure")
        out.append(dict(label="Improves with finer grids", value=value, limit=need, ok=state == "ok", state=state, gating=True))
    return out


def summary_line(m: dict, card: dict) -> str:
    """One plain sentence for the results panel."""
    parts = []
    for c in checks_for(m, card):
        parts.append(f"{c['label']}: {c['value']} ({c['limit']})")
    return ". ".join(parts) + "."


# Findings worth a sentence on a model card: (short id, solver key) -> text
NOTES = {
    ("A1F-010", "telemac"): "Passes: the front is 5.8 m behind the exact one (9.8 m allowed) and depths are within 1.4 mm on average. It is not verified: the error shrinks on finer grids at a rate of 0.69 (90 % range 0.64 to 0.73), all of it under the 0.8 required. The thin leading edge, 1 mm deep, lags further (39 m): it stays dry too long. HLLC and second-order settings did not change that.",
    ("A1F-001", "hecras"): "HEC-RAS stores input elevations to the nearest 0.001 ft (0.3 mm), even in a metric project. The depth error therefore stops at about 0.1 mm on every grid, a hundredth of the limit, and cannot shrink with the grid. It passes; the convergence rate is reported but, at the solver's own precision, not judged, so it is verified.",
    ("A1F-010", "hecras"): "The flood advances as a steep bore and its front is 97 m behind the exact one; the error does not fall on finer grids. HEC-RAS 2D was built and run with no GUI step; the dam-break step was carried in by a restart file.",
    ("A1F-010", "hecras-em"): "SWE-EM, the option HEC recommends for dam breaks, gets 40 m closer than the default SWE-ELM (58 m behind) but does not converge.",
    ("A1F-011", "hecras"): "The bore is in about the right place (depth error 5 mm), but the error does not fall on finer grids.",
    ("A1F-011", "hecras-em"): "Error 8 mm, inside the limit, but it grows slightly on finer grids.",
    ("A1F-010", "swmm524"): "SWMM's dynamic-wave routing is built for sewer networks, not dam breaks: the front is 41 m behind and the error does not shrink on finer grids. One conduit near x = 1,126 m also spikes to a 9 m depth at the reporting time (the chart clips it); that is the engine's own output, not a plotting fault.",
    ("A1F-011", "swmm524"): "The bore smears and lags, and the stored water drifts 4 % above the exact volume: dynamic-wave routing is not built for moving shocks.",
    ("A1F-010", "openswmm-dw"): "Identical, number for number, to EPA SWMM 5.2.4: OpenSWMM 6 keeps the original dynamic-wave solver, including the 9 m one-conduit spike near x = 1,126 m.",
    ("A1F-011", "openswmm-dw"): "Identical, number for number, to EPA SWMM 5.2.4: OpenSWMM 6 keeps the original dynamic-wave solver.",
    ("A1F-001", "openswmm-dw"): "Identical, number for number, to EPA SWMM 5.2.4.",
    ("A1F-011", "openswmm-fv"): "OpenSWMM 6's new finite-volume routing is 1 mm from the exact answer where SWMM's dynamic wave is 37 mm off. It passes. Its convergence rate is 0.87, but its 90 % range (0.79 to 0.95) dips just below the 0.8 required, so on these four grids it is not yet verified.",
    ("A1F-010", "openswmm-fv"): "Passes, where dynamic wave fails: 3.3 m behind instead of 41 m, and it conserves water. It is not verified: the error shrinks at a rate of 0.66 (90 % range 0.54 to 0.77), under the 0.8 required.",
    ("A1F-001", "openswmm-fv"): "Passes: 0.4 mm. Not verified: its convergence rate fitted through the four grids is 0.79, with a 90 % range of 0.73 to 0.85 that includes the 0.8 required, so these grids cannot settle whether it converges. Dynamic wave reaches 1.8.",
    ("B-RTC-001", "openswmm6"): "Pumps switch the same 74 times, but one node peaks 50 % higher than in SWMM 5.2.4, at a different time; worth a look by the OpenSWMM developers.",
    ("A1F-010", "lisflood-acc"): "The local-inertia scheme leaves out the advection term, so it is not expected to get a dam break right; it is shown because it is what most LISFLOOD-FP users run.",
    ("A1F-011", "lisflood-acc"): "The local-inertia scheme leaves out the advection term, so it cannot form the right bore; it is shown because it is what most LISFLOOD-FP users run.",
    ("A2C-EA1", "lisflood-acc"): "The pond settles 5 mm above the sill (2 cm allowed). The stored volume is 2.7 % above the figure integrated on the EA's 2 m DEM; that check does not gate, because a 10 m grid samples the ground differently.",
    ("A2C-EA4", "lisflood-fv1"): "Run at the specification's 5 m grid (the demo solver uses the allowed 10 m alternative). The inflow enters as LISFLOOD-FP point sources on the cells the inflow line crosses.",
    ("A2A-020", "telemac"): "Run with TELEMAC's HLLC scheme: its default kinetic scheme goes unstable with this supercritical inflow. The depth is right (1 cm) and converges, but the stored water is 0.15 % above exact (0.1 % allowed), as with ANUGA (0.13 % below).",
    ("A2A-010", "telemac"): "Passes: 0.13 mm from the exact water level, converging at first order. The inflow discharge and outlet level are listed in the order TELEMAC numbers its open boundaries.",
    ("A2C-EA2", "telemac"): "Run with a 1 s largest step, as for the other codes: with TELEMAC's step left to the 5-minute output interval, the dry start took long first steps that undersampled the inflow and lost 6 % of the water.",
    ("A2A-010", "hecras"): "Very accurate (0.09 mm), but the error stops falling below about 0.1 mm on finer grids (0.54, 0.16, 0.12, 0.09 mm), so it passes but its convergence rate's range is wide (0.11 to 1.50): not verified. HEC-RAS stops iterating at its default water-surface tolerance (0.01), which is the likely floor.",
    ("A2A-010", "hecras-em"): "As SWE-ELM: 0.06 mm, but the error levels off near 0.1 mm on finer grids (rate 1.02, 90 % range 0.43 to 1.60): passes, not verified.",
    ("A2C-EA1", "hecras"): "Run on the EA's own 2 m DEM, which HEC-RAS uses as sub-grid terrain. The pond settles 1.3 cm above the sill (2 cm allowed).",
    ("A2C-EA2", "hecras"): "HEC-RAS's own volume accounting reports 1.4 % more water stored than flowed in (98,576 m³ from 97,194 m³). Integrating its water levels over the 2 m DEM gives +0.76 %, also over the limit. Run on the EA's own 2 m DEM as sub-grid terrain.",
    ("A2C-EA2", "hecras-em"): "As SWE-ELM: HEC-RAS's own accounting shows a 1.4 % volume error.",
    ("A1F-010", "hydronet-fvm"): "The dam never breaks: no water crosses onto the dry bed. HydroNet's Roe residual uses a fixed 1 cm dry threshold and, at a face between a wet and a dry cell, the wet cell's own flux, so still water next to dry ground feels no net force. The same happens below a 1 cm downstream layer. Mass is conserved because nothing moves.",
    ("A1F-011", "hydronet-fvm"): "Into 10 cm of water the dam break runs normally: depth error 1.4 mm (passes) and mass 0.016 %, but the error falls at a rate of 0.70 (90 % range 0.68 to 0.72; minimum 0.8).",
    ("A1F-011", "hydronet-pinn"): "The trained network smears the bore and the rarefaction: average depth error 12.6 cm (1 cm allowed), 4.5 % of the water lost, and no improvement on finer grids. Trained with the recipe of HydroNet's own dam-break example, which on its own 20 m, 1 s case gives an RMS error of 6 cm on a 2 m dam (3 %); this case is 2 km over 30 s.",
    ("A1D-001", "openswmm-fv"): "Accurate mid-line (under 2 mm), but up to 1.4 cm too deep in the pipes next to the normal-depth outfalls and 7 mm too deep in the first pipes below the inflows. EPA SWMM 5.2.4 holds normal depth to 0.3 mm everywhere.",
    ("A1D-002", "openswmm-fv"): "The pipes are surcharged and the finite-volume routing overestimates the friction loss: the hydraulic grade line falls 1.42 m over the five pipes instead of 1.19 m (19 % more), so the upstream manholes stand up to 28 cm too high. Dynamic wave in the same engine is 0.4 mm from exact.",
    ("A1D-001", "hydra-uds"): "Exact to rounding (0.0005 mm): Hydra computes the circular section exactly, where the SWMM engines interpolate a 51-entry table (0.27 mm off).",
    ("A1D-005", "openswmm-fv"): "Passes (3.7 mm). With one cell per pipe (FV_MIN_CELLS 1, as on the channel tests) it is 2.2 cm off and fails; the default subdivides each pipe.",
    ("A1F-041", "anuga"): "Passes, within 0.7 mm with the SWASHES downstream condition (0.66 m held while the outflow is subcritical); not verified only because three grids leave its convergence rate's range wide (0.69 to 1.14). With a free (transmissive) outflow instead, ANUGA settled on a fully subcritical state 1.06 m deep, 0.39 m off.",
    ("A1F-043", "anuga"): "Nothing moves (velocities 1e-14 m/s). The worst depth difference, 1.7 mm, is in the cells cut by the shoreline, where a cell-mean depth on the sloping bump differs from the exact depth at the cell centre; that check is informational.",
    ("A12-010", "swmm-anuga"): "The street carries exactly what the manhole releases (0.5 m³/s, depth 0.1 mm from exact), but 5 m³ of the 885 m³ is missing at the end (0.56 %; 0.5 % allowed). The coupler moves water exactly; the loss is SWMM's own continuity error (0.50 % in its report), made as the dead-end pipe filled and surcharged.",
    ("A12-011", "swmm-anuga"): "Passes. While the pipe runs full, SWMM's reported pipe and manhole volumes exceed its own balance by up to 3.1 m³ (1.2 %), which disappears as the pipe empties: its end-of-run continuity error is 0.000 %.",
    ("A12-012", "swmm-anuga"): "Passes: 180.05 m³ out of 180 m³ in. As in A12-011, SWMM's reported storage is off by up to 2.4 m³ while surcharged, and back to balance once the pipes drain.",
    ("A12-010", "openswmm-2d"): "Passes, with OpenSWMM's own coupling and defaults: the manhole passes 0.503 m³/s onto the street (0.5 exact), the street runs 0.6 mm from normal depth, and the water balances to 0.01 m³ of 900 m³.",
    ("A12-010", "openswmm-2d-x"): "Same exchange and balance as on the two-triangle mesh, but with each square cut into four triangles the street runs 85.7 mm deep instead of 77.7 mm (3 mm allowed). The same model on the simpler two-triangle mesh is 0.6 mm off: the sheet flow depends on how the grid is triangulated.",
    ("A12-011", "openswmm-2d"): "The yard drains 12 mm below the 5 cm gully crest, so 4 % too much leaves by the outfall. OpenSWMM's exchange is meant to close at the crest, and a still pond 1 cm below it does not drain, but here it kept draining at 0.035–0.045 m³/s for about ten minutes while both the surface and the manhole head were below the crest. The 1.5 m³ missing from the balance is the network's own continuity error (0.62 % in its report).",
    ("A12-011", "openswmm-2d-x"): "As on the two-triangle mesh: the yard drains 14 mm below the crest and 5 % too much leaves by the outfall; the exchange keeps running below the crest while the yard drains. The balance passes (0.31 % short, the network's own continuity error).",
    ("A12-012", "openswmm-2d"): "Passes: 110 m³ surges onto the surface and drains back; 179.6 of the 180 m³ leaves by the outfall and 0.4 m³ stays on the slope. The balance closes to 0.03 m³.",
    ("A12-012", "openswmm-2d-x"): "Passes, as on the two-triangle mesh: 179.6 m³ out, 0.4 m³ left on the slope, balance within 0.03 m³.",
    ("A1F-010", "hydronet-pinn"): "The trained network spreads 0.3–0.4 m of water over the whole dry channel downstream, so its front is 713 m ahead of the exact one; it gains 3.3 % of the water, and the error grows on finer grids. Its own finite-volume engine, by contrast, never starts the flow.",
}
CASE_NOTES = {
    "A1F-040": "The SWMM dynamic-wave engines (EPA SWMM 5.2.4, OpenSWMM v6 dynamic wave and Hydra) never settle on this frictionless channel with 10 and 5 cm conduits, even with a 0.0025 s routing step: depths swing by more than a metre. On 20 cm conduits SWMM 5.2.4 is within 8 mm on the subcritical case. OpenSWMM v6's finite-volume routing passes all four bump tests.",
    "A1F-041": "The SWMM dynamic-wave engines (EPA SWMM 5.2.4, OpenSWMM v6 dynamic wave and Hydra) never settle on this frictionless channel with 10 and 5 cm conduits, even with a 0.0025 s routing step: depths swing by more than a metre. On 20 cm conduits SWMM 5.2.4 is within 8 mm on the subcritical case. OpenSWMM v6's finite-volume routing passes all four bump tests.",
    "A1F-042": "The SWMM dynamic-wave engines (EPA SWMM 5.2.4, OpenSWMM v6 dynamic wave and Hydra) never settle on this frictionless channel with 10 and 5 cm conduits, even with a 0.0025 s routing step: depths swing by more than a metre. On 20 cm conduits SWMM 5.2.4 is within 8 mm on the subcritical case. OpenSWMM v6's finite-volume routing passes all four bump tests.",
    "A1F-043": "Every code that ran keeps the lake still except Hydra (currents up to 0.12 m/s). The SWMM engines needed a routing step matched to the grid: SWMM's variable step follows the flow velocity, so in still water it stays at the routing step, and with a 1 s step on 20 cm conduits a lake on a 0.4 % slope starts sloshing at 1.3 m/s.",
    "A1F-010": "Since version 2 the front is measured by volume: the point beyond which the last 5 % of the released water lies. Version 1 used the 1 mm depth contour, which every production code failed by 12 to 211 m: on the thin tip a millimetre of depth moves that contour about 10 m, and production codes treat water shallower than about 1 mm as dry. The 1 mm edge is still reported, but no longer decides the result.",
}


# ── layout ──────────────────────────────────────────────────────────────────

NAV = [("results.html", "Tests &amp; results"), ("viewer.html", "Viewer"), ("score.html", "Score your model"), ("how-it-works.html", "How it works")]
FOOT = [("news.html", "What's new"), ("solvers.html", "Models"), ("compare.html", "Compare models"), ("viewer.html", "Results viewer"), ("corpus.html", "SWMM corpus"), ("reports.html", "Reports and audit"), ("downloads.html", "Downloads"),
        ("method.html", "Method"), ("get-started.html", "Command line")]
LOGO = ('<svg viewBox="0 0 34 22" aria-hidden="true"><path class="w" d="M1 8 C7 2 11 14 17 8 S27 2 33 8" fill="none" stroke-width="3" stroke-linecap="round"/>'
        '<path class="b" d="M1 18 H33" stroke-width="3" stroke-linecap="round"/></svg>')


def layout(title: str, body: str, active: str, depth: int = 0, description: str = "", scripts: str = "", math: bool = False,
           og_image: str = "assets/og/home.png", path: str = "") -> str:
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
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description or 'Open benchmarks for flood, river, drainage and water-network models. Every test has a known right answer.')}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}{esc(path or active)}">
<meta property="og:image" content="{SITE_URL}{esc(og_image)}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/atom+xml" title="{SITE_NAME}: what's new" href="{up}feed.xml">
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


VERDICT_BADGE = {"pass": '<span class="badge pass">✓ Passes</span>', "fail": '<span class="badge fail">✗ Fails</span>',
                 "inconclusive": '<span class="badge unsure">? Inconclusive</span>'}
VERDICT_WORD = {"pass": "passes", "fail": "fails", "inconclusive": "inconclusive"}
SYM = {"ok": "✓", "no": "✗", "unsure": "?", "info": "·"}


def two_verdicts(card: dict) -> str:
    """Method 2's two verdicts, when the test has a grid study (otherwise accuracy is the verdict)."""
    a = card.get("_judged") or method_v2.assess(card)
    cv = a["converges"]["verdict"]
    if cv == "n/a":
        return ""
    acc = '<span class="ok">✓ yes</span>' if a["accurate"] == "pass" else '<span class="no">✗ no</span>'
    con = {"pass": '<span class="ok">✓ yes</span>', "fail": '<span class="no">✗ no</span>',
           "inconclusive": '<span class="unsure">? not settled by these grids</span>',
           "at_floor": '<span class="ok">at its own precision</span>'}[cv]
    ver = ('<span class="ok">✓ verified</span>' if a.get("verified") else '<span class="muted">not verified</span>') if a["accurate"] == "pass" else ""
    return f'<p class="two-verdicts small"><span>Accurate: {acc}</span><span>Converges: {con}</span>{f"<span>{ver}</span>" if ver else ""}</p>'


def verdict(card: dict | None) -> str:
    """pass, fail or inconclusive (scoring method 2; docs/methodology/scoring_v2.md)."""
    if not card:
        return "none"
    return card.get("verdict") or ("pass" if card.get("passed") else "fail")


def badge(card: dict | None) -> str:
    if card is None:
        return '<span class="badge none">Not run</span>'
    return VERDICT_BADGE[verdict(card)]


SOLVER_DOCS = {"hecras": "hecras.md", "hecras-em": "hecras.md", "openswmm-dw": "openswmm.md", "openswmm-fv": "openswmm.md",
               "openswmm6": "openswmm.md", "hydra-uds": "hydra.md", "hydra-wds": "hydra.md", "hydronet-fvm": "hydronet.md",
               "hydronet-pinn": "hydronet.md", "swmm-anuga": "coupled.md",
               "openswmm-2d": "coupled.md", "openswmm-2d-x": "coupled.md"}
KIND_WORDS = {"production": "Production software, run by the suite as a black box with its own default settings.",
              "research": "Research code, run with the settings of its own examples.",
              "suite": "A worked example that ships with the suite.",
              "compat": "Scored for compatibility with the current release, not for physics.",
              "submitted": "Run by others and submitted as results files; scored by the suite with the same limits as every other run."}


def solver_page(key: str, manifests: list[dict], runs: dict) -> str:
    """One model: every test it ran, with the checks and the notes."""
    s = SOLVER[key]
    mine = [(m, runs[m["test_id"]][key]) for m in manifests if key in (runs.get(m["test_id"]) or {})]
    n_pass = sum(1 for _, c in mine if c.get("passed"))
    versions = sorted({(c.get("solver") or {}).get("name", "") for _, c in mine})
    rows = []
    for m, c in mine:
        sid = sid_of(m["test_id"])
        checks = "; ".join(f'{SYM[ck["state"]]} {ck["label"]} {ck["value"]}' for ck in checks_for(m, c) if ck.get("gating", True))
        note = NOTES.get((sid, key), "")
        rows.append(f'<tr><td><a href="../tests/{sid}.html#m-{key}"><b>{esc(story(m)["name"])}</b></a><div class="muted small">{esc(sid)}</div></td>'
                    f'<td>{badge(c)}</td><td class="small">{esc(checks)}{("<p class=note>" + esc(note) + "</p>") if note else ""}</td></tr>')
    doc = SOLVER_DOCS.get(key)
    doc_link = f'<p><a href="{REPO_URL}/blob/master/docs/{doc}">How it is run, and what was found →</a></p>' if doc else ""
    body = f"""<div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="../solvers.html">Models</a> / {esc(s['name'])}</nav>
<section class="page-head">
  <h1><span class="sw" style="background:{s['color']}"></span>{esc(s['name'])} <small class="muted">{esc(s['sub'])}</small></h1>
  <p class="lede">{esc(s['what'])}.</p>
  <p class="muted">{esc(KIND_WORDS.get(s['kind'], ''))} Passes <b>{n_pass} of {len(mine)}</b> tests it ran. Score cards from: {esc(', '.join(versions))}.</p>
  {doc_link}
  <p><a href="../compare.html?a={esc(key)}">Compare {esc(s['name'])} with another model →</a></p>
</section>
<section class="section"><div class="table-scroll"><table class="data"><thead><tr><th>Test</th><th>Result</th><th>Checks that decide the result</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></section>
</div>"""
    return layout(s["name"] + " " + s["sub"], body, "solvers.html", depth=1, description=f"Every benchmark result for {s['name']} ({s['sub']}).")


def compare_page(manifests: list[dict], runs: dict) -> str:
    """Two models side by side, test by test."""
    keys = SOLVERS_ORDER({k for v in runs.values() for k in v})
    models = [dict(key=k, name=series_label(k, keys) if SOLVER[k]["name"] in {SOLVER[o]["name"] for o in keys if o != k} else SOLVER[k]["name"],
                   sub=SOLVER[k]["sub"], color=SOLVER[k]["color"], kind=SOLVER[k]["kind"]) for k in keys]
    for mm in models:
        mm["full"] = mm["name"] if mm["sub"].split("·")[-1].strip() in mm["name"] else f'{mm["name"]} · {mm["sub"]}'
    tests = []
    for gkey, gname in GROUPS.items():
        for m in manifests:
            if story(m)["group"] != gkey or not runs.get(m["test_id"]):
                continue
            sid = sid_of(m["test_id"])
            res = {}
            for k, c in runs[m["test_id"]].items():
                res[k] = dict(p=verdict(c) == "pass", v=verdict(c), c=[[ck["label"], ck["value"], ck["state"]] for ck in checks_for(m, c) if ck.get("gating", True)],
                              n=NOTES.get((sid, k), ""))
            tests.append(dict(sid=sid, name=story(m)["name"], group=gname, r=res))
    data = dict(models=models, tests=tests)
    opts = "".join(f'<option value="{esc(mm["key"])}">{esc(mm["full"])}</option>' for mm in models)
    body = f"""<div class="wrap">
<section class="page-head">
  <h1>Compare two models</h1>
  <p class="lede">Pick two models to see, test by test, where they agree and where they part ways.</p>
</section>
<div class="cmp-pick">
  <label>Model A<select id="cmp-a">{opts}</select></label>
  <span class="vs" aria-hidden="true">vs</span>
  <label>Model B<select id="cmp-b">{opts}</select></label>
  <button type="button" class="pill" id="cmp-swap">Swap</button>
</div>
<div id="cmp-summary" class="cmp-summary" aria-live="polite"></div>
<div class="table-scroll"><table class="data cmp" id="cmp-table"><thead><tr><th>Test</th><th id="cmp-ha">A</th><th id="cmp-hb">B</th></tr></thead><tbody></tbody></table></div>
<p class="small" id="cmp-only"></p>
</div>
{json_script("cmp-data", data)}"""
    script = """<script>
(function(){var D=JSON.parse(document.getElementById('cmp-data').textContent),A=document.getElementById('cmp-a'),B=document.getElementById('cmp-b');
var M={};D.models.forEach(function(m){M[m.key]=m;});
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
var q=new URLSearchParams(location.search);A.value=M[q.get('a')]?q.get('a'):(M['swmm524']?'swmm524':D.models[0].key);
B.value=M[q.get('b')]?q.get('b'):(M['openswmm-fv']?'openswmm-fv':D.models[1].key);
function cell(r,m){var dm=' data-m="'+esc(m)+'"';if(!r)return '<td class="muted"'+dm+'>not run</td>';var h='<td'+dm+'>'+({pass:'<span class="badge pass">✓ Passes</span>',fail:'<span class="badge fail">✗ Fails</span>',inconclusive:'<span class="badge unsure">? Inconclusive</span>'})[r.v]+'<ul class="cmp-checks">';
r.c.forEach(function(c){h+='<li class="'+c[2]+'">'+({ok:'✓ ',no:'✗ ',unsure:'? '})[c[2]]+esc(c[0])+': '+esc(c[1])+'</li>';});return h+'</ul></td>';}
function draw(){var a=A.value,b=B.value,both=[],onlyA=0,onlyB=0,s={bp:0,ap:0,bpo:0,bf:0};
history.replaceState(null,'','?a='+encodeURIComponent(a)+'&b='+encodeURIComponent(b));
document.getElementById('cmp-ha').textContent=M[a].full;document.getElementById('cmp-hb').textContent=M[b].full;
D.tests.forEach(function(t){var ra=t.r[a],rb=t.r[b];if(ra&&rb){both.push(t);if(ra.p&&rb.p)s.bp++;else if(ra.p)s.ap++;else if(rb.p)s.bpo++;else s.bf++;}else if(ra)onlyA++;else if(rb)onlyB++;});
both.sort(function(x,y){var dx=x.r[a].v!==x.r[b].v?0:1,dy=y.r[a].v!==y.r[b].v?0:1;return dx-dy;});
var rows='';both.forEach(function(t){var diff=t.r[a].v!==t.r[b].v;rows+='<tr'+(diff?' class="cmp-diff"':'')+'><th scope="row"><a href="tests/'+esc(t.sid)+'.html">'+esc(t.name)+'</a><small>'+esc(t.sid)+' · '+esc(t.group)+'</small></th>'+cell(t.r[a],M[a].name)+cell(t.r[b],M[b].name)+'</tr>';});
document.querySelector('#cmp-table tbody').innerHTML=rows||'<tr><td colspan="3">These two models have no test in common yet.</td></tr>';
var n=both.length;document.getElementById('cmp-summary').innerHTML=n?('<div><b>'+n+'</b><span>tests both ran</span></div><div><b>'+s.bp+'</b><span>both pass</span></div><div class="hl"><b>'+s.ap+'</b><span>only '+esc(M[a].name)+' passes</span></div><div class="hl"><b>'+s.bpo+'</b><span>only '+esc(M[b].name)+' passes</span></div><div><b>'+s.bf+'</b><span>neither passes</span></div>'):'';
document.getElementById('cmp-only').textContent=(onlyA||onlyB)?('Not compared: '+onlyA+' test(s) only '+M[a].name+' ran, '+onlyB+' only '+M[b].name+' ran.'):'';}
A.addEventListener('change',draw);B.addEventListener('change',draw);
document.getElementById('cmp-swap').addEventListener('click',function(){var t=A.value;A.value=B.value;B.value=t;draw();});draw();})();
</script>"""
    return layout("Compare two models", body, "solvers.html", scripts=script, description="Two benchmark models side by side, test by test.")


def solvers_index(manifests: list[dict], runs: dict) -> str:
    keys = SOLVERS_ORDER({k for v in runs.values() for k in v})
    groups = [("production", "Production software"), ("submitted", "Submitted results"), ("research", "Research codes"),
              ("suite", "Worked examples"), ("compat", "Compatibility")]
    out = []
    for kind, title in groups:
        ks = [k for k in keys if SOLVER[k]["kind"] == kind]
        if not ks:
            continue
        lis = []
        for k in ks:
            cards = [runs[m["test_id"]][k] for m in manifests if k in (runs.get(m["test_id"]) or {})]
            lis.append(f'<li><a href="solvers/{k}.html"><span class="sw" style="background:{SOLVER[k]["color"]}"></span><b>{esc(SOLVER[k]["name"])}</b> '
                       f'<span class="muted">{esc(SOLVER[k]["sub"])}</span></a> — passes {sum(1 for c in cards if c.get("passed"))} of {len(cards)}</li>')
        out.append(f'<section class="section"><h2>{title}</h2><p class="muted">{esc(KIND_WORDS[kind])}</p><ul class="waitlist">{"".join(lis)}</ul></section>')
    body = f"""<div class="wrap"><section class="page-head"><h1>Models</h1>
<p class="lede">Every model scored on the benchmark, with all of its results on one page. <a href="compare.html">Compare two models side by side →</a></p></section>{''.join(out)}</div>"""
    return layout("Models", body, "solvers.html", description="Every model scored on the benchmark.")


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
        lim = 9.8
        for mm in manifests:
            if mm["test_id"].startswith("A1F-010"):
                lim = next((float(c["threshold"]["value"]) for c in mm["scoring"]["criteria"] if c["id"] == "volume_front"), lim)
        ok = sorted((k for k, v in fronts.items() if v <= lim), key=lambda k: fronts[k])
        far = sorted(v for v in fronts.values() if v > lim)
        who = ", ".join(dict.fromkeys(SOLVER[k]["name"].split(" ")[0] for k in ok)) or "none"
        cards.append(f"""<a class="finding" href="tests/A1F-010.html">
  <div class="num">{len(ok)} of {len(fronts)}</div>
  <b>The dam-break front splits the field</b>
  <p>In the classic dam break, {len(ok)} of {len(fronts)} production runs put the flood front within {nice(lim, 2)} m of the exact one after a minute ({esc(who)}: {nice(min(fronts[k] for k in ok), 2) if ok else '–'}–{nice(max(fronts[k] for k in ok), 2) if ok else '–'} m). The other {len(far)} are {nice(far[0], 2) if far else '–'}–{nice(far[-1], 3) if far else '–'} m behind.</p>
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
    by_sid = {sid_of(m["test_id"]): m for m in manifests}
    featured = ["A1F-010", "A2C-EA4", "A1F-042", "A1D-002", "A12-012", "A1P-020", "B-RTC-001"]
    tcards = "".join(test_card(by_sid[s_], runs) for s_ in featured if s_ in by_sid)
    n_live = sum(1 for m in manifests if m["status"] != "draft")
    tcards += (f'<a class="card more-card" href="results.html"><div><b>{n_live}</b><span>tests with a known right answer</span></div>'
               f'<div class="more-groups">{"".join(f"<span>{esc(v)}</span>" for v in GROUPS.values())}</div>'
               f'<span class="more-link">Browse every test →</span></a>')
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
  <div class="head-row"><div><h2>Tests built from real engineering questions</h2>
  <p class="muted" style="margin:0">Each one isolates something a model has to get right on a real project, from a sewer pipe running full to a dam failing above a city.</p></div>
  <a href="results.html" style="font-weight:600">All {n_live} tests →</a></div>
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


def test_card(m: dict, runs: dict, up: str = "", status_text: str | None = None) -> str:
    """A tile for one test: picture, topic, question and how the models did."""
    sid = sid_of(m["test_id"])
    st = story(m)
    by = runs.get(m["test_id"]) or {}
    scored = [k for k in by if SOLVER.get(k, {}).get("kind") != "compat" or m["track"] == "B"]
    n_ok = sum(1 for k in scored if verdict(by[k]) == "pass")
    n_un = sum(1 for k in scored if verdict(by[k]) == "inconclusive")
    if status_text:
        score = f'<div class="tc-score">{esc(status_text)}</div>'
    elif scored:
        n = len(scored)
        score = (f'<div class="tc-score"><div class="tc-bar" aria-hidden="true"><i class="p" style="width:{100 * n_ok / n:.1f}%"></i>'
                 f'<i class="u" style="width:{100 * n_un / n:.1f}%"></i>'
                 f'<i class="f" style="width:{100 * (n - n_ok - n_un) / n:.1f}%"></i></div>'
                 f'<span>{n_ok} of {n} model{"s" if n != 1 else ""} pass{f" · {n_un} inconclusive" if n_un else ""}</span></div>')
    else:
        score = '<div class="tc-score">Not run yet</div>'
    return (f'<a class="card test-card" href="{up}tests/{sid}.html" data-group="{st["group"]}">{tile_svg(sid)}'
            f'<div class="body"><div class="tc-kick"><span>{esc(GROUPS.get(st["group"], ""))}</span><span>{esc(sid)}</span></div>'
            f'<h3>{esc(st["name"])}</h3><p>{esc(st["question"])}</p>{score}</div></a>')


def _short_need(text: str) -> str:
    t = text.split(";")[0].split(" (")[0].strip()
    return t if len(t) <= 70 else t[:68].rsplit(" ", 1)[0] + "…"


def _holder(m: dict) -> str:
    """Who holds the missing data, from the first pending input or the reference."""
    for e in m["inputs"]:
        if e.get("pending"):
            return e["pending"].get("obtain_from", "")
    return (m.get("reference") or {}).get("obtain_from", "")


def in_preparation(drafts: list[dict]) -> str:
    """The tests defined but waiting on data: what is missing and who holds it."""
    if not drafts:
        return ""
    items = []
    for m in drafts:
        sid = sid_of(m["test_id"])
        holder = _holder(m)
        items.append(f'<li class="prep-item"><a href="tests/{sid}.html"><b>{esc(story(m)["name"])}</b></a> <span class="muted small">{esc(sid)}</span>'
                     f'<div class="small">Missing: {esc(_need(m))}.</div>'
                     + (f'<div class="small muted">Held by: {esc(holder)}</div>' if holder else "") + "</li>")
    return f"""<section class="tile-group prep" data-group="prep" id="in-preparation">
  <h3>In preparation: {len(drafts)} tests waiting on data</h3>
  <p class="muted">Defined, with their physics, inputs and scoring written, but each needs measurements or geometry that its owners have to release. If you hold one of these datasets, or know who does, <a href="{REPO_URL}/issues/new?title=Data%20for%20a%20test%20in%20preparation">tell us</a>.</p>
  <ul class="prep-list">{''.join(items)}</ul>
</section>"""


def test_gallery(manifests: list[dict], runs: dict, drafts_need=None) -> str:
    """Every test as a tile, grouped by topic."""
    out = []
    for gkey, gname in GROUPS.items():
        ms = [m for m in manifests if story(m)["group"] == gkey]
        if not ms:
            continue
        cards = "".join(test_card(m, runs, status_text=("Waiting on data: " + _short_need(drafts_need(m)) if m["status"] == "draft"
                                                         and not runs.get(m["test_id"]) and drafts_need else None)) for m in ms)
        out.append(f'<section class="tile-group" data-group="{gkey}"><h3>{esc(gname)}</h3><p class="muted">{esc(GROUP_BLURBS.get(gkey, ""))}</p>'
                   f'<div class="grid narrow">{cards}</div></section>')
    return "".join(out)


def SOLVERS_ORDER(keys) -> list[str]:
    return [s["key"] for s in SOLVERS if s["key"] in keys]


# ── tests and results ───────────────────────────────────────────────────────


def results_page(manifests: list[dict], runs: dict, parity, census) -> str:
    shown = [m for m in manifests if m["status"] != "draft" or runs.get(m["test_id"])]
    drafts = [m for m in manifests if m not in shown]
    cols = SOLVERS_ORDER({k for m in shown for k in (runs.get(m["test_id"]) or {})})
    head = "".join(f'<th scope="col"><a href="solvers/{k}.html">{esc(SOLVER[k]["name"])}</a><small>{esc(SOLVER[k]["sub"])}</small></th>' for k in cols)
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
                v = verdict(c)
                cells[cid] = dict(test=st["name"], sid=sid, solver=f'{SOLVER[k]["name"]} · {SOLVER[k]["sub"]}', verdict=v,
                                  checks=checks_for(m, c), note=NOTES.get((sid, k), ""))
                label = f'{st["name"]}, {SOLVER[k]["name"]} {SOLVER[k]["sub"]}: {VERDICT_WORD[v]}'
                cls = {"pass": "pass", "fail": "fail"}.get(v, "unsure")
                tds.append(f'<td><button type="button" class="cellbtn {cls}" data-cell="{esc(cid)}" aria-pressed="false" aria-label="{esc(label)}">{SYM[{"pass": "ok", "fail": "no"}.get(v, "unsure")]}</button></td>')
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
    labels = {"swmm-5.1.15": "SWMM 5.1.15", "openswmm-6": "OpenSWMM Engine v6", "openswmm-6-fv": "OpenSWMM v6 finite volume", "hydra": "Hydra 17"}
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
    wait = ""  # the tests waiting on data have their own section under the gallery (in_preparation)
    prod_list = ", ".join(SOLVER[k]["name"] + (" " + SOLVER[k]["sub"].split("·")[-1].strip() if k.startswith("lisflood") else "") for k in cols if SOLVER[k]["kind"] == "production")
    subs = [k for k in cols if SOLVER[k]["kind"] == "submitted"]
    if subs:
        items = "".join(
            f'<li><b>{esc(SOLVER[k]["name"])}</b> <span class="muted">{esc(SOLVER[k]["sub"])}</span>: '
            f'{sum(1 for m in shown if (runs.get(m["test_id"]) or {}).get(k, {}).get("passed"))} of '
            f'{sum(1 for m in shown if k in (runs.get(m["test_id"]) or {}))} tests pass</li>' for k in subs)
        submitted = f"""<div class="card" style="flex:1 1 340px;min-width:0">
  <h2 style="font-size:22px">Submitted results</h2>
  <p class="muted">Run by the solver's developer or user and submitted as results files; the suite scores them with the same limits as every other run.</p>
  <ul class="waitlist">{items}</ul>
  <p style="margin:12px 0 0"><a href="{REPO_URL}/blob/master/docs/submitting.md">Submit yours →</a></p>
</div>"""
    else:
        submitted = f"""<div class="card" style="flex:1 1 340px;min-width:0">
  <h2 style="font-size:22px">Submitted results</h2>
  <p class="muted">None yet. Commercial codes the suite cannot run itself (TUFLOW, MIKE, InfoWorks ICM, Flood Modeller and others) can be run by their developers or users, who submit the results files; the suite scores them with the same limits as everything here.</p>
  <p style="margin:12px 0 0"><a href="{REPO_URL}/blob/master/docs/submitting.md">How to submit results →</a></p>
</div>"""
    body = f"""
<div class="wrap">
<section class="page-head">
  <h1>Tests and results</h1>
  <p class="lede">Every model runs the same inputs against a known right answer. Click any result to see the numbers behind it.</p>
</section>
<div class="filters" role="group" aria-label="Filter tests">{filters}
  <div class="view-toggle" role="group" aria-label="View"><button type="button" data-view="cards" aria-pressed="true">Cards</button><button type="button" data-view="table" aria-pressed="false">Table</button></div>
</div>
<div id="view-cards">{test_gallery(shown, runs, _need)}{in_preparation(drafts)}</div>
<div id="view-table">
<aside class="card panel" aria-live="polite" id="panel">{panel}</aside>
<div class="matrix-wrap">
  <table class="matrix" id="matrix">
    <thead><tr><th scope="col" class="test-col">Test</th>{head}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
</div>
<p class="small" style="margin-top:14px;max-width:90ch">The demo solvers are simple worked examples that ship with the suite. {esc(prod_list)} are production software, each run as a black box with its own default settings. HydroNet is a research code (physics-informed machine learning), scored with the settings of its own examples. SWMM 5.1.15 and EPANET 2.0 are scored for compatibility with the current releases, not for physics. Columns marked <i>submitted by …</i> were run by others and scored here.</p>
<section class="section" style="display:flex;flex-wrap:wrap;gap:20px;align-items:stretch">{corpus}{wait}{submitted}</section>
</div>
{json_script("cells", cells)}"""
    script = """<script>
(function(){var data=JSON.parse(document.getElementById('cells').textContent),panel=document.getElementById('panel');
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function render(id){var c=data[id];if(!c)return;var h='<div class="kicker">Selected result</div><div class="title">'+esc(c.test)+'</div><div class="solver">'+esc(c.solver)+'</div>'+
({pass:'<span class="badge pass">✓ Passes</span>',fail:'<span class="badge fail">✗ Fails</span>',inconclusive:'<span class="badge unsure">? Inconclusive</span>'})[c.verdict]+'<ul class="checks">';
c.checks.forEach(function(k){var sy={ok:'✓',no:'✗',unsure:'?',info:'·'}[k.state],al={ok:'met',no:'not met',unsure:'not settled',info:'reported only'}[k.state];h+='<li><span class="'+k.state+'" aria-label="'+al+'">'+sy+'</span><span><b>'+esc(k.label)+':</b> '+esc(k.value)+' <span class="muted">('+esc(k.limit)+')</span></span></li>';});
h+='</ul>'+(c.note?'<p class="small">'+esc(c.note)+'</p>':'')+'<a href="tests/'+esc(c.sid)+'.html#m-'+esc(id.split('|')[1])+'" style="font-weight:600">Open the test →</a>'+
'<div class="legend-mini"><span><b class="ok">✓</b> passes every check</span><span><b class="no">✗</b> fails at least one check</span><span><b class="unsure">?</b> rate not settled by these grids</span><span><b style="color:#A7B4BC">—</b> not run yet</span></div>';
panel.innerHTML=h;var rc=panel.getBoundingClientRect();if(rc.top<60||rc.top>innerHeight-80)panel.scrollIntoView({behavior:'smooth',block:'start'});document.querySelectorAll('.cellbtn').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.cell===id?'true':'false');});}
document.querySelectorAll('.cellbtn').forEach(function(b){b.addEventListener('click',function(){render(b.dataset.cell);try{history.replaceState(null,'','#cell='+encodeURIComponent(b.dataset.cell));}catch(e){}});});
var first=document.querySelector('.cellbtn[data-cell="'+(%FIRST%)+'"]');if(first)first.setAttribute('aria-pressed','true');
document.querySelectorAll('[data-filter]').forEach(function(f){f.addEventListener('click',function(){var g=f.dataset.filter;
document.querySelectorAll('[data-filter]').forEach(function(o){o.setAttribute('aria-pressed',o===f?'true':'false');});
document.querySelectorAll('#matrix tbody tr, .tile-group').forEach(function(r){r.hidden=!(g==='all'||r.dataset.group===g);});});});
var vc=document.getElementById('view-cards'),vt=document.getElementById('view-table');
function view(v){vc.hidden=v!=='cards';vt.hidden=v!=='table';document.querySelectorAll('[data-view]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.view===v?'true':'false');});try{localStorage.setItem('ohb-view',v);}catch(e){}}
var saved=null;try{saved=localStorage.getItem('ohb-view');}catch(e){}
if(location.hash==='#table')saved='table';
var hc=decodeURIComponent(location.hash).match(/^#cell=(.+)$/);
if(hc&&data[hc[1]]){saved='table';setTimeout(function(){render(hc[1]);var b=document.querySelector('.cellbtn[data-cell="'+hc[1]+'"]');if(b)b.scrollIntoView({block:'center'});},0);}
view(saved==='table'?'table':'cards');
document.querySelectorAll('[data-view]').forEach(function(b){b.addEventListener('click',function(){view(b.dataset.view);});});})();
</script>""".replace("%FIRST%", json.dumps(first or ""))
    return layout("Tests and results", body, "results.html", scripts=script,
                  description="Which flood, river, drainage and network models pass which tests, and by how much.")


def _panel_html(c: dict | None) -> str:
    if not c:
        return ""
    checks = "".join(f'<li><span class="{k["state"]}" aria-label="{ {"ok": "met", "no": "not met", "unsure": "not settled", "info": "reported only"}[k["state"]] }">{SYM[k["state"]]}</span>'
                     f'<span><b>{esc(k["label"])}:</b> {esc(k["value"])} <span class="muted">({esc(k["limit"])})</span></span></li>' for k in c["checks"])
    return (f'<div class="kicker">Selected result</div><div class="title">{esc(c["test"])}</div><div class="solver">{esc(c["solver"])}</div>'
            f'{VERDICT_BADGE[c["verdict"]]}'
            f'<ul class="checks">{checks}</ul>' + (f'<p class="small">{esc(c["note"])}</p>' if c["note"] else "")
            + f'<a href="tests/{esc(c["sid"])}.html" style="font-weight:600">Open the test →</a>'
            '<div class="legend-mini"><span><b class="ok">✓</b> passes every check</span><span><b class="no">✗</b> fails at least one check</span>'
            '<span><b class="unsure">?</b> rate not settled by these grids</span>'
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
             "intercomparison": ("Benchmark with known end states", "blue"),
             "exact_states": ("Exact answer known", "blue"), "pinned_engine": ("Compared with a pinned engine", "blue")}.get(kind, (kind, ""))
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
    keys = [k for k in SOLVERS_ORDER(set(profiles)) if k in profiles]
    for k in keys:
        s = SOLVER[k]
        series.append(dict(key=k, label=series_label(k, keys), color=s["color"], x=profiles[k]["x"], y=profiles[k]["y"],
                           dots=s["kind"] == "suite", dx=profiles[k].get("dx"), hidden=far_off(m, runs.get(k))))
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
    data = dict(sid=sid, xlabel=spec["x"], ylabel=spec["y"], exact=exact, series=series, fronts=fronts, rescale=True,
                front=sid == "A1F-010" and bool(fronts), front_exact=front_exact, dam=(1000 if sid == "A1F-010" else 0 if sid == "A1F-011" else None))
    front_limit = next((float(c["threshold"]["value"]) for c in m["scoring"]["criteria"] if c.get("metric") == "volume_front_error"), None)
    data["front_limit"] = front_limit
    toggles = '<button type="button" class="pill" data-series="exact" aria-pressed="true"><span class="sw" style="background:var(--water)"></span>Exact answer</button>' if exact else ""
    for s in series:
        sw = f'<span class="sw dot" style="color:{s["color"]}"></span>' if s["dots"] else f'<span class="sw" style="background:{s["color"]}"></span>'
        on = "false" if (s["key"] == "lisflood-acc" and len(series) > 1) or s.get("hidden") else "true"
        toggles += f'<button type="button" class="pill" data-series="{s["key"]}" aria-pressed="{on}">{sw}{esc(s["label"])}</button>'
    hid = [x["label"] for x in series if x.get("hidden")]
    hidden_note = (f'<p class="small" style="margin:0 0 8px">Hidden at first because they are far off the exact answer: {esc(", ".join(hid))}. '
                   'Click a name to show it.</p>' if hid else "")
    replay = bool(exact and exact.get("frames"))
    t_end = float(m["simulation"]["t_end"])
    controls = ""
    if replay:
        controls = f"""<div class="controls">
  <button type="button" class="play" aria-label="Play"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg></button>
  <label>Time since the start<input type="range" class="scrub" min="0" max="{len(exact['times']) - 1}" step="1" value="{len(exact['times']) - 1}"></label>
  <div class="readout">Press play, or drag the slider, to watch the exact answer unfold. Models are compared at the end, t = {nice(t_end, 3)} s.</div>
</div>"""
    elif series:
        controls = '<div class="controls"><div class="readout"></div></div>'
    html_ = f"""<section class="replay" aria-label="Exact answer and model results">
  <div class="replay-top"><div class="toggles" role="group" aria-label="Show on the chart">{toggles}</div><div class="tlabel" aria-live="polite"></div></div>
  {hidden_note}
  <svg class="chart" viewBox="0 0 1000 380" role="img" aria-label="{esc(spec['y'])} against {esc(spec['x'].lower())}: exact answer and model results"></svg>
  {controls}
  {_data_script(data)}
</section>"""
    if front_exact is not None and fronts:
        # a close-up of the front: lags of a few metres are invisible on the whole channel
        ex_final = ({k: v for k, v in exact.items() if k not in ("frames", "times")} if exact else None)
        if ex_final and exact.get("frames"):
            ex_final["y"] = exact["frames"][-1]
        lo = front_exact - 4 * (front_limit or 10)
        close = dict(data, exact=ex_final, rescale=False, dam=None, front=True, front_marks=True,
                     xlim=[lo, front_exact + 3 * (front_limit or 10) + 40], ylim=[0, 0.16])
        html_ += f"""<section class="replay" aria-label="Close-up of the flood front">
  <h3 class="h3">Close-up of the front</h3>
  <p class="small muted" style="margin:0 0 8px">The last stretch of the flood, 15 times taller. The dashed line is the exact front (where the last 5 % of the released water begins), the shaded band the {nice(front_limit or 0, 2)} m allowed, and each triangle a model's front.</p>
  <div class="replay-top"><div class="toggles" role="group" aria-label="Show on the close-up">{toggles}</div></div>
  <svg class="chart" viewBox="0 0 1000 380" role="img" aria-label="Close-up of the flood front: exact answer and model results"></svg>
  <div class="controls"><div class="readout"></div></div>
  {_data_script(close)}
</section>"""
    return html_, ""


BUILD_COMMIT = ""   # set by build.py: the commit the site was built from
INPUT_ZIPS: dict = {}  # (sid, key) -> (published path, bytes), set by build.py


def run_block(sid: str, k: str, card: dict, up: str = "../") -> str:
    """How this result was produced, and how to produce it again."""
    import recipes

    r = recipes.recipe(k, sid)
    if not r:
        return ""
    ver = (card.get("solver") or {}).get("version") or ""
    commit = BUILD_COMMIT[:12] or "master"
    clone = [f"git clone {recipes.REPO_URL} && cd benchmark1d2d", f"git checkout {commit}"]
    steps = "\n".join(clone + r["install"] + r["run"])
    z = INPUT_ZIPS.get((sid, k))
    files = (f'<p class="small"><a href="{up}{esc(z[0])}" download>The model files the suite wrote for this run (.zip, {nice(z[1] / 1024, 2)} KB)</a>: '
             'the exact inputs the solver read (one folder per grid, where the test has several), with their SHA-256.</p>' if z else
             '<p class="small muted">The model files for this run will be published with its next run.</p>')
    note = f'<p class="small">{esc(r["note"])}</p>' if r.get("note") else ""
    return (f'<details class="share run-it"><summary>Run it yourself</summary>'
            f'<p class="small">{esc(card.get("solver", {}).get("name", ""))}{f" · version {esc(ver)}" if ver and ver not in card.get("solver", {}).get("name", "") else ""} · '
            f'runs on {esc(r["platform"])} · produced by <a href="{REPO_URL}/blob/master/{esc(r["script"])}">{esc(r["script"])}</a> '
            f'in <a href="{REPO_URL}/blob/master/.github/workflows/{esc(r["workflow"])}">{esc(r["workflow"])}</a>.</p>'
            f'<pre class="code"><code>{esc(steps)}</code></pre>{files}{note}'
            f'<p class="small">The test itself (inputs, exact answer, limits): <a href="{up}data/cases/{esc(sid)}.zip" download>{esc(sid)}.zip</a>. '
            f'The score card above is signed; check it with <code>benchmark1d2d verify-card</code>.</p></details>')


def share_block(sid: str, k: str, card: dict) -> str:
    """A link to this result and a badge to embed it."""
    link = f"{SITE_URL}results.html#cell={sid}|{k}"
    badge = f"{SITE_URL}badges/{sid}/{k}.svg"
    word = VERDICT_WORD[verdict(card)]
    md = f"[![OpenHydro Bench {sid}: {word}]({badge})]({link})"
    html_ = f'<a href="{link}"><img src="{badge}" alt="OpenHydro Bench {sid}: {word}"></a>'
    return (f'<details class="share"><summary>Share or embed this result</summary>'
            f'<p class="small"><img src="../badges/{esc(sid)}/{esc(k)}.svg" alt="" height="20"></p>'
            f'<label class="small">Link<input type="text" readonly value="{esc(link)}" onclick="this.select()"></label>'
            f'<label class="small">Badge (Markdown)<input type="text" readonly value="{esc(md)}" onclick="this.select()"></label>'
            f'<label class="small">Badge (HTML)<input type="text" readonly value="{esc(html_)}" onclick="this.select()"></label>'
            f'<p class="small muted">The badge always shows the latest published result.</p></details>')


def series_label(k: str, keys: list[str]) -> str:
    """A model's name on a chart, with its variant when another series has the same name."""
    s_ = SOLVER[k]
    same = sum(1 for o in keys if SOLVER[o]["name"] == s_["name"])
    if same < 2:
        return s_["name"]
    sub = s_["sub"].split("·")[-1].strip()
    return f'{s_["name"]} {sub}'


def far_off(m: dict, card: dict | None) -> bool:
    """A run that fails its first gating check by more than three times the limit starts hidden on the chart."""
    if not card or card.get("passed"):
        return False
    for r in card.get("criteria_results", []):
        if r.get("gating") and r.get("observed") is not None and r["threshold"]["op"] == "abs<=":
            return abs(r["observed"]) > 3 * float(r["threshold"]["value"])
    return False


def _data_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" class="chart-data">{text}</script>'


def network_charts(m: dict, runs: dict, charts: list | None) -> str:
    """Extra charts (drainage, coupled and flood-gauge tests, site/netcharts.py), one section each."""
    out = []
    for ch in charts or []:
        series = []
        keys = SOLVERS_ORDER(set(ch["series"]) & set(runs))
        for k in keys:
            s_ = SOLVER[k]
            d = ch["series"][k]
            series.append(dict(key=k, label=series_label(k, keys), color=s_["color"],
                               x=d["x"], y=d["y"], dots=bool(d.get("dots")), join=bool(d.get("dots"))))
        if not series:
            continue
        ex = ch.get("exact")
        data = dict(xlabel=ch["xlabel"], ylabel=ch["ylabel"], exact=ex, series=series, band=ch.get("band"), symmetric=ch.get("symmetric", False),
                    rescale=ch.get("rescale", False), snap=ch.get("snap", False), unit=ch.get("unit", ""), labels=ch.get("labels"),
                    free=ch.get("free", False))
        toggles = (f'<button type="button" class="pill" data-series="exact" aria-pressed="true"><span class="sw" style="background:var(--water)"></span>{esc(ex.get("label") or "Exact answer")}</button>'
                   if ex else "")
        for s_ in series:
            toggles += f'<button type="button" class="pill" data-series="{s_["key"]}" aria-pressed="true"><span class="sw" style="background:{s_["color"]}"></span>{esc(s_["label"])}</button>'
        out.append(f"""<section class="replay" aria-label="{esc(ch['title'])}">
  <h3>{esc(ch['title'])}</h3>
  {f'<p class="chart-note">{esc(ch["note"])}</p>' if ch.get("note") else ''}
  <div class="replay-top"><div class="toggles" role="group" aria-label="Show on the chart">{toggles}</div></div>
  <svg class="chart" viewBox="0 0 1000 380" role="img" aria-label="{esc(ch['title'])}: {esc(ch['ylabel'])} against {esc(ch['xlabel'].lower())}"></svg>
  <div class="controls"><div class="readout">Point at the chart to read every model's value; click a name to hide or show it.</div></div>
  {_data_script(data)}
</section>""")
    return "".join(out)


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


def case_page(m: dict, runs: dict, exact: dict | None, profiles: dict, legacy_figs: str, evidence: list[dict], extra: list | None = None) -> str:
    from benchmark1d2d.catalog.promotion import checklist, next_stage

    sid = sid_of(m["test_id"])
    st = story(m)
    group = GROUPS.get(st["group"], "")
    chart_html, chart_data = compare_chart(m, runs, exact, profiles)
    net_html = network_charts(m, runs, extra)
    net_head = "Measurements and models" if (m.get("reference") or {}).get("kind") == "measured" else "Exact answer and models"
    netsec = (f'<section class="section" style="padding-bottom:0"><h2>{net_head}</h2>{net_html}</section>' if net_html else "")
    if net_html:
        chart_html = net_html

    figure = ("" if net_html else chart_html) or (f'<section class="card">{legacy_figs}</section>' if legacy_figs.strip() else "")
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
        checks = "".join(f'<div class="check{ {"ok": "", "no": " bad", "unsure": " unsure", "info": " info"}[ck["state"]] }"><div class="k">{esc(ck["label"])}</div>'
                         f'<div class="v">{SYM[ck["state"]]} {esc(ck["value"])}</div><div class="lim">{esc(ck["limit"])}{_margin_span(ck)}</div></div>'
                         for ck in checks_for(m, c))
        note = NOTES.get((sid, k), "")
        name = s["name"] if not k.startswith("lisflood") else f'{s["name"]} {s["sub"].split("·")[-1].strip()}'
        mcards.append(f"""<article class="model-card" id="m-{k}">
  <div class="top"><div><div class="name"><span class="sw" style="background:{s['color']}"></span>{esc(name)}</div><div class="what">{esc(s['what'])}</div></div>{badge(c)}</div>
  {two_verdicts(c)}
  <div class="checks-grid">{checks}</div>
  {f'<p class="note">{esc(note)}</p>' if note else ''}
  <p class="note small">Signed score card: <a href="../data/scorecards/{k}/{esc(c['_path'].name)}" download>{esc((c.get('solver') or {}).get('name', ''))}</a></p>
  {share_block(sid, k, c)}
  {run_block(sid, k, c) if m["track"] == "A" else ""}
</article>""")
    levels = (m["simulation"].get("mesh_refinement") or {}).get("levels") or []
    grid_txt = (f"Each model runs the same inputs on {len(levels)} grids, from {nice(max(levels), 3)} m down to {nice(min(levels), 3)} m cells."
                if len(levels) > 1 else "Each model runs the same inputs.")
    case_note = CASE_NOTES.get(sid)
    not_yet = ""
    if (sid.startswith("A1D") or sid.startswith("A12")) and m["status"] != "draft":
        nyl = NOT_YET_DRAINAGE if sid.startswith("A1D") else NOT_YET_COUPLED
        not_yet = (f'<div class="notyet"><div><b>Not run yet:</b> {esc(", ".join(nyl))}</div>'
                   f'<a href="../score.html" style="font-weight:600">Run it and add yours →</a></div>')
    elif m["track"] == "A" and m["physics"]["dimensionality"] in ("1D", "2D") and m["status"] != "draft":
        missing = [SOLVER[k]["name"] for k in PRODUCTION_2D if k not in runs and not k.startswith("lisflood-")]
        if not any(k.startswith("lisflood") for k in runs):
            missing.append("LISFLOOD-FP")
        missing = list(dict.fromkeys(missing)) + NOT_YET
        not_yet = (f'<div class="notyet"><div><b>Not run yet:</b> {esc(", ".join(missing))}</div>'
                   f'<a href="../score.html" style="font-weight:600">Run it and add yours →</a></div>')
    if mcards:
        models = f"""<section class="section" style="padding-bottom:0" id="models">
  <h2>How models did</h2>
  <p class="muted">{esc(grid_txt)}{f' <a href="../viewer.html#{esc(sid)}">Compare them in the results viewer{" (depth maps and animation)" if m["physics"].get("dimensionality") == "2D" else ""} →</a>' if m["track"] == "A" else ""}</p>
  {f'<p class="callout">{esc(case_note)}</p>' if case_note else ''}
  <div class="models">{''.join(mcards)}{not_yet}</div>
</section>"""
    else:
        models = f"""<section class="section" style="padding-bottom:0" id="models"><h2>How models did</h2>
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
        "exact_states": "Exact states that follow from the inputs by conservation and hydrostatics: exchanged and discharged volumes, settled levels and steady flows, plus the model's own volume balance.",
        "measured": f"Measured data at <code>{esc(m['reference'].get('data_path', ''))}</code>; availability: <b>{esc(str(m['reference'].get('availability', 'unknown')).replace('_', ' '))}</b>.",
        "pinned_engine": f"{esc(m['reference'].get('engine'))} {esc(m['reference'].get('version'))}, run on the test's own input.",
    }.get(kind, "")
    states = ""
    if kind in ("intercomparison", "exact_states"):
        states = '<div class="table-scroll"><table class="data"><thead><tr><th>Expected state</th><th class=num>Value</th><th>Why it must hold</th></tr></thead><tbody>' + "".join(
            f"<tr><td><b>{esc(s['id'])}</b><div class=muted>{esc(s['variable'])}{(' at ' + esc(s.get('where') or s.get('element'))) if (s.get('where') or s.get('element')) else ''}</div></td>"
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
    kind = (m.get("reference") or {}).get("kind")
    truth = {"analytic": "Exact solution", "exact_states": "Exact, from conservation", "intercomparison": "Known end states",
             "measured": "Laboratory or field measurements", "pinned_engine": "A pinned reference engine"}.get(kind, "")
    n_run = len(runs)
    n_ok = sum(1 for c in runs.values() if c.get("passed"))
    result_line = (f"<b>{n_ok} of {n_run}</b> model{'s' if n_run != 1 else ''} pass" if n_run else "No model run yet")
    hero_chart = bool(chart_html) and not net_html
    art = (f'<figure class="case-art">{tile_svg(sid, "Sketch of the test: " + st["name"], fit="meet")}'
           f'<figcaption><dl class="glance"><dt>Right answer</dt><dd>{esc(truth)}{(" · " + esc(_source_short(m))) if _source_short(m) else ""}</dd>'
           f'<dt>Results</dt><dd>{result_line} · <a href="#models">see them ↓</a></dd>'
           f'<dt>Must</dt><dd>{esc(st["must"][0])}</dd></dl>'
           f'<span class="small">Sketch, not to scale.</span></figcaption></figure>') if not hero_chart else ""
    body = f'<div class="wrap">{head}{art}{figure}{story_cards}{netsec}{models}{split}{tech}</div>{chart_data}'
    scripts = '<script src="../static/chart.js" defer></script>' if chart_html else ""
    return layout(st["name"], body, "results.html", depth=1, description=st["question"], scripts=scripts, math=True,
                  og_image=f"assets/og/{sid}.png", path=f"tests/{sid}.html")


# ── score your model ────────────────────────────────────────────────────────


def score_page(manifests: list[dict], checkable: list[dict]) -> str:
    checkable = sorted(checkable, key=lambda c: c["sid"])
    opts = "".join(f'<option value="{esc(c["sid"])}">{esc(c["sid"])} — {esc(c["name"])}</option>' for c in checkable)
    rows = "".join(
        f'<tr id="{esc(c["sid"])}"><td><a href="tests/{esc(c["sid"])}.html"><b>{esc(c["name"])}</b></a><div class="muted small">{esc(c["sid"])}</div></td>'
        f'<td><a href="data/cases/{esc(c["sid"])}.zip" download>Inputs (.zip)</a></td>'
        f'<td>{" · ".join(f"<a href=\"data/check/{esc(f)}\" download>{esc(lab)}</a>" for lab, f in c["templates"])}</td></tr>'
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
  <p class="muted">These tests have exact answers, so your results can be compared point by point, node by node, or state by state. Templates list what to report: one file per grid size for the channel and flood tests, one file for the drainage and coupled tests.</p>
  <div class="table-scroll"><table class="data"><thead><tr><th>Test</th><th>Inputs</th><th>Results templates (grid size)</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>
<section class="section tight">
  <h2>Getting an official score card</h2>
  <p>The browser check uses the same formulas as the scorer, but an official result is a signed score card made by the command-line tool, which also reads Parquet, network results and the other tests:</p>
<pre><code>pip install -e ".[dev]"
benchmark1d2d score A1F-010 --results mine_dx1.25.csv \\
  --refinement mine_dx10.csv mine_dx5.csv mine_dx2.5.csv mine_dx1.25.csv \\
  --solver-name my-solver --solver-version 1.0</code></pre>
  <p>To publish results, <a href="{REPO_URL}/blob/master/docs/submitting.md">submit your results files</a>: the suite scores them itself and lists them on the site as submitted by you. The <a href="get-started.html">command-line guide</a> covers network and compatibility tests.</p>
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
    return (f'<!doctype html><html lang="en"><meta charset="utf-8"><title>Moved</title><meta http-equiv="refresh" content="0; url={esc(to)}">'
            f'<link rel="canonical" href="{esc(to)}"><p>This page moved to <a href="{esc(to)}">{esc(to)}</a>.</p>')
