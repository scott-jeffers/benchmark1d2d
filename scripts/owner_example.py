#!/usr/bin/env python3
"""The owner-run workflow's worked example: what an owner's command does, with the suite's demo 1D solver.

Called as ``owner_example.py TEST KIT RESULTS``. A real owner's command would
build their model from ``KIT/inputs`` (or start from ``KIT/model``), run their
software, put the model files it used in ``KIT/model`` and its outputs in
``KIT/output``, and fill in the sheets in ``RESULTS``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO / "examples" / "demo_solver")]


def main() -> int:
    from benchmark1d2d.catalog import load_manifest
    import pandas as pd
    from solve import run_case

    test, kit, results = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    m = load_manifest(test, repo=REPO)
    case = {"A1F-010": "ritter", "A1F-011": "stoker"}.get(test)
    if case is None:
        print(f"the example handles A1F-010 and A1F-011, not {test}")
        return 1
    (kit / "model").mkdir(exist_ok=True)
    (kit / "model" / "settings.txt").write_text("demo 1D solver: first-order finite volume (HLL), CFL 0.5\n", encoding="utf-8")
    for sheet in sorted(results.glob(f"{test}_dx*.csv")):
        dx = float(sheet.stem.split("_dx")[1])
        out = kit / "output" / f"{test}_dx{dx:g}.parquet"
        run_case(case, dx=dx, t_end=None, out=out, manifest=m)
        df = pd.read_parquet(out)
        with sheet.open(newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        head = rows[0]
        xs = df["x"].to_numpy()
        for r in rows[1:]:
            x = float(r[head.index("x")])
            i = abs(xs - x).argmin()
            for col in head:
                if col in ("h", "u") and col in df:
                    r[head.index(col)] = f"{float(df[col].iloc[i]):.8g}"
        with sheet.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
