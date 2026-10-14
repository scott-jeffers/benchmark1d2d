#!/usr/bin/env python3
"""Score ANUGA (Geoscience Australia / ANU) on the catalog's 1D and 2D analytic cases.

ANUGA is an open-source unstructured finite-volume shallow-water solver
(conda-forge / PyPI ``anuga``). It is run with its own defaults (flow
algorithm, wet/dry thresholds) on a ``rectangular_cross`` mesh at each of the
case's refinement levels; the final state is sampled at the cell centres of
the case's regular grid, the same points every other solver reports on.

Cases: A1F-010 (Ritter), A1F-011 (Stoker) on a 2D strip; A2A-001 (Thacker
bowl); A2A-010 (MacDonald 2D channel, inflow by ``Inlet_operator``, stage set
downstream); A2A-020 (oblique jump, upstream state set west and north).

Score cards go to ``out/anuga/``. Usage::

    python scripts/run_anuga.py [CASE ...]
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

import anuga  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from benchmark1d2d.catalog import load_manifest  # noqa: E402
from benchmark1d2d.io.results import write_results_parquet  # noqa: E402
from benchmark1d2d.scoring.scorer import score_case  # noqa: E402

OUT = REPO / "out" / "anuga"
KEY = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
TS = "2024-01-01T00:00:00Z"
G = 9.81


def _domain(lx: float, ly: float, dx: float, origin=(0.0, 0.0)):
    m, n = max(int(round(lx / dx)), 1), max(int(round(ly / dx)), 1)
    d = anuga.rectangular_cross_domain(m, n, len1=lx, len2=ly, origin=origin)
    d.set_store(False)
    return d


def _sample(domain, pts: np.ndarray) -> dict[str, np.ndarray]:
    st = domain.quantities["stage"].get_values(interpolation_points=pts)
    el = domain.quantities["elevation"].get_values(interpolation_points=pts)
    xm = domain.quantities["xmomentum"].get_values(interpolation_points=pts)
    ym = domain.quantities["ymomentum"].get_values(interpolation_points=pts)
    h = np.maximum(st - el, 0.0)
    wet = h > 1e-6
    u = np.where(wet, xm / np.where(wet, h, 1.0), 0.0)
    v = np.where(wet, ym / np.where(wet, h, 1.0), 0.0)
    return {"h": h, "u": u, "v": v, "z": el}


def _grid(x0, x1, y0, y1, dx):
    xs = np.arange(x0 + dx / 2, x1, dx)
    ys = np.arange(y0 + dx / 2, y1, dx)
    X, Y = np.meshgrid(xs, ys)
    return np.column_stack([X.ravel(), Y.ravel()])


def _evolve(domain, t_end: float) -> float:
    for t in domain.evolve(yieldstep=t_end, finaltime=t_end):
        pass
    return float(domain.get_time())


# ── cases ───────────────────────────────────────────────────────────────────


def dam_break(m: dict, dx: float, tid: str) -> dict:
    p = m["reference"]["generator"]["parameters"]
    if tid.startswith("A1F-010"):
        xmin, xmax, x0, hl, hr = 0.0, 2000.0, float(p.get("x0", 1000.0)), float(p.get("h0", 1.0)), 0.0
    else:
        xmin, xmax, x0, hl, hr = -1000.0, 1000.0, float(p.get("x0", 0.0)), float(p.get("hl", 1.0)), float(p.get("hr", 0.1))
    width = 2 * dx
    d = _domain(xmax - xmin, width, dx, origin=(xmin, 0.0))
    d.set_quantity("elevation", 0.0)
    d.set_quantity("friction", 0.0)
    d.set_quantity("stage", lambda x, y: np.where(x < x0, hl, hr))
    br = anuga.Reflective_boundary(d)
    d.set_boundary({"left": br, "right": br, "top": br, "bottom": br})
    t = _evolve(d, float(m["simulation"]["t_end"]))
    xs = np.arange(xmin + dx / 2, xmax, dx)
    s = _sample(d, np.column_stack([xs, np.full_like(xs, width / 2)]))
    n = len(xs)
    nan = np.full(n, np.nan)
    return {"t": np.full(n, t), "x": xs, "y": nan.copy(), "h": s["h"], "u": s["u"], "v": nan.copy(), "p": nan.copy(), "Q": s["h"] * s["u"]}


def thacker(m: dict, dx: float, tid: str) -> dict:
    from references.thacker import bed_elevation, depth_velocity

    prm = m["reference"]["generator"]["parameters"]
    dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
    d = _domain(dom["xmax"] - dom["xmin"], dom["ymax"] - dom["ymin"], dx, origin=(dom["xmin"], dom["ymin"]))
    zf = lambda x, y: bed_elevation(x, y, prm["h0"], prm["L"])  # noqa: E731
    d.set_quantity("elevation", zf)
    d.set_quantity("friction", 0.0)
    d.set_quantity("stage", lambda x, y: np.maximum(depth_velocity(x, y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", G))["h"], 0.0) + zf(x, y))
    br = anuga.Reflective_boundary(d)
    d.set_boundary({"left": br, "right": br, "top": br, "bottom": br})
    t = _evolve(d, float(m["simulation"]["t_end"]))
    pts = _grid(dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"], dx)
    return _frame2d(pts, _sample(d, pts), t)


def macdonald_2d(m: dict, dx: float, tid: str) -> dict:
    from references.macdonald_2d import bed_elevation, depth_profile

    prm = m["reference"]["generator"]["parameters"]
    L, W, q, n = prm["L"], prm["W"], prm["q"], prm["n_manning"]
    d = _domain(L, W, dx)
    zf = lambda x, y: bed_elevation(x, L=L, q=q, n_manning=n)  # noqa: E731
    h_out = float(depth_profile(L))
    d.set_quantity("elevation", zf)
    d.set_quantity("friction", n)
    d.set_quantity("stage", lambda x, y: zf(x, y) + h_out)  # uniform depth: the steady profile must emerge
    anuga.Inlet_operator(d, [[0.25 * dx, 0.0], [0.25 * dx, W]], Q=q * W)
    zl = float(bed_elevation(L, L=L, q=q, n_manning=n))
    br = anuga.Reflective_boundary(d)
    out = anuga.Transmissive_n_momentum_zero_t_momentum_set_stage_boundary(d, lambda t: zl + h_out)
    d.set_boundary({"left": br, "right": out, "top": br, "bottom": br})
    t = _evolve(d, float(m["simulation"]["t_end"]))
    pts = _grid(0.0, L, 0.0, W, dx)
    return _frame2d(pts, _sample(d, pts), t)


def oblique_jump(m: dict, dx: float, tid: str) -> dict:
    from references.oblique_jump import states

    prm = m["reference"]["generator"]["parameters"]
    dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
    st = states(prm["Fr1"], prm["theta_deg"], prm["h1"], prm.get("g", G))
    d = _domain(dom["xmax"] - dom["xmin"], dom["ymax"] - dom["ymin"], dx, origin=(dom["xmin"], dom["ymin"]))
    d.set_quantity("elevation", 0.0)
    d.set_quantity("friction", 0.0)
    d.set_quantity("stage", st["h1"])
    d.set_quantity("xmomentum", st["h1"] * st["u1"])
    d.set_quantity("ymomentum", st["h1"] * st["v1"])
    inflow = anuga.Dirichlet_boundary([st["h1"], st["h1"] * st["u1"], st["h1"] * st["v1"]])
    d.set_boundary({"left": inflow, "top": inflow, "bottom": anuga.Reflective_boundary(d), "right": anuga.Transmissive_boundary(d)})
    t = _evolve(d, float(m["simulation"]["t_end"]))
    pts = _grid(dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"], dx)
    return _frame2d(pts, _sample(d, pts), t)


def _frame2d(pts, s, t):
    n = len(pts)
    return {"t": np.full(n, t), "x": pts[:, 0], "y": pts[:, 1], "h": s["h"], "u": s["u"], "v": s["v"], "p": np.full(n, np.nan), "z": s["z"]}


CASES = {"A1F-010": dam_break, "A1F-011": dam_break, "A2A-001": thacker, "A2A-010": macdonald_2d, "A2A-020": oblique_jump}


def main(argv: list[str]) -> int:
    solver = {"name": f"ANUGA {anuga.__version__}", "version": anuga.__version__, "adapter": "anuga (rectangular_cross mesh, defaults, sampled at cell centres)"}
    OUT.mkdir(parents=True, exist_ok=True)
    for tid in argv or list(CASES):
        m = load_manifest(tid, repo=REPO)
        paths = []
        for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
            t0 = time.perf_counter()
            with tempfile.TemporaryDirectory() as td:
                import os

                cwd = os.getcwd()
                os.chdir(td)  # ANUGA may drop scratch files in the working directory
                try:
                    cols = CASES[tid](m, float(dx), tid)
                finally:
                    os.chdir(cwd)
            paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx:g}.parquet", cols))
            print(f"  {tid} dx={dx}: {time.perf_counter() - t0:.1f}s")
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=KEY, solver=solver)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{'PASS' if card['passed'] else 'FAIL'} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        c = card.get("convergence_result") or {}
        print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
        if not card["passed"]:
            print(f"::warning title=ANUGA {m['test_id']}::fails at least one criterion (a finding, not a harness error)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
