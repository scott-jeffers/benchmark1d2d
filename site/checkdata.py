"""Data for the in-browser results check on the "Score your model" page.

For every test with an exact answer and a grid, writes to ``dist/data/check/``:

* ``<SID>.json``             the checks the browser can run, the grid levels
* ``<SID>_dx<L>.json``       the report points of grid level L and the exact
                             answer there (computed by the scorer's own code)
* ``<SID>_dx<L>_template.csv`` the same points as a results template

The report points are the cell centres the suite's own solvers use (taken
from the demo results), so a template filled in by any solver lines up with
the reference point by point.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

SUPPORTED = {"L1", "L2", "Linf", "global_mass_error", "front_position_error"}


def _levels_for(m: dict, result_dirs: list[Path]) -> dict[float, Path]:
    sid = m["test_id"].split("_")[0]
    found: dict[float, Path] = {}
    for d in result_dirs:
        for p in list(d.glob(f"{m['test_id']}_dx*.parquet")) + list(d.glob(f"{sid}_*dx*.parquet")):
            try:
                found.setdefault(float(p.stem.rsplit("dx", 1)[1]), p)
            except ValueError:
                continue
    return found


def _num(v: float) -> str:
    return f"{v:.10g}"


def build(manifests: list[dict], result_dirs: list[Path], out: Path, names: dict[str, str]) -> list[dict]:
    from benchmark1d2d.scoring import scorer
    from pages import check_label

    out.mkdir(parents=True, exist_ok=True)
    checkable = []
    for m in manifests:
        if (m.get("reference") or {}).get("kind") != "analytic":
            continue
        levels = (m["simulation"].get("mesh_refinement") or {}).get("levels") or []
        crit = m["scoring"]["criteria"]
        if len(levels) < 2 or not any(c["metric"] in SUPPORTED for c in crit):
            continue
        files = _levels_for(m, result_dirs)
        if not all(float(lv) in files for lv in levels):
            continue
        sid = m["test_id"].split("_")[0]
        fn, params = scorer._load_generator(m)
        t_end = float(m["simulation"]["t_end"])
        conv = m["scoring"].get("convergence") or None
        if conv and conv.get("not_applicable"):
            conv = None
        need = {c.get("variable", "h") for c in crit if c["metric"] in ("L1", "L2", "Linf")}
        need |= {c.get("variable") for c in crit if c["metric"] == "global_mass_error" and c.get("variable") not in ("volume", "h", None)}
        need |= {"h"} | ({conv["variable"]} if conv else set())
        meta_levels = []
        is2d = False
        for lv in sorted(levels, reverse=True):
            df = pd.read_parquet(files[float(lv)])
            sim = scorer._final_slice(df)
            x, y = scorer._sim_xy(sim)
            is2d = y is not None
            ref = scorer._call_reference(fn, params, x, t_end, m, y=y)
            refv = {k: [None if not np.isfinite(v) else round(float(v), 9) for v in np.asarray(ref[k], dtype=float)] for k in need if k in ref}
            name = f"{float(lv):g}"
            pts = {"x": [round(float(v), 6) for v in x], "y": None if y is None else [round(float(v), 6) for v in y], "ref": refv}
            (out / f"{sid}_dx{name}.json").write_text(json.dumps(pts, separators=(",", ":")), encoding="utf-8")
            cols = ["t", "x", "y", "h", "u", "v"] + [c for c in ("c", "p") if c in need]
            with (out / f"{sid}_dx{name}_template.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(cols)
                for i in range(len(x)):
                    w.writerow([_num(t_end), _num(x[i]), "" if y is None else _num(y[i])] + [""] * (len(cols) - 3))
            meta_levels.append({"name": name, "dx": float(lv), "n": int(len(x))})
        front = None
        if any(c["metric"] == "front_position_error" for c in crit):
            from references.ritter import depth_contour_position

            h0 = float(params.get("h0", 1.0))
            front = {"thresh": 1e-3 * h0, "exact": float(depth_contour_position(t_end, 1e-3 * h0, h0=h0, x0=float(params.get("x0", 1000.0)), g=float(params.get("g", 9.81))))}
        meta = {"sid": sid, "name": names.get(sid, m.get("title", sid)), "t_end": t_end, "is2d": is2d, "levels": meta_levels,
                "criteria": [{"id": c["id"], "label": check_label(c), "metric": c["metric"], "variable": c.get("variable", "h"), "threshold": c["threshold"],
                              "gating": bool(c.get("gating", True)), "supported": c["metric"] in SUPPORTED} for c in crit],
                "conv": conv, "front": front}
        (out / f"{sid}.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
        checkable.append({"sid": sid, "name": meta["name"], "level_names": [lv["name"] for lv in meta_levels]})
    return checkable
