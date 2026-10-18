#!/usr/bin/env python3
"""Score HEC-RAS 2D (USACE) on the 2D cases that need boundary lines: MacDonald 2D and the EA tests.

Built and run headless with the same pipeline as the dam breaks
(``run_hecras_2d.py``: GeoTIFF terrain through ``RasProcess CreateTerrain``,
a mesh from cell-centre seed points in the geometry text, ``ras-commander``
to preprocess and compute), plus what these cases add:

* **Boundary lines** in the geometry text (``BC Line ...``) and their
  hydrographs in the unsteady-flow text: a flow hydrograph on an inflow line,
  a stage hydrograph on a level boundary. A line on the edge of the area is
  drawn a hair outside it, as RAS Mapper does; an inflow line inside the area
  (EA Test 5) is an internal boundary line.
* **Terrain**: the case's own DEM where it has one (EA 1, 2, 5: the EA
  archive's 2 m or 10 m raster, so HEC-RAS uses its sub-grid terrain as it
  normally would); a fine raster of the exact bed for MacDonald 2D; flat for
  EA 4. The mesh cells are the cell centres every other solver uses.
* **Output**: HEC-RAS writes the results HDF at its *mapping* interval, so
  that is set to the output interval (the probe interval for the EA tests).
  A run restarted at 00:01 needs an output interval that divides 00:01, so
  MacDonald 2D writes every minute.
* **Initial state**: EA 1 starts from its water level (``Initial Storage
  Elev``); EA 2, 4 and 5 start dry. MacDonald 2D starts at a uniform depth
  over a sloping bed, which one level cannot express, so a short still-water
  run writes a restart file whose per-cell water surface is then set to
  bed + depth (the dam breaks' restart-file method).
* **Depth reported**: HEC-RAS cells are sub-grid (a flat water surface over
  the terrain inside the cell), so the depth written to the results is the
  cell's water volume over its plan area, computed from the same terrain
  pixels, and the bed is the cell's mean ground level. Volumes are exactly
  HEC-RAS's; where a cell is fully wet, depth + bed is HEC-RAS's water level.

Usage (Windows, HEC-RAS 6.6)::

    python scripts/run_hecras_2d_cases.py --accept-hec-terms [--equations elm em] [CASE ...]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

import run_hecras_2d as base  # noqa: E402
from run_hecras_2d import AREA, EQUATIONS, OUT, START, TS, X0, Y0, _crlf, _xy16, compute, log  # noqa: E402

# EA Test 4 at the specification's 5 m (HEC-RAS is fast enough).
EA_CASES = ("A2C-EA1", "A2C-EA2", "A2C-EA4", "A2C-EA5")


def demo():
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_demo_2d", REPO / "scripts" / "run_demo_2d.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── text files ──────────────────────────────────────────────────────────────


def f8(v: float) -> str:
    """A number in HEC-RAS's 8-character hydrograph field, as precise as fits."""
    for p in (4, 3, 2, 1, 0):
        s = f"{v:8.{p}f}"
        if len(s) <= 8:
            return s
    raise ValueError(f"{v} does not fit an 8-character field")


def interval(seconds: float) -> str:
    table = {1: "1SEC", 2: "2SEC", 5: "5SEC", 10: "10SEC", 15: "15SEC", 20: "20SEC", 30: "30SEC", 60: "1MIN",
             120: "2MIN", 300: "5MIN", 600: "10MIN", 900: "15MIN", 1800: "30MIN", 3600: "1HOUR"}
    s = int(round(seconds))
    if s not in table:
        raise ValueError(f"no HEC-RAS interval for {seconds} s")
    return table[s]


def date_clock(seconds: float) -> tuple[str, str]:
    """HEC-RAS date and HHMM clock ``seconds`` after the start (01JAN2000 00:00)."""
    import datetime as dt

    t = dt.datetime(2000, 1, 1) + dt.timedelta(seconds=round(seconds))
    if t.second:
        raise ValueError("HEC-RAS plan times are whole minutes")
    return t.strftime("%d%b%Y").upper(), t.strftime("%H%M")


