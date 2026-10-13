#!/usr/bin/env python3
"""Run the demo 2D finite-volume solver on Thacker and the EA cases, then score.

This is the end-to-end proof that 2D cases can be set up from their committed
and fetched inputs alone, run by a real solver (``examples/demo_solver/swe2d.py``),
and scored. Results and score cards land in ``out/demo_2d/``.

Usage::

    python scripts/fetch_inputs.py && python scripts/run_demo_2d.py            # all
    python scripts/run_demo_2d.py A2C-EA4 A2A-001                                 # some
"""

from __future__ import annotations

import csv
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "examples" / "demo_solver")]

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from benchmark1d2d.catalog import load_manifest  # noqa: E402
from benchmark1d2d.io.results import write_results_parquet  # noqa: E402
from benchmark1d2d.scoring.scorer import ReferenceUnavailable, score_case  # noqa: E402
from swe2d import WALL_Z, Case, Grid, run  # noqa: E402

OUT = REPO / "out" / "demo_2d"
SOLVER = {"name": "demo-swe2d (first-order FV, HLL + hydrostatic reconstruction)", "version": "0.1.0", "adapter": "generic_parquet"}
KEY = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))
TS = "2024-01-01T00:00:00Z"


# ── input readers ───────────────────────────────────────────────────────────


def read_asc(path: Path) -> tuple[dict[str, float], np.ndarray]:
    with path.open() as fh:
        hdr = {}
        for _ in range(6):
            k, v = fh.readline().split()
            hdr[k.lower()] = float(v)
        z = np.loadtxt(fh)
    z[z == hdr.get("nodata_value", -9999)] = np.nan
    return hdr, np.flipud(z)  # row 0 = south


def read_polygon(path: Path) -> np.ndarray:
    """First ring of the first polygon in an ESRI .shp (no dependencies)."""
    data = path.read_bytes()
    off = 100 + 8  # file header + record header
    shape_type = struct.unpack("<i", data[off : off + 4])[0]
    if shape_type != 5:
        raise ValueError(f"expected polygon shape type 5, got {shape_type}")
    num_parts, num_points = struct.unpack("<2i", data[off + 36 : off + 44])
    pts_off = off + 44 + 4 * num_parts
    pts = np.frombuffer(data[pts_off : pts_off + 16 * num_points], dtype="<f8").reshape(-1, 2)
    return pts


