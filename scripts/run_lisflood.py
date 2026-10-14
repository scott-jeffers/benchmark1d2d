#!/usr/bin/env python3
"""Score LISFLOOD-FP 8.3 (University of Bristol) on the catalog's 2D-grid cases.

LISFLOOD-FP is an open-source (GPL-3.0) raster flood model widely used for
large-scale inundation. Its three CPU solvers are run as black boxes with
their own defaults (CFL, wet/dry threshold, limiters); only the input
rasters, the simulation time, closed or fixed boundaries and the output
precision are set:

* ``fv1``  first-order Godunov finite volume (full shallow-water equations)
* ``dg2``  second-order discontinuous Galerkin (full shallow-water equations)
* ``acc``  the local-inertia ("acceleration") solver LISFLOOD-FP is best known
  for. It drops the advection term, so it is *expected* to miss supercritical
  flow and shocks; it is scored anyway, because it is what most users run.

(``fv2`` exists only in the CUDA build; on the CPU the keyword silently falls
back to the old diffusive scheme, so it is not offered here.)

``initial_tstep`` is LISFLOOD-FP's largest allowed step; it is set to the
whole simulation so the CFL condition alone controls the step. Output
precision is raised from the 3-decimal default to 8, because 3 decimals
(1 mm) is the size of several of the catalog's tolerances. DG2 also needs the
x and y slope coefficients of the bed and the initial depth (``<file>1x``,
``<file>1y``); they are made the way LISFLOOD-FP's own ``generateDG2DEM`` does,
from the four corner values of each cell, but from the exact function rather
than a raster.

Cases: A1F-010 (Ritter) and A1F-011 (Stoker) on a two-cell-wide strip;
A2A-001 (Thacker bowl); A2A-010 (MacDonald 2D, ``QFIX`` inflow west and
``HFIX`` water level east). A2A-020 (oblique jump) needs a supercritical inflow
with both depth and velocity fixed, which LISFLOOD-FP's boundary types cannot
express, so it is not run.

Build (CPU only; NetCDF-C, OpenMP and libnuma required)::

    cmake -S LISFLOOD-FP-8.3/source -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --target lisflood

Score cards go to ``out/lisflood/<solver>/``. Usage::

    python scripts/run_lisflood.py --exe build/lisflood [--solver fv1 dg2 acc] [CASE ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "lisflood"
TS = "2024-01-01T00:00:00Z"
G = 9.81
KEYWORD = {"fv1": "fv1", "dg2": "dg2", "acc": "acceleration"}
LABEL = {"fv1": "FV1", "dg2": "DG2", "acc": "ACC"}
Field = Callable[[np.ndarray, np.ndarray], np.ndarray]


# ── raster I/O ──────────────────────────────────────────────────────────────


class Grid:
    def __init__(self, x0: float, y0: float, dx: float, nx: int, ny: int):
        self.x0, self.y0, self.dx, self.nx, self.ny = x0, y0, dx, nx, ny

    def centres(self):
        xs = self.x0 + (np.arange(self.nx) + 0.5) * self.dx
        ys = self.y0 + (np.arange(self.ny) + 0.5) * self.dx
        return np.meshgrid(xs, ys)  # [row from south, col from west]

    def header(self) -> str:
        return f"ncols {self.nx}\nnrows {self.ny}\nxllcorner {self.x0:.12g}\nyllcorner {self.y0:.12g}\ncellsize {self.dx:.12g}\nNODATA_value -9999\n"


def write_asc(path: Path, g: Grid, a: np.ndarray) -> None:
    with open(path, "w", encoding="ascii") as f:
        f.write(g.header())
        for row in a[::-1]:  # ASCII grids store the northern row first
            f.write(" ".join(f"{v:.12g}" for v in row) + "\n")


def read_asc(path: Path, g: Grid) -> np.ndarray:
    """A LISFLOOD-FP raster as [row from south, col from west] at cell centres.

    Face-centred grids (ACC writes velocity with ``ncols+1`` or ``nrows+1``)
    are averaged onto the cells.
    """
    hdr = {}
    with open(path, encoding="ascii") as f:
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.lower()] = float(v)
        a = np.loadtxt(f, ndmin=2)
    a = np.where(a == hdr["nodata_value"], np.nan, a)[::-1]
    if a.shape[1] == g.nx + 1:
        a = 0.5 * (a[:, 1:] + a[:, :-1])
    if a.shape[0] == g.ny + 1:
        a = 0.5 * (a[1:] + a[:-1])
    assert a.shape == (g.ny, g.nx), (path, a.shape, (g.ny, g.nx))
    return a


def dg2_coefficients(f: Field, g: Grid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean and x/y slope coefficients from the cell corners (LISFLOOD-FP's
    ``dg2::initialise_field``). Corners are pulled a hair inside the cell so a
    discontinuity lying on a cell face is seen from the correct side."""
    X, Y = g.centres()
    e = 0.5 * g.dx * (1 - 1e-9)
    sw, se, nw, ne = f(X - e, Y - e), f(X + e, Y - e), f(X - e, Y + e), f(X + e, Y + e)
    r = 4 * np.sqrt(3.0)
    return 0.25 * (sw + se + nw + ne), (ne + se - nw - sw) / r, (ne + nw - se - sw) / r


