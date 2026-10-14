"""Exact answers and model results as small curves for the case-page charts.

``exact_curves(m)`` evaluates a case's reference along the line the chart
shows (and, for the dam breaks, at a series of times for the replay).
``model_curve(m, parquet)`` cuts a solver's finest-grid result along the same
line. ``python site/profiles.py`` refreshes ``site/fixtures/profiles/`` from
the solver outputs under ``out/`` (the production solvers' results are not
re-run when the site is built, so their curves are kept as fixtures).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "runner" / "python"), str(ROOT)]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "profiles"
MAX_POINTS = 500

# Which line each chart shows: (variable shown, axis labels, cut)
CHART = {
    "A1F-001": dict(var="wse", x="Distance along the channel (m)", y="Water level (m)"),
    "A1F-010": dict(var="h", x="Distance along the channel (m)", y="Depth (m)", window=(600, 1500)),
    "A1F-011": dict(var="h", x="Distance along the channel (m)", y="Depth (m)", window=(-600, 600)),
    "A1F-020": dict(var="h", x="Distance along the channel (m)", y="Depth (m)", window=(40, 60)),
    "A1P-020": dict(var="p_kpa", x="Distance from the reservoir (m)", y="Pressure rise (kPa)"),
    "A1P-030": dict(var="c", x="Distance along the pipe (m)", y="Concentration (fraction of inflow)", window=(0, 600)),
    "A2A-001": dict(var="wse", x="Across the bowl, x (m)", y="Water level (m)", cut=("y", 0.0)),
    "A2A-010": dict(var="wse", x="Distance along the channel (m)", y="Water level (m)", cut=("y", "mid")),
    "A2A-020": dict(var="h", x="Distance from the wall (m)", y="Depth (m)", cut=("x", 30.0)),
}
REPLAY = {"A1F-010", "A1F-011", "A1P-020", "A1P-030", "A2A-001"}


def short_id(test_id: str) -> str:
    return test_id.split("_")[0]


def _thin(x: np.ndarray, y: np.ndarray, n: int = MAX_POINTS) -> tuple[list, list]:
    step = max(1, int(np.ceil(len(x) / n)))
    return [round(float(v), 4) for v in x[::step]], [None if not np.isfinite(v) else round(float(v), 6) for v in y[::step]]


def _fn(m: dict):
    gen = m["reference"]["generator"]
    return getattr(importlib.import_module(gen["module"]), gen["function"]), dict(gen.get("parameters") or {})


def exact_curves(m: dict) -> dict | None:
    """{"x":…, "y":…, "floor":…, "times":[…], "frames":[[…]…]} for the chart, or None."""
    sid = short_id(m["test_id"])
    spec = CHART.get(sid)
    if spec is None or (m.get("reference") or {}).get("kind") != "analytic":
        return None
    t_end = float(m["simulation"]["t_end"])
    out: dict = {"t_end": t_end}
    if sid in ("A1F-010", "A1F-011"):
        fn, prm = _fn(m)
        lo, hi = spec["window"]
        x = np.linspace(lo, hi, 451)
        out["x"] = _thin(x, x)[0]
        out["times"] = [round(float(t), 3) for t in np.linspace(0, t_end, 61)]
        out["frames"] = [_thin(x, fn(x, max(t, 1e-9), **prm)["h"])[1] for t in out["times"]]
        out["y"] = out["frames"][-1]
    elif sid == "A1F-001":
        from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

        x = np.linspace(0, M1_PARAMS["L"], 401)
        zb = bed_elevation(x)
        out["x"], out["y"] = _thin(x, zb + depth_profile(x))
        out["floor"] = _thin(x, zb)[1]
    elif sid == "A1F-020":
        fn, prm = _fn(m)
        x = np.linspace(*spec["window"], 801)
        out["x"], out["y"] = _thin(x, fn(x, **prm)["h"])
        out["step"] = True
    elif sid == "A1P-020":
        fn, prm = _fn(m)
        x = np.linspace(0, prm["L"], 401)
        out["x"] = _thin(x, x)[0]
        out["times"] = [round(float(t), 4) for t in np.linspace(0, t_end, 51)]
        out["frames"] = [_thin(x, fn(x, max(t, 1e-9), **prm)["p"] / 1e3)[1] for t in out["times"]]
        out["y"] = out["frames"][-1]
    elif sid == "A1P-030":
        fn, prm = _fn(m)
        x = np.linspace(*spec["window"], 401)
        out["x"] = _thin(x, x)[0]
        out["times"] = [round(float(t), 1) for t in np.linspace(0, t_end, 61)]
        out["frames"] = [_thin(x, fn(x, max(t, 1e-6), **prm)["c"])[1] for t in out["times"]]
        out["y"] = out["frames"][-1]
    elif sid == "A2A-001":
        from references.thacker import bed_elevation, depth_velocity

        prm = m["reference"]["generator"]["parameters"]
        x = np.linspace(-1.1, 1.1, 441)
        zb = bed_elevation(x, 0 * x, prm["h0"], prm["L"])

        def wse(t):
            r = depth_velocity(x, 0 * x, t, **prm)
            return np.where(r["h"] > 0, r["h"] + zb, np.nan)

        out["x"] = _thin(x, x)[0]
        out["floor"] = _thin(x, zb)[1]
        out["times"] = [round(float(t), 3) for t in np.linspace(0, t_end, 41)]
        out["frames"] = [_thin(x, wse(t))[1] for t in out["times"]]
        out["y"] = out["frames"][-1]
    elif sid == "A2A-010":
        from references.macdonald_2d import bed_elevation, depth_profile

        prm = m["reference"]["generator"]["parameters"]
        x = np.linspace(0, prm["L"], 401)
        zb = bed_elevation(x, L=prm["L"], q=prm["q"], n_manning=prm["n_manning"])
        out["x"], out["y"] = _thin(x, zb + depth_profile(x))
        out["floor"] = _thin(x, zb)[1]
    elif sid == "A2A-020":
        from references.oblique_jump import depth_velocity

        prm = m["reference"]["generator"]["parameters"]
        dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
        y = np.linspace(0, dom["ymax"], 601)
        h = depth_velocity(np.full_like(y, spec["cut"][1]), y, **{k: prm[k] for k in ("Fr1", "theta_deg", "h1")})["h"]
        out["x"], out["y"] = _thin(y, h)
        out["step"] = True
    return out


def model_curve(m: dict, parquet: Path) -> dict | None:
    """The solver's final state along the chart line."""
    import pandas as pd

    sid = short_id(m["test_id"])
    spec = CHART.get(sid)
    if spec is None:
        return None
    df = pd.read_parquet(parquet)
    df = df[np.isclose(df["t"], df["t"].max())]
    cut = spec.get("cut")
    if cut:
        axis, where = cut
        other = "x" if axis == "y" else "y"
        vals = np.unique(df[axis].to_numpy())
        target = vals[len(vals) // 2] if where == "mid" else vals[np.argmin(np.abs(vals - where))]
        df = df[np.isclose(df[axis], target)].sort_values(other)
        xs = df[other].to_numpy()
    else:
        df = df.sort_values("x")
        xs = df["x"].to_numpy()
    var = spec["var"]
    if var == "wse":
        if "z" in df and df["z"].notna().any():
            z = df["z"].to_numpy()
        elif sid == "A1F-001":
            from references.macdonald import bed_elevation

            z = bed_elevation(xs)
        else:
            return None
        h = df["h"].to_numpy()
        ys = np.where(h > 1e-4, h + z, np.nan)
    elif var == "p_kpa":
        ys = df["p"].to_numpy() / 1e3
    else:
        ys = df[var].to_numpy()
    w = spec.get("window")
    if w:
        keep = (xs >= w[0]) & (xs <= w[1])
        xs, ys = xs[keep], ys[keep]
    if len(xs) == 0:
        return None
    x, y = _thin(xs, ys)
    return {"x": x, "y": y, "dx": _dx_of(parquet)}


def _dx_of(p: Path) -> float | None:
    try:
        return float(p.stem.rsplit("dx", 1)[1])
    except (IndexError, ValueError):
        return None


def finest(dir_: Path, test_id: str) -> Path | None:
    sid = short_id(test_id)
    cands = list(dir_.glob(f"{test_id}_dx*.parquet")) + list(dir_.glob(f"{sid}_*dx*.parquet"))
    if not cands:
        for c in (dir_ / f"{test_id}.parquet", *dir_.glob(f"{test_id}.*.parquet")):
            if c.is_file():
                return c
        return None

    def dx(p):
        try:
            return float(p.stem.rsplit("dx", 1)[1])
        except ValueError:
            return 1e9

    return min(cands, key=dx)


# Solver output folders under out/ -> solver key used on the site
SOURCES = [
    ("telemac", "out/telemac"), ("anuga", "out/anuga"), ("geoclaw", "out/geoclaw"),
    ("lisflood-fv1", "out/lisflood/fv1"), ("lisflood-dg2", "out/lisflood/dg2"), ("lisflood-acc", "out/lisflood/acc"),
    ("swmm524", "out/swmm_track_a/swmm524"), ("openswmm-dw", "out/swmm_track_a/openswmm-dw"), ("openswmm-fv", "out/swmm_track_a/openswmm-fv"),
    ("hecras", "out/hecras"), ("hecras", "out/hecras2d/elm"), ("hecras-em", "out/hecras2d/em"),
]


def refresh_fixtures() -> None:
    sys.path.insert(0, str(ROOT / "site"))
    from benchmark1d2d.catalog import load_manifest  # noqa: F401

    from build import load_manifests  # type: ignore

    FIXTURES.mkdir(parents=True, exist_ok=True)
    for m in load_manifests():
        sid = short_id(m["test_id"])
        if sid not in CHART:
            continue
        path = FIXTURES / f"{sid}.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        for key, d in SOURCES:
            p = finest(ROOT / d, m["test_id"])
            if p is None:
                continue
            c = model_curve(m, p)
            if c:
                data[key] = c
        if data:
            path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{sid}: {sorted(data)}")


if __name__ == "__main__":
    refresh_fixtures()
