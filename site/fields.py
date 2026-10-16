"""Depth maps for the results viewer: each model's final 2D field, the exact field, and frames over time.

``extract_field(m, folder)`` bins a model's finest-grid result at the end of
the run onto a regular grid of at most ``MAX_BINS`` cells along its longer
side (mean depth per bin; empty bins are null), so maps from triangular
meshes, raster models and the exact answer can be drawn side by side. If the
runner saved snapshots (``<test_id>.frames.npz``, written when
``BENCH_FRAMES`` is set; arrays ``t``, ``x``, ``y``, ``h`` with ``h`` of shape
(times, cells)), they are binned the same way for the viewer's animation.

``exact_field(m, grid, times)`` evaluates an analytic test's exact depth at
the bin centres of a grid, at the end of the run or at the given times.

Both run in CI (``scripts/export_curves.py`` adds ``field`` to each 2D
test's extract) and at site build time (the exact fields).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

MAX_BINS = 96
MAX_FRAMES = 30
FRAME_BINS = 48  # frames are drawn on a coarser grid, to keep the files small


def is_2d(m: dict) -> bool:
    return (m.get("physics") or {}).get("dimensionality") == "2D" and m.get("track") == "A"


def cell_size(x: np.ndarray, y: np.ndarray) -> float | None:
    """The spacing of a regular grid of cell centres, or None for an unstructured mesh."""
    ux, uy = np.unique(np.round(x, 9)), np.unique(np.round(y, 9))
    if len(ux) * len(uy) > 4 * len(x) or len(ux) < 2:
        return None
    dx = np.diff(ux)
    d = float(np.median(dx))
    return d if d > 0 and np.allclose(dx, d, rtol=1e-3) else None


def grid_for(x: np.ndarray, y: np.ndarray, max_bins: int = MAX_BINS, cell: float | None = None) -> dict:
    x0, x1, y0, y1 = float(np.min(x)), float(np.max(x)), float(np.min(y)), float(np.max(y))
    span = max(x1 - x0, y1 - y0) or 1.0
    if cell:
        # a whole number of model cells per bin, aligned to the cell edges: every bin averages the same cells,
        # and the exact answer at the bin centre is the mean of a linear field over it
        k = max(1, int(np.ceil((span + cell) / cell / max_bins)))
        d = k * cell
        nx, ny = int(np.ceil((x1 - x0 + cell) / d - 1e-9)), int(np.ceil((y1 - y0 + cell) / d - 1e-9))
        return {"x0": x0 - cell / 2, "y0": y0 - cell / 2, "dx": d, "nx": max(nx, 1), "ny": max(ny, 1)}
    d = span / max_bins
    nx, ny = max(1, int(np.ceil((x1 - x0) / d + 1e-9))), max(1, int(np.ceil((y1 - y0) / d + 1e-9)))
    # pad so the outermost cell centres fall inside a bin
    return {"x0": x0 - d / 2, "y0": y0 - d / 2, "dx": d, "nx": nx + 1, "ny": ny + 1}


def _bin(g: dict, x: np.ndarray, y: np.ndarray, v: np.ndarray) -> np.ndarray:
    i = np.clip(((x - g["x0"]) / g["dx"]).astype(int), 0, g["nx"] - 1)
    j = np.clip(((y - g["y0"]) / g["dx"]).astype(int), 0, g["ny"] - 1)
    k = j * g["nx"] + i
    s = np.bincount(k, weights=v, minlength=g["nx"] * g["ny"])
    n = np.bincount(k, minlength=g["nx"] * g["ny"])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / np.maximum(n, 1), np.nan)


def _pack(a: np.ndarray) -> list:
    return [None if not np.isfinite(v) else round(float(v), 5) for v in a]


def _finest(folder: Path, test_id: str) -> Path | None:
    import profiles

    return profiles.finest(folder, test_id)


def extract_field(m: dict, folder: Path) -> dict | None:
    if not is_2d(m):
        return None
    import pandas as pd

    p = _finest(folder, m["test_id"])
    if p is None:
        return None
    import pyarrow.parquet as pq

    names = pq.read_schema(p).names
    df = pd.read_parquet(p, columns=[c for c in ("t", "x", "y", "h", "element_type") if c in names])
    if "element_type" in df.columns:
        df = df[df["element_type"].fillna("cell").isin(["cell", ""])]
    df = df[np.isfinite(df["x"]) & np.isfinite(df["y"]) & np.isfinite(df["h"])]
    counts = df.groupby("t").size()
    full = counts[counts >= 50]
    if full.empty:  # probes only, not a field
        return None
    last = df[df["t"] == full.index.max()]  # the latest time with a whole field (some models write it hourly)
    x, y, h = (last[c].to_numpy(float) for c in ("x", "y", "h"))
    g = grid_for(x, y, cell=cell_size(x, y))
    out = {**g, "t": float(last["t"].iloc[0]), "h": _pack(np.maximum(_bin(g, x, y, h), 0.0)), "cells": int(len(last))}
    ft = sorted(full.index)
    if len(ft) >= 3:  # the results hold the whole field at several times (the EA tests): frames for the animation
        idx = np.unique(np.linspace(0, len(ft) - 1, min(len(ft), MAX_FRAMES)).round().astype(int))
        fg = grid_for(x, y, FRAME_BINS, cell=cell_size(x, y))
        hs = []
        for i in idx:
            snap = df[df["t"] == ft[i]]
            hs.append([None if v is None else round(v, 3) for v in
                       _pack(np.maximum(_bin(fg, snap["x"].to_numpy(float), snap["y"].to_numpy(float), snap["h"].to_numpy(float)), 0.0))])
        out["frames"] = {"grid": fg, "t": [float(ft[i]) for i in idx], "h": hs}
    fr = folder / f"{m['test_id']}.frames.npz"
    if fr.is_file() and "frames" not in out:
        try:
            z = np.load(fr)
            t, fx, fy, fh = z["t"], z["x"], z["y"], z["h"]
            idx = np.unique(np.linspace(0, len(t) - 1, min(len(t), MAX_FRAMES)).round().astype(int))
            fg = grid_for(fx, fy, FRAME_BINS, cell=cell_size(fx, fy))
            out["frames"] = {"grid": fg, "t": [float(t[i]) for i in idx],
                             "h": [_pack(np.maximum(_bin(fg, fx, fy, fh[i]), 0.0)) for i in idx]}
        except Exception:  # noqa: BLE001 - frames are optional
            pass
    return out


def exact_field(m: dict, g: dict, times: list[float] | None = None) -> dict | None:
    """Exact depth at the grid's bin centres (analytic tests only); with ``times``, one frame per time."""
    if (m.get("reference") or {}).get("kind") != "analytic":
        return None
    from benchmark1d2d.scoring import scorer

    fn, params = scorer._load_generator(m)
    if fn is None:
        return None
    xc = g["x0"] + g["dx"] * (np.arange(g["nx"]) + 0.5)
    yc = g["y0"] + g["dx"] * (np.arange(g["ny"]) + 0.5)
    X, Y = np.meshgrid(xc, yc)

    def at(t: float):
        r = scorer._call_reference(fn, params, X.ravel(), float(t), m, y=Y.ravel())
        h = np.asarray(r["h"] if isinstance(r, dict) else r, dtype=float)
        return _pack(np.maximum(h, 0.0))

    t_end = float(m["simulation"]["t_end"])
    out = {**g, "t": t_end, "h": at(t_end)}
    if times:
        out["frames"] = {"grid": {k: g[k] for k in ("x0", "y0", "dx", "nx", "ny")}, "t": [float(t) for t in times], "h": [at(t) for t in times]}
    return out