def run(exe: Path, solver: str, g: Grid, zf: Field, hf: Field, t_end: float, fric: float = 0.0,
        bci: list[str] | None = None) -> dict[str, np.ndarray]:
    X, Y = g.centres()
    with tempfile.TemporaryDirectory() as td:
        w = Path(td)
        if solver == "dg2":
            for name, f in (("c.dem", zf), ("c.start", hf)):
                m0, m1x, m1y = dg2_coefficients(f, g)
                write_asc(w / name, g, m0)
                write_asc(w / f"{name}1x", g, m1x)
                write_asc(w / f"{name}1y", g, m1y)
            z = dg2_coefficients(zf, g)[0]
        else:
            z = zf(X, Y)
            write_asc(w / "c.dem", g, z)
            write_asc(w / "c.start", g, hf(X, Y))
        par = [
            "DEMfile c.dem", "startfile c.start", "resroot c", "dirroot res",
            f"sim_time {t_end:.12g}", f"initial_tstep {t_end:.12g}", f"saveint {t_end:.12g}", f"massint {t_end:.12g}",
            f"fpfric {fric:.12g}", KEYWORD[solver], "voutput", "output_precision 8",
        ]
        if bci:
            (w / "c.bci").write_text("\n".join(bci) + "\n", encoding="ascii")
            par.append("bcifile c.bci")
        (w / "c.par").write_text("\n".join(par) + "\n", encoding="ascii")
        p = subprocess.run([str(exe), "c.par"], cwd=w, capture_output=True, text=True, timeout=3600)
        r = w / "res"
        if p.returncode != 0 or not (r / "c-0001.wd").exists():
            raise RuntimeError(f"lisflood failed ({p.returncode}):\n{p.stdout[-3000:]}\n{p.stderr[-2000:]}")
        h = np.nan_to_num(read_asc(r / "c-0001.wd", g))
        u = np.nan_to_num(read_asc(r / "c-0001.Vx", g))
        v = np.nan_to_num(read_asc(r / "c-0001.Vy", g))
    return {"X": X, "Y": Y, "h": h, "u": u, "v": v, "z": z}


def _frame2d(s, t):
    n = s["X"].size
    return {"t": np.full(n, t), "x": s["X"].ravel(), "y": s["Y"].ravel(), "h": s["h"].ravel(), "u": s["u"].ravel(),
            "v": s["v"].ravel(), "p": np.full(n, np.nan), "z": s["z"].ravel()}


def _n(lo, hi, dx):
    return int(round((hi - lo) / dx))


# ── cases ───────────────────────────────────────────────────────────────────


