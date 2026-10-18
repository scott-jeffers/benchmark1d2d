#!/usr/bin/env python3
"""Score Landlab's OverlandFlow component on the catalog's grid tests.

Landlab (Hobley et al. 2017; Barnhart et al. 2020; ``pip install landlab``)
is an open-source Python toolkit for Earth-surface models. Its
``OverlandFlow`` component is the local-inertial ("de Almeida") 2D flood
scheme used by LISFLOOD-FP's ACC solver, written independently in NumPy. It
is run with its own defaults (CFL ``alpha`` 0.7, ``theta`` 0.8, minimum depth
1e-5 m, no steep-slope limiter); only what the tests need is set:

* the grid: one Landlab node per cell centre of the test's grid, plus a ring
  of boundary nodes;
* walls: the boundary nodes are closed; a held depth downstream: the boundary
  nodes stay open with the depth reset after every step;
* an inflow: water added to the first column of cells after every step
  (Landlab has no discharge boundary), the test's unit discharge times the
  step over the cell size;
* friction: Manning's n where the test has it, 0 elsewhere.

Depths are reported as at least zero (OverlandFlow lets a nearly dry node go
slightly negative) and velocities as discharge over depth where the depth is
at least 1 mm.

Like LISFLOOD-FP's ACC, it drops the advection term, so it is expected to miss
fast (supercritical) flow and shocks; it is scored anyway.

Cases: A1F-010, A1F-011 and A1F-001 and the SWASHES bump channel A1F-040 to
043 on a one-cell-wide strip; A2A-001 (Thacker bowl); A2A-010 (MacDonald 2D).

Score cards go to ``out/landlab/``. Usage::

    python scripts/run_landlab.py [CASE ...]
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "landlab"
from benchmark1d2d.clock import run_timestamp  # noqa: E402

TS = run_timestamp()  # when this run happened (BENCH_TIMESTAMP pins it)
G = 9.80665


class Strip:
    """A Landlab raster whose core nodes are the cell centres x0 + dx/2 … (and y0 + dx/2 …)."""

    def __init__(self, x0: float, x1: float, dx: float, y0: float = 0.0, y1: float | None = None):
        from landlab import RasterModelGrid

        self.nx = int(round((x1 - x0) / dx))
        self.ny = 1 if y1 is None else int(round((y1 - y0) / dx))
        self.dx = dx
        self.g = RasterModelGrid((self.ny + 2, self.nx + 2), xy_spacing=dx, xy_of_lower_left=(x0 - dx / 2, y0 - dx / 2))
        self.z = self.g.add_zeros("topographic__elevation", at="node")
        self.h = self.g.add_zeros("surface_water__depth", at="node")
        self.core = self.g.core_nodes
        self.west_core = self.core[np.isclose(self.g.x_of_node[self.core], x0 + dx / 2)]
        self.east_bdry = np.flatnonzero(np.isclose(self.g.x_of_node, x1 + dx / 2) & (self.g.y_of_node > y0) & (self.g.y_of_node < y0 + self.ny * dx))

    def walls(self, east_open: bool = False) -> None:
        self.g.set_closed_boundaries_at_grid_edges(not east_open, True, True, True)

    def run(self, t_end: float, n: float = 0.0, q_in: float | None = None, h_out: float | None = None) -> float:
        from landlab.components import OverlandFlow

        of = OverlandFlow(self.g, mannings_n=n)
        t = 0.0
        while t < t_end - 1e-9:
            if h_out is not None:
                self.h[self.east_bdry] = h_out
            dt = min(of.calc_time_step(), t_end - t)
            of.overland_flow(dt)
            if q_in is not None:  # the test's unit discharge, added to the first column of cells
                self.h[self.west_core] += q_in * dt / self.dx
            t += dt
        if h_out is not None:
            self.h[self.east_bdry] = h_out
        return t

    def fields(self) -> dict:
        from landlab.grid.raster_mappers import map_mean_of_horizontal_links_to_node, map_mean_of_vertical_links_to_node

        q = self.g.at_link["surface_water__discharge"]
        h = np.maximum(self.h[self.core], 0.0)  # OverlandFlow can drive a nearly dry node below zero; a depth is reported as at least 0
        qx = map_mean_of_horizontal_links_to_node(self.g, q)[self.core]
        qy = map_mean_of_vertical_links_to_node(self.g, q)[self.core]
        wet = h > 1e-3  # velocity only where there is a millimetre of water (q / h is meaningless on a film)
        u = np.where(wet, qx / np.where(wet, h, 1.0), 0.0)
        v = np.where(wet, qy / np.where(wet, h, 1.0), 0.0)
        return {"x": self.g.x_of_node[self.core], "y": self.g.y_of_node[self.core], "h": h, "u": u, "v": v, "z": self.z[self.core]}


def _one_d(s: Strip, t: float) -> dict:
    f = s.fields()
    n = len(f["x"])
    nan = np.full(n, np.nan)
    return {"t": np.full(n, t), "x": f["x"], "y": nan.copy(), "h": f["h"], "u": f["u"], "v": nan.copy(), "p": nan.copy(), "Q": f["h"] * f["u"]}


def _two_d(s: Strip, t: float) -> dict:
    f = s.fields()
    n = len(f["x"])
    return {"t": np.full(n, t), "x": f["x"], "y": f["y"], "h": f["h"], "u": f["u"], "v": f["v"], "p": np.full(n, np.nan), "z": f["z"]}


# ── cases ───────────────────────────────────────────────────────────────────


def dam_break(m: dict, dx: float, tid: str) -> dict:
    p = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())
    dom, ic = p["domain"], p["initial_condition"]
    s = Strip(dom["xmin"], dom["xmax"], dx)
    s.walls()
    s.h[:] = np.where(s.g.x_of_node < ic["dam_x_m"], ic["h_left_m"], ic["h_right_m"])
    s.h[s.g.boundary_nodes] = 0.0
    t = s.run(float(m["simulation"]["t_end"]))
    return _one_d(s, t)


def macdonald_1d(m: dict, dx: float, tid: str) -> dict:
    from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

    L, B, Q, n = (float(M1_PARAMS[k]) for k in ("L", "B", "Q", "n_manning"))
    fine = np.linspace(0.0, L, 200001)
    zfine = bed_elevation(fine)  # beyond the ends (the boundary nodes) the bed is held level
    s = Strip(0.0, L, dx)
    s.walls(east_open=True)
    s.z[:] = np.interp(s.g.x_of_node, fine, zfine)
    h_out = float(depth_profile(np.array([L]))[0])
    s.h[:] = h_out
    t = s.run(float(m["simulation"]["t_end"]), n=n, q_in=Q / B, h_out=h_out)
    return _one_d(s, t)


def swashes_bump(m: dict, dx: float, tid: str) -> dict:
    from references.swashes import bed

    p = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())
    L = p["domain"]["xmax"]
    up, down = p["upstream"], p["downstream"]
    s = Strip(0.0, L, dx)
    s.walls(east_open="depth_m" in down)
    s.z[:] = bed(np.clip(s.g.x_of_node, 0.0, L))
    s.h[:] = np.maximum(p["initial"]["level_m"] - s.z, 0.0)
    s.h[s.g.boundary_nodes] = 0.0
    t = s.run(float(m["simulation"]["t_end"]), q_in=up.get("discharge_m2s"), h_out=down.get("depth_m"))
    return _one_d(s, t)


def thacker(m: dict, dx: float, tid: str) -> dict:
    from references.thacker import bed_elevation, depth_velocity

    prm = m["reference"]["generator"]["parameters"]
    dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
    s = Strip(dom["xmin"], dom["xmax"], dx, dom["ymin"], dom["ymax"])
    s.walls()
    x, y = s.g.x_of_node, s.g.y_of_node
    s.z[:] = bed_elevation(x, y, prm["h0"], prm["L"])
    s.h[:] = np.maximum(depth_velocity(x, y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", 9.81))["h"], 0.0)
    s.h[s.g.boundary_nodes] = 0.0
    t = s.run(float(m["simulation"]["t_end"]))
    return _two_d(s, t)


def macdonald_2d(m: dict, dx: float, tid: str) -> dict:
    from references.macdonald_2d import bed_elevation, depth_profile

    prm = m["reference"]["generator"]["parameters"]
    L, W, q, n = prm["L"], prm["W"], prm["q"], prm["n_manning"]
    s = Strip(0.0, L, dx, 0.0, W)
    s.walls(east_open=True)
    s.z[:] = bed_elevation(np.clip(s.g.x_of_node, 0.0, L + dx), L=L, q=q, n_manning=n)
    h_out = float(depth_profile(L))
    s.h[:] = h_out
    t = s.run(float(m["simulation"]["t_end"]), n=n, q_in=q, h_out=h_out)
    return _two_d(s, t)


CASES = {"A1F-010": dam_break, "A1F-011": dam_break, "A1F-001": macdonald_1d,
         "A1F-040": swashes_bump, "A1F-041": swashes_bump, "A1F-042": swashes_bump, "A1F-043": swashes_bump,
         "A2A-001": thacker, "A2A-010": macdonald_2d}


def main() -> int:
    import argparse
    import importlib.metadata as md

    from benchmark1d2d.signing import private_key as signing_key

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    key = signing_key()  # BENCH_SIGNING_KEY, else the public development key
    ver = md.version("landlab")
    solver = {"name": f"Landlab {ver} OverlandFlow", "version": ver,
              "adapter": "landlab.components.OverlandFlow (local inertial, defaults; a node per cell centre)"}
    OUT.mkdir(parents=True, exist_ok=True)
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        paths = []
        for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
            t0 = time.perf_counter()
            cols = CASES[tid](m, float(dx), tid)
            paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx:g}.parquet", cols, wall_seconds=time.perf_counter() - t0))
            print(f"  {tid} dx={dx}: {time.perf_counter() - t0:.1f}s", flush=True)
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        c = card.get("convergence_result") or {}
        print(f"    convergence p={c.get('observed_order')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
