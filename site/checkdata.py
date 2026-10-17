"""Data for the in-browser results check on the "Score your model" page.

Three kinds of test can be checked in the browser.

**Grids** (``mode: grid``). For every test with an exact answer and a grid, writes to ``dist/data/check/``:

* ``<SID>.json``             the checks the browser can run, the grid levels
* ``<SID>_dx<L>.json``       the report points of grid level L and the exact
                             answer there (computed by the scorer's own code)
* ``<SID>_dx<L>_template.csv`` the same points as a results template

The report points are the cell centres the suite's own solvers use (taken
from the demo results, or for a 1D case without demo results the centres of
cells of the grid size along its domain), so a template filled in by any
solver lines up with the reference point by point.

**Networks** (``mode: elements``): a test whose exact answer is keyed by node
and link (the drainage tests). ``<SID>.json`` lists the elements and the exact
values; one template, ``<SID>_template.csv``.

**Exact states** (``mode: states``): the coupled tests, scored on exact states
(a probe's depth, an exchange flow, a volume account at a time) and the water
balance; one template.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import difference  # noqa: E402  (what each check is a percentage of)

SUPPORTED = {"L1", "L2", "Linf", "global_mass_error", "front_position_error", "volume_front_error"}
SUPPORTED_STATES = {"expected_state_error", "continuity_error"}


def _synth_levels(m: dict) -> dict[float, np.ndarray] | None:
    """Cell centres of each grid size along a 1D case's domain (inputs/params.json), for cases without demo results."""
    try:
        dom = json.loads((Path(m["_case_dir"]) / "inputs" / "params.json").read_text(encoding="utf-8"))["domain"]
        x0, x1 = float(dom["xmin"]), float(dom["xmax"])
    except (OSError, KeyError, ValueError):
        return None
    if "ymin" in dom:
        return None
    levels = (m["simulation"].get("mesh_refinement") or {}).get("levels") or []
    return {float(lv): np.arange(x0 + lv / 2, x1, lv) for lv in levels}


def _elements_meta(m: dict, out: Path, names: dict, check_label) -> dict | None:
    from benchmark1d2d.catalog.kit import kit_files
    from benchmark1d2d.scoring import scorer

    fn, params = scorer._load_generator(m)
    ref = scorer._call_reference(fn, params, np.array([0.0]), float(m["simulation"]["t_end"]), m)
    if not isinstance(ref, dict) or "element_id" not in ref:
        return None
    crit = m["scoring"]["criteria"]
    sid = m["test_id"].split("_")[0]
    vals = {k: [None if not np.isfinite(v) else round(float(v), 9) for v in np.asarray(ref[k], float)]
            for k in ("h", "Q") if k in ref}
    meta = {"sid": sid, "mode": "elements", "name": names.get(sid, m.get("title", sid)), "t_end": float(m["simulation"]["t_end"]),
            "elements": [[str(t), str(e)] for t, e in zip(ref.get("element_type") or [""] * len(ref["element_id"]), ref["element_id"])],
            "ref": vals,
            "criteria": [{"id": c["id"], "label": check_label(c), "metric": c["metric"], "variable": c.get("variable", "h"),
                          "threshold": c["threshold"], "scale": difference.scale_for(m["test_id"], c["id"]), "gating": bool(c.get("gating", True)), "supported": c["metric"] in ("L1", "L2", "Linf")}
                         for c in crit]}
    (out / f"{sid}.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    (out / f"{sid}_template.csv").write_text(kit_files(m)["RESULTS_TEMPLATE.csv"], encoding="utf-8")
    return meta


def _states_meta(m: dict, out: Path, names: dict, check_label) -> dict:
    from benchmark1d2d.catalog.kit import kit_files

    sid = m["test_id"].split("_")[0]
    meta = {"sid": sid, "mode": "states", "name": names.get(sid, m.get("title", sid)), "t_end": float(m["simulation"]["t_end"]),
            "states": m["reference"]["expected_states"], "probes": m["simulation"].get("probes") or [],
            "criteria": [{"id": c["id"], "label": check_label(c), "metric": c["metric"], "variable": c.get("variable", "h"),
                          "against": c.get("against"), "threshold": c["threshold"], "scale": difference.scale_for(m["test_id"], c["id"]), "gating": bool(c.get("gating", True)),
                          "supported": c["metric"] in SUPPORTED_STATES} for c in m["scoring"]["criteria"]]}
    (out / f"{sid}.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    (out / f"{sid}_template.csv").write_text(kit_files(m)["RESULTS_TEMPLATE.csv"], encoding="utf-8")
    return meta


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
        kind = (m.get("reference") or {}).get("kind")
        if m["status"] == "draft":
            continue
        sid0 = m["test_id"].split("_")[0]
        if kind == "exact_states":
            meta = _states_meta(m, out, names, check_label)
            checkable.append({"sid": sid0, "name": meta["name"], "templates": [("Template", f"{sid0}_template.csv")]})
            continue
        if kind != "analytic":
            continue
        levels = (m["simulation"].get("mesh_refinement") or {}).get("levels") or []
        crit = m["scoring"]["criteria"]
        if len(levels) < 2:
            meta = _elements_meta(m, out, names, check_label) if m["test_id"].startswith("A1D") else None
            if meta:
                checkable.append({"sid": sid0, "name": meta["name"], "templates": [("Template", f"{sid0}_template.csv")]})
            continue
        if not any(c["metric"] in SUPPORTED for c in crit):
            continue
        files = _levels_for(m, result_dirs)
        synth = None
        if not all(float(lv) in files for lv in levels):
            synth = _synth_levels(m)
            if not synth:
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
            if synth:
                x, y = synth[float(lv)], None
            else:
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
        vfront = None
        if any(c["metric"] == "volume_front_error" for c in crit):
            from references.ritter import volume_front_position

            frac = scorer.VOLUME_FRONT_FRACTION
            x0 = float(params.get("x0", 1000.0))
            vfront = {"fraction": frac, "x0": x0, "exact": volume_front_position(
                t_end, frac, h0=float(params.get("h0", 1.0)), x0=x0, g=float(params.get("g", 9.81)))}
        meta = {"sid": sid, "mode": "grid", "name": names.get(sid, m.get("title", sid)), "t_end": t_end, "is2d": is2d, "levels": meta_levels,
                "criteria": [{"id": c["id"], "label": check_label(c), "metric": c["metric"], "variable": c.get("variable", "h"), "threshold": c["threshold"], "scale": difference.scale_for(m["test_id"], c["id"]),
                              "gating": bool(c.get("gating", True)), "supported": c["metric"] in SUPPORTED} for c in crit],
                "conv": conv, "front": front, "vfront": vfront}
        (out / f"{sid}.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
        checkable.append({"sid": sid, "name": meta["name"], "templates": [(lv["name"], f"{sid}_dx{lv['name']}_template.csv") for lv in meta_levels]})
    return checkable
