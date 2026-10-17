#!/usr/bin/env python3
"""Print the exact solutions' mean depths (and discharges) behind test_catalog/difference_scales.json.

A depth-norm check's percent difference is its error over the exact solution's
mean |h| over the domain on the finest grid, the same average the error is
taken over (benchmark1d2d.metrics.norms.L1 is a domain mean). This prints
those means for the analytic tests so the scales file can be checked:

    python scripts/difference_scales.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

from benchmark1d2d.scoring.scorer import _call_reference, _load_generator  # noqa: E402

TESTS = ["A1F-001", "A1F-011", "A1F-040", "A1F-041", "A1F-042", "A1F-043", "A2A-001", "A2A-010", "A2A-020"]


def main() -> int:
    scales = json.loads((REPO / "test_catalog" / "difference_scales.json").read_text(encoding="utf-8"))
    for t in TESTS:
        d = next(REPO.glob(f"test_catalog/*/*/{t}*/"))
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        m["_case_dir"] = str(d)
        p = json.loads((d / "inputs" / "params.json").read_text(encoding="utf-8"))
        dx = min(m["simulation"]["mesh_refinement"]["levels"])
        dom = p.get("domain") or {"xmin": 0.0, "xmax": p["L"], "ymin": 0.0, "ymax": p["W"]}
        fn, par = _load_generator(m)
        xs = np.arange(dom["xmin"] + dx / 2, dom["xmax"], dx)
        if t.startswith("A2"):
            ys = np.arange(dom["ymin"] + dx / 2, dom["ymax"], dx)
            X, Y = np.meshgrid(xs, ys)
            x, y = X.ravel(), Y.ravel()
        else:
            x, y = xs, None
        r = _call_reference(fn, par, x, float(m["simulation"]["t_end"]), m, y=y)
        means = {k: float(np.nanmean(np.abs(np.asarray(v, float)))) for k, v in r.items() if k in ("h", "Q")}
        print(f"{t}: mean |h| {means.get('h', float('nan')):.4f} m"
              + (f", mean |Q| {means['Q']:.4f} m²/s" if "Q" in means else "")
              + f"   (scales file: {scales.get(t)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