def write_geometry(path: Path, title: str, perim: np.ndarray, seeds: np.ndarray, dx: float, n: float,
                   bc_lines: dict[str, np.ndarray]) -> None:
    """One 2D flow area: perimeter polygon, seed points and boundary lines (case coordinates)."""
    P = np.asarray(perim, float) + (X0, Y0)
    if not np.allclose(P[0], P[-1]):
        P = np.vstack([P, P[:1]])
    S = np.asarray(seeds, float) + (X0, Y0)
    seed_lines = ["".join(_xy16(*p) for p in S[i:i + 2]) for i in range(0, len(S), 2)]
    lo, hi = P.min(0), P.max(0)
    c = (lo + hi) / 2
    lines = [f"Geom Title={title}", "Program Version=6.60",
             f"Viewing Rectangle= {lo[0] - dx} , {hi[0] + dx} , {hi[1] + dx} , {lo[1] - dx} ", "",
             f"Storage Area={AREA:<16},{c[0]},{c[1]}", f"Storage Area Surface Line= {len(P)} ",
             *[_xy16(*p) for p in P],
             "Storage Area Type= 0 ", "Storage Area Area=", "Storage Area Min Elev=", "Storage Area Is2D=-1",
             f"Storage Area Point Generation Data=,,{dx:g},{dx:g}", f"Storage Area 2D Points= {len(S)} ",
             *seed_lines,
             "Storage Area 2D PointsPerimeterTime=01Jan2000 00:00:00", f"Storage Area Mannings={n:g}",
             "2D Cell Volume Filter Tolerance=0.003", "2D Cell Minimum Area Fraction=0.01",
             "2D Face Profile Filter Tolerance=0.003", "2D Face Area Elevation Profile Filter Tolerance=0.003",
             "2D Face Area Elevation Conveyance Ratio=0.02", "2D Face Area Laminar Depth=0.2", ""]
    for name, pts in bc_lines.items():
        Q = np.asarray(pts, float) + (X0, Y0)
        mid = Q[len(Q) // 2] if len(Q) > 2 else Q.mean(0)
        arc = ["".join(_xy16(*p) for p in Q[i:i + 2]) for i in range(0, len(Q), 2)]
        lines += [f"BC Line Name={name:<32}", f"BC Line Storage Area={AREA:<16}",
                  f"BC Line Start Position= {Q[0][0]} , {Q[0][1]} ", f"BC Line Middle Position= {mid[0]} , {mid[1]} ",
                  f"BC Line End Position= {Q[-1][0]} , {Q[-1][1]} ", f"BC Line Arc= {len(Q)} ", *arc,
                  f"BC Line Text Position= {mid[0]} , {mid[1]} "]
    lines += ["LCMann Time=Dec/30/1899 00:00:00", "LCMann Region Time=Dec/30/1899 00:00:00", "LCMann Table=0",
              "Chan Stop Cuts=-1", "", ""]
    _crlf(path, lines)


def write_unsteady(path: Path, title: str, ic_level: float | None, restart: str | None, bcs: list[dict]) -> None:
    lines = [f"Flow Title={title}", "Program Version=6.60"]
    if restart:
        lines += ["Use Restart=-1 ", f"Restart Filename={restart}"]
    else:
        lines += ["Use Restart= 0 "]
        if ic_level is not None:
            lines += [f"Initial Storage Elev={AREA:<16},{ic_level:g}"]
    for bc in bcs:
        vals = [f8(v) for v in bc["values"]]
        lines += [f"Boundary Location=                ,                ,        ,        ,                ,{AREA:<16},                ,{bc['name']:<32}",
                  f"Interval={bc['interval']}",
                  f"{'Flow' if bc['kind'] == 'flow' else 'Stage'} Hydrograph= {len(vals)} ",
                  *["".join(vals[i:i + 10]) for i in range(0, len(vals), 10)],
                  "Stage Hydrograph TW Check=0"]
        if bc["kind"] == "flow":
            lines += [f"Flow Hydrograph Slope= {bc.get('slope', 0.001):g} "]
        lines += ["DSS Path=", "Use DSS=False", "Use Fixed Start Time=False", "Fixed Start Date/Time=,",
                  "Is Critical Boundary=False", "Critical Boundary Flow="]
    lines += ["Precipitation Mode=Disable", "Wind Mode=No Wind Forces", "Air Density Mode=",
              "Met BC=Precipitation|Mode=None", "Met BC=Evapotranspiration|Mode=None"]
    _crlf(path, lines)


def hydrograph(tt: np.ndarray, vv: np.ndarray, t_end: float, step: float) -> list[float]:
    t = np.arange(0.0, t_end + step / 2 + step, step)  # one value past the end
    return list(np.interp(t, tt, vv))


# ── restart and results ─────────────────────────────────────────────────────


def patch_restart_ws(rst: Path, level: float, target: np.ndarray, n_real: int) -> list[str]:
    """Replace the flat still-water surface (``level`` m) in a restart file by ``target`` (m, per cell).

    Same search as the dam breaks' ``patch_restart``: the run of ``n_real``
    equal doubles that reads ``level`` in metres or HEC-RAS's internal feet.
    """
    buf = bytearray(rst.read_bytes())
    edited = []
    target = np.asarray(target, float)
    for align in range(8):
        arr = np.frombuffer(bytes(buf[align:align + (len(buf) - align) // 8 * 8]), dtype="<f8")
        ok = np.isfinite(arr) & (np.abs(arr) > 1e-3) & (np.abs(arr) < 1e5)
        i = 0
        while i < len(arr):
            if not ok[i]:
                i += 1
                continue
            v = arr[i]
            j = i
            while j < len(arr) and ok[j] and abs(arr[j] - v) <= 1e-6 * abs(v):
                j += 1
            ratio = float(v) / level
            if j - i >= n_real and (abs(ratio - 1) < 1e-3 or abs(ratio / 3.280839895 - 1) < 1e-3):
                k = min(j - i, len(target))
                new = np.where(np.isfinite(target[:k]), target[:k] * ratio, arr[i:i + k]).astype("<f8")
                buf[align + i * 8:align + (i + k) * 8] = new.tobytes()
                edited.append(f"{j - i} doubles at byte {align + i * 8} (stored {v:.6g} = {level:g} m), {k} set")
            i = max(j, i + 1)
    if edited:
        rst.write_bytes(bytes(buf))
    return edited


def read_results(hdf: Path, ghdf: Path) -> dict:
    import h5py

    with h5py.File(ghdf, "r") as g:
        b = f"Geometry/2D Flow Areas/{AREA}"
        centres = g[f"{b}/Cells Center Coordinate"][()]
        n_real = int(g["Geometry/2D Flow Areas/Cell Points"].shape[0])
    with h5py.File(hdf, "r") as f:
        ts = "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series"
        days = f[f"{ts}/Time"][()]
        a = f[f"{ts}/2D Flow Areas/{AREA}"]
        ws = a["Water Surface"][()][:, :n_real]
        vx = vy = None
        for key in a:
            kl = key.lower()
            if "cell velocity" in kl and kl.endswith("x"):
                vx = a[key][()][:, :n_real]
            if "cell velocity" in kl and kl.endswith("y"):
                vy = a[key][()][:, :n_real]
        msgs = f["Results/Summary/Compute Messages (text)"][0].decode(errors="replace")
        # HEC-RAS's own volume accounting, for comparison with the depths reported
        acc = []
        def visit(name, obj):
            if "olume" in name and ("ccounting" in name or "Summary" in name):
                if hasattr(obj, "attrs") and obj.attrs:
                    acc.append(f"{name}: " + ", ".join(f"{k}={v}" for k, v in obj.attrs.items()))
                if hasattr(obj, "shape") and obj.size <= 64:
                    acc.append(f"{name} = {obj[()]!r}")
        f.visititems(visit)
        log("    HEC-RAS volume accounting:\n      " + "\n      ".join(acc[:40]))
    return {"t": (days - days[0]) * 86400.0, "ws": ws, "vx": vx, "vy": vy, "xy": centres[:n_real] - (X0, Y0),
            "n_real": n_real, "messages": msgs}


class Pixels:
    """Terrain pixels behind each mesh cell, for volume-equivalent depths."""

    def __init__(self, zpix: np.ndarray, x0: float, y0: float, pix: float, gx: np.ndarray, gy: np.ndarray,
                 inside: np.ndarray | None = None):
        dx = float(gx[1] - gx[0]) if gx.size > 1 else float(gy[1] - gy[0])
        f = int(round(dx / pix))
        i0 = int(round((gx[0] - dx / 2 - x0) / pix))
        j0 = int(round((gy[0] - dx / 2 - y0) / pix))
        sub = zpix[j0:j0 + gy.size * f, i0:i0 + gx.size * f]  # row 0 = south
        self.blocks = sub.reshape(gy.size, f, gx.size, f).transpose(0, 2, 1, 3).reshape(gy.size, gx.size, f * f)
        if inside is not None:
            m = inside[j0:j0 + gy.size * f, i0:i0 + gx.size * f]
            self.mask = m.reshape(gy.size, f, gx.size, f).transpose(0, 2, 1, 3).reshape(gy.size, gx.size, f * f)
        else:
            self.mask = np.ones_like(self.blocks, dtype=bool)
        self.f = f

    def zmean(self, j: np.ndarray, i: np.ndarray) -> np.ndarray:
        """Mean ground level of the pixels behind cells (j, i)."""
        z = self.blocks[j, i]
        m = self.mask[j, i] & np.isfinite(z)
        return np.where(m, z, 0.0).sum(1) / np.maximum(m.sum(1), 1)

    def depth(self, j: np.ndarray, i: np.ndarray, ws: np.ndarray) -> np.ndarray:
        """Volume over plan area for cells (j, i) at water surfaces ``ws``."""
        z = self.blocks[j, i]
        m = self.mask[j, i] & np.isfinite(z)
        wet = np.where(m, np.maximum(ws[:, None] - z, 0.0), 0.0)
        return wet.sum(1) / np.maximum(m.sum(1), 1)


# ── one run ─────────────────────────────────────────────────────────────────


def build_and_run(tag: str, eq: str, ras_exe: Path, *, perim, seeds, dx, n, bc_lines, terrain, t_end: float,
                  out_dt: float, bcs_main: list[dict], ic_level: float | None = None,
                  restart: tuple[float, np.ndarray, list[dict]] | None = None, dt: str = "1SEC") -> dict:
    """Write the project, run it and return the results. ``terrain`` = (z north-up, xmin, ymax, cell).

    ``restart`` = (still level, target water surface per seed, boundary
    conditions of the still-water run): a one-minute still-water run first,
    its restart file patched to the target, then the main run from it.
    """
    import h5py

    folder = OUT / "work" / eq / tag
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    name = "Case"
    plans = ["01", "02"] if restart else ["01"]
    base.write_project(folder, name, tag, plans, plans)
    base.write_rasmap(folder, name)
    write_geometry(folder / f"{name}.g01", tag, perim, seeds, dx, n, bc_lines)
    tz, txmin, tymax, tcell = terrain
    tif_terrain = base.create_terrain(folder, ras_exe.parent, tz, txmin, tymax, tcell)
    eq_code = EQUATIONS[eq][0]
    if restart:
        level, target, bcs_still = restart
        write_unsteady(folder / f"{name}.u01", "still water", level, None, bcs_still)
        base.write_plan(folder / f"{name}.p01", "Still water (restart)", "init", "01", "0000", "0001", dt, "1MIN", True, eq_code)
        write_unsteady(folder / f"{name}.u02", "main", None, "PLACEHOLDER", bcs_main)
        d1, c1 = date_clock(60.0 + t_end)
        base.write_plan(folder / f"{name}.p02", "Main", "main", "02", "0001", c1, dt, interval(out_dt), False, eq_code,
                        end_date=d1, map_dt=interval(out_dt))
    else:
        write_unsteady(folder / f"{name}.u01", "main", ic_level, None, bcs_main)
        d1, c1 = date_clock(t_end)
        base.write_plan(folder / f"{name}.p01", "Main", "main", "01", "0000", c1, dt, interval(out_dt), False, eq_code,
                        end_date=d1, map_dt=interval(out_dt))
    log(f"    project {tag}: {len(seeds)} seeds, {len(bc_lines)} boundary lines, terrain {tz.shape[1]}x{tz.shape[0]} at {tcell:g} m")
    base.preprocess_and_associate(folder, ras_exe, tif_terrain)
    main_plan = "01"
    if restart:
        hdf1 = compute(folder, ras_exe, "01", 900)
        rst = sorted(folder.glob("*.rst"))
        if hdf1 is None or not rst:
            log(base.listing(folder))
            log(base.messages(folder))
            raise RuntimeError("the still-water run wrote no restart file")
        with h5py.File(folder / f"{name}.g01.hdf", "r") as g:
            centres = g[f"Geometry/2D Flow Areas/{AREA}/Cells Center Coordinate"][()] - (X0, Y0)
            n_real = int(g["Geometry/2D Flow Areas/Cell Points"].shape[0])
        # target per HEC-RAS cell, by its nearest seed
        k = nearest(seeds, centres[:n_real])
        edited = patch_restart_ws(rst[-1], level, target[k], n_real)
        log(f"    restart {rst[-1].name}: {edited}")
        if not edited:
            raise RuntimeError("no per-cell water surface found in the restart file")
        write_unsteady(folder / f"{name}.u02", "main", None, rst[-1].name, bcs_main)
        main_plan = "02"
    t0 = time.perf_counter()
    hdf = compute(folder, ras_exe, main_plan, 4 * 3600)
    log(f"    main run: {time.perf_counter() - t0:.0f} s")
    if hdf is None:
        log(base.listing(folder))
        log(base.messages(folder))
        raise RuntimeError("the main run wrote no results")
    res = read_results(hdf, folder / f"{name}.g01.hdf")
    if EQUATIONS[eq][1] not in res["messages"]:
        raise RuntimeError(f"HEC-RAS did not run {EQUATIONS[eq][1]}:\n{res['messages'][:1500]}")
    log(f"    {res['n_real']} cells, {len(res['t'])} output times up to {res['t'][-1]:.0f} s")
    return res


def nearest(seeds: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Index of the nearest seed for each point (seeds on a regular grid)."""
    from scipy.spatial import cKDTree

    return cKDTree(np.asarray(seeds)).query(np.asarray(pts))[1]


# ── cases ───────────────────────────────────────────────────────────────────


def macdonald_2d(m: dict, dx: float, eq: str, ras_exe: Path) -> dict:
    from references.macdonald_2d import bed_elevation, depth_profile

    prm = m["reference"]["generator"]["parameters"]
    L, W, q, n = prm["L"], prm["W"], prm["q"], prm["n_manning"]
    t_end = float(m["simulation"]["t_end"])
    xs = np.arange(dx / 2, L - dx / 4, dx)
    ys = np.arange(W / max(round(W / dx), 1) / 2, W, W / max(round(W / dx), 1))
    X, Y = np.meshgrid(xs, ys)
    seeds = np.column_stack([X.ravel(), Y.ravel()])
    pix = dx / max(1, math.ceil(dx / 1.0))
    margin = 2 * dx
    px = np.arange(-margin + pix / 2, L + margin, pix)
    py = np.arange(-margin + pix / 2, W + margin, pix)
    zrow = bed_elevation(np.clip(px, 0.0, L), L=L, q=q, n_manning=n)
    zpix = np.tile(zrow, (py.size, 1))  # row 0 = south
    terrain = (zpix[::-1], -margin, W + margin, pix)
    h_out = float(depth_profile(L))
    z_out = float(bed_elevation(L, L=L, q=q, n_manning=n))
    sf_in = n * n * q * q / float(depth_profile(0.0)) ** (10.0 / 3.0)  # friction slope at the inlet
    e = 0.01 * dx
    bc_lines = {"Inflow": np.array([[-e, 0.0], [-e, W]]), "Outflow": np.array([[L + e, 0.0], [L + e, W]])}
    still = float(zrow.max()) + 1.0
    bcs_still = [dict(name="Inflow", kind="flow", interval="1HOUR", values=[0.0, 0.0, 0.0], slope=sf_in),
                 dict(name="Outflow", kind="stage", interval="1HOUR", values=[still] * 3)]
    bcs_main = [dict(name="Inflow", kind="flow", interval="1HOUR", values=[q * W] * 3, slope=sf_in),
                dict(name="Outflow", kind="stage", interval="1HOUR", values=[z_out + h_out] * 3)]
    zc = bed_elevation(seeds[:, 0], L=L, q=q, n_manning=n)
    res = build_and_run(f"A2A-010_dx{dx:g}", eq, ras_exe, perim=np.array([[0, W], [L, W], [L, 0], [0, 0], [0, W]], float),
                        seeds=seeds, dx=dx, n=n, bc_lines=bc_lines, terrain=terrain, t_end=t_end, out_dt=60.0,
                        bcs_main=bcs_main, restart=(still, zc + h_out, bcs_still), dt="1SEC")
    k = int(np.argmin(np.abs(res["t"] - t_end)))
    log(f"    result time {res['t'][k]:.0f} s (wanted {t_end:g})")
    pixels = Pixels(zpix, -margin, -margin, pix, xs, ys)
    jj = np.clip(((res["xy"][:, 1] - ys[0]) / (ys[1] - ys[0] if ys.size > 1 else dx)).round().astype(int), 0, ys.size - 1)
    ii = np.clip(((res["xy"][:, 0] - xs[0]) / dx).round().astype(int), 0, xs.size - 1)
    ws = res["ws"][k]
    h = pixels.depth(jj, ii, ws)
    nn = len(ws)
    return {"t": np.full(nn, res["t"][k]), "x": xs[ii], "y": ys[jj], "h": h,
            "u": res["vx"][k] if res["vx"] is not None else np.full(nn, np.nan),
            "v": res["vy"][k] if res["vy"] is not None else np.full(nn, np.nan), "p": np.full(nn, np.nan),
            "z": pixels.zmean(jj, ii)}


def ea(m: dict, tid: str, eq: str, ras_exe: Path) -> dict:
    from matplotlib.path import Path as MPath

    dm = demo()
    d = Path(m["_case_dir"])
    prm = json.loads((d / "inputs/case.json").read_text())
    case, _h, probe_dt = dm.build_ea(m)  # the specification's resolution (EA 4 at 5 m)
    gx, gy = np.asarray(case.grid.x, float), np.asarray(case.grid.y, float)
    dx = float(gx[1] - gx[0])
    act = np.asarray(case.grid.active, bool)
    J, I = np.nonzero(act)
    seeds = np.column_stack([gx[I], gy[J]])
    t_end = float(prm["t_end_s"])
    n = float(prm["manning_n"])
    if tid.startswith("A2C-EA4"):
        dom = prm["domain"]
        perim = np.array([[0, dom["ymax"]], [dom["xmax"], dom["ymax"]], [dom["xmax"], 0], [0, 0], [0, dom["ymax"]]], float)
        margin = 2 * dx
        nx, ny = int(round((dom["xmax"] + 2 * margin) / dx)), int(round((dom["ymax"] + 2 * margin) / dx))
        zpix = np.zeros((ny, nx))
        pix, px0, py0 = dx, -margin, -margin
        inside = None
    else:
        hdr, dem = dm.read_asc(d / "inputs/terrain.asc")  # row 0 = south
        pix, px0, py0 = hdr["cellsize"], hdr["xllcorner"], hdr["yllcorner"]
        zpix = np.where(np.isfinite(dem), dem, np.nanmax(dem) + 50.0)
        shp = d / "inputs/active_area.shp"
        if shp.is_file():
            ring = dm.read_polygon(shp)
            perim = ring if np.allclose(ring[0], ring[-1]) else np.vstack([ring, ring[:1]])
            PX, PY = np.meshgrid(px0 + pix * (np.arange(dem.shape[1]) + 0.5), py0 + pix * (np.arange(dem.shape[0]) + 0.5))
            inside = MPath(ring).contains_points(np.c_[PX.ravel(), PY.ravel()]).reshape(PX.shape)
        else:
            dom = prm["domain"]
            perim = np.array([[dom["xmin"], dom["ymax"]], [dom["xmax"], dom["ymax"]], [dom["xmax"], dom["ymin"]],
                              [dom["xmin"], dom["ymin"]], [dom["xmin"], dom["ymax"]]], float)
            inside = None
    terrain = (zpix[::-1], px0, py0 + pix * zpix.shape[0], pix)
    bc = prm["boundaries"]
    bc_lines, bcs = {}, []
    e = 0.01 * dx
    step = 60.0
    if "west" in bc:
        tt, lv = dm.read_table(d / "inputs" / bc["west"]["table"])
        x_w = float(perim[:, 0].min())
        bc_lines["West"] = np.array([[x_w - e, perim[:, 1].min()], [x_w - e, perim[:, 1].max()]])
        bcs.append(dict(name="West", kind="stage", interval=interval(step), values=hydrograph(tt, lv, t_end, step)))
    if "inflow" in bc:
        tt, qq = dm.read_table(d / "inputs" / bc["inflow"]["table"])
        a, b = np.asarray(bc["inflow"]["line"], float)
        on_edge = np.isclose(a[0], b[0]) and np.isclose(a[0], perim[:, 0].min())
        if on_edge:
            a, b = a - (e, 0.0), b - (e, 0.0)
        bc_lines["Inflow"] = np.array([a, b])
        bcs.append(dict(name="Inflow", kind="flow", interval=interval(step), values=hydrograph(tt, qq, t_end, step), slope=0.001))
    ic = float(prm["initial_condition"]["water_level_m"]) if isinstance(prm.get("initial_condition"), dict) else None
    res = build_and_run(tid, eq, ras_exe, perim=perim, seeds=seeds, dx=dx, n=n, bc_lines=bc_lines, terrain=terrain,
                        t_end=t_end, out_dt=probe_dt, bcs_main=bcs, ic_level=ic, dt="1SEC")
    pixels = Pixels(zpix, px0, py0, pix, gx, gy, inside)
    ii = np.clip(((res["xy"][:, 0] - gx[0]) / dx).round().astype(int), 0, gx.size - 1)
    jj = np.clip(((res["xy"][:, 1] - gy[0]) / dx).round().astype(int), 0, gy.size - 1)
    keep = act[jj, ii]
    probes = m["simulation"]["probes"]
    pc = []
    for p in probes:
        i = int(np.clip((p["x"] - (gx[0] - dx / 2)) // dx, 0, gx.size - 1))
        j = int(np.clip((p.get("y", 0.0) - (gy[0] - dx / 2)) // dx, 0, gy.size - 1))
        hit = np.flatnonzero((ii == i) & (jj == j))
        if hit.size:
            pc.append(int(hit[0]))
    pc = np.array(pc, int)
    frames = []
    for k, t in enumerate(res["t"]):
        hourly = abs(t / 3600.0 - round(t / 3600.0)) < 1e-6
        sel = np.flatnonzero(keep) if hourly else pc
        ws = res["ws"][k, sel]
        h = pixels.depth(jj[sel], ii[sel], ws)
        nn = sel.size
        u = res["vx"][k, sel] if res["vx"] is not None else np.full(nn, np.nan)
        v = res["vy"][k, sel] if res["vy"] is not None else np.full(nn, np.nan)
        frames.append({"t": np.full(nn, t), "x": gx[ii[sel]], "y": gy[jj[sel]], "h": h, "u": u, "v": v,
                       "p": np.full(nn, np.nan), "z": pixels.zmean(jj[sel], ii[sel])})
    return {c: np.concatenate([f[c] for f in frames]) for c in frames[0]}


def main() -> int:
    from run_hecras import accept_terms, find_ras_exe

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=["A2A-010", *EA_CASES])
    ap.add_argument("--ras-exe", type=Path)
    ap.add_argument("--accept-hec-terms", action="store_true")
    ap.add_argument("--equations", nargs="+", choices=list(EQUATIONS), default=list(EQUATIONS))
    ap.add_argument("--coarsest-only", action="store_true", help="MacDonald 2D: coarsest grid only (a smoke test)")
    args = ap.parse_args()

    from benchmark1d2d.signing import private_key as signing_key

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    ras_exe = args.ras_exe or find_ras_exe()
    log(f"HEC-RAS: {ras_exe}")
    if args.accept_hec_terms:
        accept_terms(ras_exe)
    version = ras_exe.parent.name
    key = signing_key()  # BENCH_SIGNING_KEY, else the public development key
    failed = 0
    for eq in args.equations:
        label = EQUATIONS[eq][1]
        solver = {"name": f"HEC-RAS {version} 2D {label}", "version": version,
                  "adapter": f"hecras 2D (headless terrain + seeded mesh + boundary lines, {label}; depth = cell volume / area)"}
        out = OUT / eq
        out.mkdir(parents=True, exist_ok=True)
        for tid in args.cases:
            m = load_manifest(tid, repo=REPO)
            t0 = time.perf_counter()
            try:
                if tid.startswith(EA_CASES):
                    log(f"  {label} {tid}")
                    p = write_results_parquet(out / f"{m['test_id']}.parquet", ea(m, tid, eq, ras_exe), wall_seconds=time.perf_counter() - t0)
                    card = score_case(m, p, timestamp=TS, private_key=key, solver=solver)
                else:
                    levels = sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True)
                    if args.coarsest_only:
                        levels = levels[:1]
                    paths = []
                    for dx in levels:
                        log(f"  {label} {tid} dx={dx}")
                        t1 = time.perf_counter()
                        paths.append(write_results_parquet(out / f"{m['test_id']}_dx{dx:g}.parquet", macdonald_2d(m, float(dx), eq, ras_exe),
                                                           wall_seconds=time.perf_counter() - t1))
                    if len(paths) < 2:
                        continue
                    card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                failed += 1
                continue
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            log(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']}) in {time.perf_counter() - t0:.0f} s")
            for r in card["criteria_results"]:
                log(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}  {r.get('detail', '')}")
            c = card.get("convergence_result") or {}
            if c:
                log(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
    return 1 if failed else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