def read_table(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = [r for r in csv.reader(path.open(encoding="utf-8-sig")) if r][1:]
    return np.array([float(r[0]) * 60.0 for r in rows]), np.array([float(r[1]) for r in rows])


def block_mean(hdr, z, x0, x1, y0, y1, dx):
    """Resample a DEM onto a dx grid over [x0,x1]×[y0,y1] by block averaging."""
    cs = hdr["cellsize"]
    f = int(round(dx / cs))
    i0 = int(round((x0 - hdr["xllcorner"]) / cs))
    j0 = int(round((y0 - hdr["yllcorner"]) / cs))
    nx = int(round((x1 - x0) / dx))
    ny = int(round((y1 - y0) / dx))
    sub = z[j0 : j0 + ny * f, i0 : i0 + nx * f]
    with np.errstate(invalid="ignore"):
        zz = np.nanmean(sub.reshape(ny, f, nx, f), axis=(1, 3))
    x = x0 + dx * (np.arange(nx) + 0.5)
    y = y0 + dx * (np.arange(ny) + 0.5)
    return x, y, zz


def probe_cells(manifest, grid: Grid) -> dict[str, tuple[int, int]]:
    out = {}
    for p in manifest["simulation"].get("probes") or []:
        i = int(np.argmin(np.abs(grid.x - p["x"])))
        j = int(np.argmin(np.abs(grid.y - p.get("y", 0.0))))
        out[p["id"]] = (j, i)
    return out


def segment_cells(grid: Grid, a, b, width: float) -> np.ndarray:
    X, Y = np.meshgrid(grid.x, grid.y)
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    t = np.clip(((X - ax) * vx + (Y - ay) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
    d = np.hypot(X - (ax + t * vx), Y - (ay + t * vy))
    return (d <= width) & grid.active


# ── case builders ───────────────────────────────────────────────────────────


def build_thacker(manifest, dx: float) -> tuple[Case, list[float], float | None]:
    from references.thacker import bed_elevation, depth_velocity

    prm = manifest["reference"]["generator"]["parameters"]
    dom = json.loads((Path(manifest["_case_dir"]) / "inputs/params.json").read_text())["domain"]
    nx = int(round((dom["xmax"] - dom["xmin"]) / dx))
    x = dom["xmin"] + dx * (np.arange(nx) + 0.5)
    y = dom["ymin"] + dx * (np.arange(nx) + 0.5)
    X, Y = np.meshgrid(x, y)
    z = bed_elevation(X, Y, prm["h0"], prm["L"])
    sol = depth_velocity(X, Y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", 9.81))
    grid = Grid(x, y, z, np.ones_like(z, dtype=bool))
    case = Case(grid, sol["h"], np.zeros_like(z), np.zeros_like(z), t_end=float(manifest["simulation"]["t_end"]))
    return case, [], None


def build_ea(manifest, dx_override: float | None = None) -> tuple[Case, list[float], float | None]:
    d = Path(manifest["_case_dir"])
    prm = json.loads((d / "inputs/case.json").read_text())
    dx = dx_override or prm["grid_resolution_m"]
    t_end = float(prm["t_end_s"])
    tid = manifest["test_id"]
    if tid.startswith("A2C-EA4"):
        dom = prm["domain"]
        nx, ny = int(dom["xmax"] / dx), int(dom["ymax"] / dx)
        x = dx * (np.arange(nx) + 0.5)
        y = dx * (np.arange(ny) + 0.5)
        z = np.zeros((ny, nx))
        active = np.ones_like(z, dtype=bool)
    else:
        hdr, dem = read_asc(d / "inputs/terrain.asc")
        if "domain" in prm:
            dom = prm["domain"]
            x0, x1, y0, y1 = dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"]
        else:
            poly = read_polygon(d / "inputs/active_area.shp")
            x0, y0 = np.floor(poly.min(axis=0) / dx) * dx
            x1, y1 = np.ceil(poly.max(axis=0) / dx) * dx
            x0 = max(x0, hdr["xllcorner"]); y0 = max(y0, hdr["yllcorner"])
            x1 = min(x1, hdr["xllcorner"] + hdr["cellsize"] * hdr["ncols"]); y1 = min(y1, hdr["yllcorner"] + hdr["cellsize"] * hdr["nrows"])
            x0 = hdr["xllcorner"] + np.ceil((x0 - hdr["xllcorner"]) / dx) * dx
            y0 = hdr["yllcorner"] + np.ceil((y0 - hdr["yllcorner"]) / dx) * dx
            x1 = x0 + np.floor((x1 - x0) / dx) * dx
            y1 = y0 + np.floor((y1 - y0) / dx) * dx
        x, y, z = block_mean(hdr, dem, x0, x1, y0, y1, dx)
        active = np.isfinite(z)
        shp = d / "inputs/active_area.shp"
        if shp.is_file():
            from matplotlib.path import Path as MPath

            X, Y = np.meshgrid(x, y)
            inside = MPath(read_polygon(shp)).contains_points(np.c_[X.ravel(), Y.ravel()]).reshape(X.shape)
            active &= inside
        z = np.where(active, z, WALL_Z)
    grid = Grid(x, y, z, active)
    h = np.zeros_like(z)
    case = Case(grid, h, np.zeros_like(z), np.zeros_like(z), manning_n=float(prm["manning_n"]), t_end=t_end)
    bc = prm["boundaries"]
    if "west" in bc:  # EA1 water-level boundary
        tt, lv = read_table(d / "inputs" / bc["west"]["table"])
        case.west_level = lambda t, tt=tt, lv=lv: float(np.interp(t, tt, lv))
        h0 = prm["initial_condition"]["water_level_m"]
        case.h = np.where(active, np.maximum(0.0, h0 - z), 0.0)
    if "inflow" in bc:
        tt, qq = read_table(d / "inputs" / bc["inflow"]["table"])
        case.inflow = lambda t, tt=tt, qq=qq: float(np.interp(t, tt, qq))
        a, b = bc["inflow"]["line"]
        case.inflow_cells = segment_cells(grid, a, b, 0.75 * dx)
        if not case.inflow_cells.any():
            raise SystemExit(f"{tid}: inflow line hits no active cell")
    case.probes = probe_cells(manifest, grid)
    hours = np.arange(0.0, t_end + 1.0, 3600.0).tolist()
    return case, hours, float(prm["outputs"]["probe_interval_s"])


# ── driver ──────────────────────────────────────────────────────────────────


def to_parquet(cols, path: Path) -> Path:
    cols = {k: v for k, v in cols.items() if k != "steps"}
    return write_results_parquet(path, cols)


def run_thacker() -> dict:
    m = load_manifest("A2A-001", repo=REPO)
    paths = []
    for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
        case, ft, pi = build_thacker(m, dx)
        t0 = time.perf_counter()
        cols = run(case, ft, pi)
        p = to_parquet(cols, OUT / f"A2A-001_thacker_dx{dx}.parquet")
        print(f"  A2A-001 dx={dx}: {cols['steps']} steps in {time.perf_counter() - t0:.1f}s")
        paths.append(p)
    card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=KEY, solver=SOLVER)
    return card


# The EA specification allows "1 alternative resolution or mesh"; the demo uses
# 10 m for Test 4 (spec 5 m) to keep CI under a few minutes. Mass conservation,
# the gating check, does not depend on resolution.
DEMO_DX = {"A2C-EA4": 10.0}


def run_ea(prefix: str) -> dict:
    m = load_manifest(prefix, repo=REPO)
    dx = next((v for k, v in DEMO_DX.items() if m["test_id"].startswith(k)), None)
    case, ft, pi = build_ea(m, dx)
    t0 = time.perf_counter()
    print(f"  {m['test_id']}: grid {case.grid.z.shape[1]}×{case.grid.z.shape[0]} ({int(case.grid.active.sum())} active cells)")
    cols = run(case, ft, pi, progress=True)
    p = to_parquet(cols, OUT / f"{m['test_id']}.parquet")
    print(f"  {m['test_id']}: {cols['steps']} steps in {time.perf_counter() - t0:.0f}s")
    solver = dict(SOLVER)
    if dx:
        solver["name"] += f" at {dx:g} m (spec alternative resolution)"
    return score_case(m, p, timestamp=TS, private_key=KEY, solver=solver)


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = argv or ["A2A-001", "A2C-EA1", "A2C-EA4", "A2C-EA2", "A2C-EA5"]
    ok = True
    for tid in wanted:
        try:
            card = run_thacker() if tid.startswith("A2A-001") else run_ea(tid)
        except ReferenceUnavailable as exc:
            print(f"NOT SCORED {tid}: {exc}")
            ok = False
            continue
        out = OUT / f"{card['test_id']}.scorecard.json"
        out.write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{'PASS' if card['passed'] else 'FAIL'} {card['test_id']}")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}  {r.get('detail', '')}")
        if card.get("convergence_result"):
            c = card["convergence_result"]
            print(f"    convergence: p={c['observed_order']} errors={c.get('errors')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
