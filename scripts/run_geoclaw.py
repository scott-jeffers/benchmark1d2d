#!/usr/bin/env python3
"""Score GeoClaw (Clawpack 5.9) on the dam-break cases and the Thacker bowl.

GeoClaw is the open-source shallow-water code in Clawpack (finite volume,
f-wave Riemann solvers, adaptive mesh refinement), widely used for tsunamis
and floods. It is compiled from the Clawpack source (``--claw``) and run with
the settings of its own stock example (``tsunami/chile2010``: second order, MC
limiters, transverse waves, dry tolerance 1 mm) except where a case needs
otherwise: Cartesian coordinates, one grid level (no AMR, so each refinement
level is a uniform grid), walls on every side, no friction.

The initial water surface is a GeoClaw "qinit type 4" file (surface
elevation; depth = surface - bed). Cases with inflow boundaries (A2A-010,
A2A-020) need custom boundary Fortran in GeoClaw and are not run.

Score cards go to ``out/geoclaw/``. Usage::

    CLAW=/path/to/clawpack-src python scripts/run_geoclaw.py [CASE ...]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "geoclaw"
TS = "2024-01-01T00:00:00Z"

MAKEFILE = """CLAWMAKE = $(CLAW)/clawutil/src/Makefile.common
CLAW_PKG = geoclaw
EXE = xgeoclaw
SETRUN_FILE = setrun.py
OUTDIR = _output
SETPLOT_FILE = setplot.py
PLOTDIR = _plots
FFLAGS ?= -O2
GEOLIB = $(CLAW)/geoclaw/src/2d/shallow
include $(GEOLIB)/Makefile.geoclaw
SOURCES = \\
  $(CLAW)/riemann/src/rpn2_geoclaw.f \\
  $(CLAW)/riemann/src/rpt2_geoclaw.f \\
  $(CLAW)/riemann/src/geoclaw_riemann_utils.f