def dam_break(exe, solver, m, dx, tid):
    p = m["reference"]["generator"]["parameters"]
    if tid.startswith("A1F-010"):
        xmin, xmax, x0, hl, hr = 0.0, 2000.0, float(p.get("x0", 1000.0)), float(p.get("h0", 1.0)), 0.0
    else:
        xmin, xmax, x0, hl, hr = -1000.0, 1000.0, float(p.get("x0", 0.0)), float(p.get("hl", 1.0)), float(p.get("hr", 0.1))
    g = Grid(xmin, 0.0, dx, _n(xmin, xmax, dx), 2)
    t = float(m["simulation"]["t_end"])
    s = run(exe, solver, g, lambda x, y: np.zeros_like(x), lambda x, y: np.where(x < x0, hl, hr), t)
    xs = s["X"][0]
    n = xs.size
    nan = np.full(n, np.nan)
    h, u = s["h"].mean(axis=0), s["u"].mean(axis=0)
    return {"t": np.full(n, t), "x": xs, "y": nan.copy(), "h": h, "u": u, "v": nan.copy(), "p": nan.copy(), "Q": h * u}


def thacker(exe, solver, m, dx, tid):
    from references.thacker import bed_elevation, depth_velocity

    prm = m["reference"]["generator"]["parameters"]
    dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
    g = Grid(dom["xmin"], dom["ymin"], dx, _n(dom["xmin"], dom["xmax"], dx), _n(dom["ymin"], dom["ymax"], dx))
    zf = lambda x, y: bed_elevation(x, y, prm["h0"], prm["L"])  # noqa: E731
    hf = lambda x, y: np.maximum(depth_velocity(x, y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", G))["h"], 0.0)  # noqa: E731
    t = float(m["simulation"]["t_end"])
    return _frame2d(run(exe, solver, g, zf, hf, t), t)


def macdonald_2d(exe, solver, m, dx, tid):
    from references.macdonald_2d import bed_elevation, depth_profile

    prm = m["reference"]["generator"]["parameters"]
    L, W, q, n = prm["L"], prm["W"], prm["q"], prm["n_manning"]
    g = Grid(0.0, 0.0, dx, _n(0, L, dx), _n(0, W, dx))
    zf = lambda x, y: bed_elevation(x, L=L, q=q, n_manning=n) + 0.0 * y  # noqa: E731
    h_out = float(depth_profile(L))
    zl = float(bed_elevation(L, L=L, q=q, n_manning=n))
    hf = lambda x, y: np.full_like(x, h_out)  # noqa: E731  (uniform depth: the steady profile must emerge)
    bci = [f"W 0 {W:.12g} QFIX {q:.12g}", f"E 0 {W:.12g} HFIX {zl + h_out:.12g}"]
    t = float(m["simulation"]["t_end"])
    return _frame2d(run(exe, solver, g, zf, hf, t, fric=n, bci=bci), t)


CASES = {"A1F-010": dam_break, "A1F-011": dam_break, "A2A-001": thacker, "A2A-010": macdonald_2d}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    ap.add_argument("--exe", type=Path, required=True, help="the lisflood executable")
    ap.add_argument("--solver", nargs="+", choices=list(KEYWORD), default=list(KEYWORD))
    ap.add_argument("--version", default="8.3")
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    exe = args.exe.resolve()
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    for sv in args.solver:
        out = OUT / sv
        out.mkdir(parents=True, exist_ok=True)
        solver = {"name": f"LISFLOOD-FP {args.version} {LABEL[sv]}", "version": args.version,
                  "adapter": f"lisflood ({KEYWORD[sv]} solver, defaults; CPU, double precision)"}
        for tid in args.cases:
            m = load_manifest(tid, repo=REPO)
            paths = []
            for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
                t0 = time.perf_counter()
                cols = CASES[tid](exe, sv, m, float(dx), tid)
                paths.append(write_results_parquet(out / f"{m['test_id']}_dx{dx:g}.parquet", cols))
                print(f"  {sv} {tid} dx={dx}: {time.perf_counter() - t0:.1f}s", flush=True)
            card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{'PASS' if card['passed'] else 'FAIL'} {m['test_id']} ({solver['name']})")
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
            c = card.get("convergence_result") or {}
            print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}", flush=True)
            if not card["passed"]:
                print(f"::warning title=LISFLOOD-FP {LABEL[sv]} {m['test_id']}::fails at least one criterion (a finding, not a harness error)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