include $(CLAWMAKE)
"""


def build(claw: Path) -> Path:
    bdir = OUT / "build"
    bdir.mkdir(parents=True, exist_ok=True)
    exe = bdir / "xgeoclaw"
    if exe.is_file():
        return exe
    (bdir / "Makefile").write_text(MAKEFILE)
    env = dict(os.environ, CLAW=str(claw))
    t0 = time.perf_counter()
    proc = subprocess.run(["make", ".exe"], cwd=bdir, env=env, capture_output=True, text=True)
    if proc.returncode != 0 or not exe.is_file():
        raise RuntimeError(f"GeoClaw build failed:\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    print(f"built GeoClaw in {time.perf_counter() - t0:.0f}s")
    return exe


def write_grid_file(path: Path, x0: float, y0: float, dx: float, values: np.ndarray, header: bool) -> None:
    """Topotype 3 (header + rows north to south) or qinit xyz lines (NW to SE)."""
    ny, nx = values.shape
    with open(path, "w") as fh:
        if header:
            fh.write(f"{nx} ncols\n{ny} nrows\n{x0:.10g} xll\n{y0:.10g} yll\n{dx:.10g} cellsize\n-99999 nodata_value\n")
            for j in range(ny - 1, -1, -1):
                fh.write(" ".join(f"{v:.10g}" for v in values[j]) + "\n")
        else:
            for j in range(ny - 1, -1, -1):
                y = y0 + j * dx
                for i in range(nx):
                    fh.write(f"{x0 + i * dx:.10g} {y:.10g} {values[j, i]:.10g}\n")


def rundata_for(claw: Path, xlo, xhi, ylo, yhi, nx, ny, t_end):
    spec = importlib.util.spec_from_file_location("chile_setrun", claw / "geoclaw/examples/tsunami/chile2010/setrun.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rd = mod.setrun("geoclaw")
    cd = rd.clawdata
    cd.lower = [xlo, ylo]
    cd.upper = [xhi, yhi]
    cd.num_cells = [nx, ny]
    cd.output_style = 2
    cd.output_times = [t_end]
    cd.output_t0 = False
    cd.tfinal = t_end
    cd.output_format = "ascii"
    cd.bc_lower = ["wall", "wall"]
    cd.bc_upper = ["wall", "wall"]
    cd.dt_initial = 1e-3 * (xhi - xlo) / nx
    cd.checkpt_style = 0
    rd.amrdata.amr_levels_max = 1
    cd.capa_index = 0  # Cartesian: no latitude-longitude capacity
    cd.num_aux = 1
    rd.amrdata.aux_type = ["center"]
    geo = rd.geo_data
    geo.coordinate_system = 1
    geo.sea_level = 0.0
    geo.friction_forcing = False
    geo.manning_coefficient = 0.0
    rd.dtopo_data.dtopofiles = []
    rd.gaugedata.gauges = []
    for attr in ("regions",):
        if hasattr(rd, "regiondata"):
            setattr(rd.regiondata, attr, [])
    if hasattr(rd, "flagregiondata"):
        rd.flagregiondata.flagregions = []
    if hasattr(rd, "fgmax_data"):
        rd.fgmax_data.fgmax_grids = []
    if hasattr(rd, "fgout_data"):
        rd.fgout_data.fgout_grids = []
    return rd


def run_case(exe: Path, claw: Path, rdir: Path, xlo, xhi, ylo, yhi, dx, bed, eta0, t_end) -> dict:
    """bed(x, y), eta0(x, y) on node grids; returns final cell-centre fields."""
    rdir.mkdir(parents=True, exist_ok=True)
    nx, ny = int(round((xhi - xlo) / dx)), int(round((yhi - ylo) / dx))
    pad = 2 * dx
    xs = np.arange(xlo - pad, xhi + pad + dx / 2, dx / 2)
    ys = np.arange(ylo - pad, yhi + pad + dx / 2, dx / 2)
    X, Y = np.meshgrid(xs, ys)
    write_grid_file(rdir / "topo.tt3", xs[0], ys[0], dx / 2, bed(X, Y), header=True)
    write_grid_file(rdir / "qinit.xyz", xs[0], ys[0], dx / 2, eta0(X, Y), header=False)
    rd = rundata_for(claw, xlo, xhi, ylo, yhi, nx, ny, t_end)
    rd.topo_data.topofiles = [[3, str(rdir / "topo.tt3")]]
    rd.qinit_data.qinit_type = 4
    rd.qinit_data.qinitfiles = [[str(rdir / "qinit.xyz")]]
    rd.write(out_dir=str(rdir))
    from benchmark1d2d import keep

    keep.inputs("geoclaw", rdir.name.rsplit("_dx", 1)[0], rdir, dx)
    proc = subprocess.run([str(exe)], cwd=rdir, capture_output=True, text=True)
    if proc.returncode != 0 or not (rdir / "fort.q0001").is_file():
        raise RuntimeError(f"xgeoclaw failed in {rdir}:\n{proc.stdout[-3000:]}\n{proc.stderr[-2000:]}")
    return read_final(rdir, nx, ny, xlo, ylo)


def read_final(rdir: Path, nx: int, ny: int, xlo: float, ylo: float) -> dict:
    """Read the output frame (fort.q0001, ascii) and stitch its patches into one grid."""
    lines = (rdir / "fort.q0001").read_text().splitlines()
    t = float((rdir / "fort.t0001").read_text().split()[0])
    keys = ("grid_number", "AMR_level", "mx", "my", "xlow", "ylow", "dx", "dy")
    q = None
    x0, y0 = xlo, ylo
    dxg = dyg = None
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        hdr = {}
        for k in keys:
            val, name = lines[i].split()[:2]
            hdr[name] = float(val)
            i += 1
        mx, my = int(hdr["mx"]), int(hdr["my"])
        block = []
        while len(block) < mx * my:
            if lines[i].strip():
                block.append(list(map(float, lines[i].split())))
            i += 1
        block = np.array(block).reshape(my, mx, -1)
        if q is None:
            dxg, dyg = hdr["dx"], hdr["dy"]
            q = np.full((ny, nx, block.shape[2]), np.nan)
        # patch offsets relative to the domain origin, found from the patch's lower corner
        ix = int(round((hdr["xlow"] - x0) / dxg))
        iy = int(round((hdr["ylow"] - y0) / dyg))
        q[iy:iy + my, ix:ix + mx, :] = block
    if np.isnan(q).any():
        raise RuntimeError("output patches do not cover the grid")
    x = x0 + (np.arange(nx) + 0.5) * dxg
    y = y0 + (np.arange(ny) + 0.5) * dyg
    h, hu, hv, eta = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    wet = h > 1e-8
    u = np.where(wet, hu / np.where(wet, h, 1.0), 0.0)
    v = np.where(wet, hv / np.where(wet, h, 1.0), 0.0)
    return {"t": t, "x": x, "y": y, "h": h, "u": u, "v": v, "z": eta - h}


# ── cases ───────────────────────────────────────────────────────────────────


def dam_break(exe, claw, m, dx, tid):
    p = m["reference"]["generator"]["parameters"]
    if tid.startswith("A1F-010"):
        xlo, xhi, x0, hl, hr = 0.0, 2000.0, float(p.get("x0", 1000.0)), float(p.get("h0", 1.0)), 0.0
    else:
        xlo, xhi, x0, hl, hr = -1000.0, 1000.0, float(p.get("x0", 0.0)), float(p.get("hl", 1.0)), float(p.get("hr", 0.1))
    w = 4 * dx  # GeoClaw needs at least 4 cells in each direction
    f = run_case(exe, claw, OUT / "work" / f"{tid}_dx{dx:g}", xlo, xhi, 0.0, w, dx,
                 lambda X, Y: np.zeros_like(X), lambda X, Y: np.where(X < x0, hl, hr), float(m["simulation"]["t_end"]))
    j = 0  # rows are identical across the strip
    n = len(f["x"])
    nan = np.full(n, np.nan)
    return {"t": np.full(n, f["t"]), "x": f["x"], "y": nan.copy(), "h": f["h"][j], "u": f["u"][j], "v": nan.copy(), "p": nan.copy(), "Q": f["h"][j] * f["u"][j]}


def thacker(exe, claw, m, dx, tid):
    from references.thacker import bed_elevation, depth_velocity

    prm = m["reference"]["generator"]["parameters"]
    dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
    bed = lambda X, Y: bed_elevation(X, Y, prm["h0"], prm["L"])  # noqa: E731
    eta = lambda X, Y: np.where(depth_velocity(X, Y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", 9.81))["h"] > 0,  # noqa: E731
                                depth_velocity(X, Y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", 9.81))["h"] + bed(X, Y), bed(X, Y) - 1.0)
    f = run_case(exe, claw, OUT / "work" / f"{tid}_dx{dx:g}", dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"], dx, bed, eta, float(m["simulation"]["t_end"]))
    X, Y = np.meshgrid(f["x"], f["y"])
    n = X.size
    return {"t": np.full(n, f["t"]), "x": X.ravel(), "y": Y.ravel(), "h": f["h"].ravel(), "u": f["u"].ravel(), "v": f["v"].ravel(), "p": np.full(n, np.nan), "z": f["z"].ravel()}


def lake_at_rest(exe, claw, m, dx, tid):
    """A1F-043 (SWASHES lake at rest with an emerged bump): walls all round, still water at 0.1 m."""
    from references.swashes import bed

    prm = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())
    L, level = prm["domain"]["xmax"], prm["initial"]["level_m"]
    w = 4 * dx
    f = run_case(exe, claw, OUT / "work" / f"{tid}_dx{dx:g}", 0.0, L, 0.0, w, dx,
                 lambda X, Y: bed(np.asarray(X, float)), lambda X, Y: np.full_like(X, level), float(m["simulation"]["t_end"]))
    j = 0
    n = len(f["x"])
    nan = np.full(n, np.nan)
    return {"t": np.full(n, f["t"]), "x": f["x"], "y": nan.copy(), "h": f["h"][j], "u": f["u"][j], "v": nan.copy(), "p": nan.copy(), "Q": f["h"][j] * f["u"][j]}


CASES = {"A1F-010": dam_break, "A1F-011": dam_break, "A1F-043": lake_at_rest, "A2A-001": thacker}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    ap.add_argument("--claw", type=Path, default=Path(os.environ.get("CLAW", "")), help="Clawpack source tree (with geoclaw/src)")
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    claw = args.claw.resolve()
    os.environ["CLAW"] = str(claw)
    version = (claw / "clawutil" / "src" / "python" / "clawutil" / "__init__.py")
    ver = "5.9.2"
    try:
        import clawpack

        ver = getattr(clawpack, "__version__", ver)
    except ImportError:
        pass
    exe = build(claw)
    solver = {"name": f"GeoClaw {ver}", "version": ver, "adapter": "geoclaw (uniform grid, stock example settings)"}
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        paths = []
        for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
            t0 = time.perf_counter()
            cols = CASES[tid](exe, claw, m, float(dx), tid)
            paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx:g}.parquet", cols, wall_seconds=time.perf_counter() - t0))
            print(f"  {tid} dx={dx}: {time.perf_counter() - t0:.1f}s, t={cols['t'][0]:.3f}")
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        c = card.get("convergence_result") or {}
        print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
        if not card["passed"]:
            print(f"::warning title=GeoClaw {m['test_id']}::{'is inconclusive (convergence range straddles the minimum)' if card.get('verdict') == 'inconclusive' else 'fails at least one criterion'} (a finding, not a harness error)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
