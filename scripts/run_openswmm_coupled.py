#!/usr/bin/env python3
"""Score OpenSWMM Engine v6's own 1D/2D coupling on the exact coupled cases (A12-01x).

OpenSWMM v6 couples its sewer network to a 2D surface itself: a local-inertial
finite-volume mesh, each manhole tied to a mesh vertex through an orifice law
with a gate at the manhole's rim (``docs/coupled.md``). Unlike the suite's
SWMM + ANUGA example, nothing here moves water between the two: the engine is
run as a black box with its own defaults, and only the model is written for it
(``scripts/openswmm_coupled_model.py``, run in the Python that has the
``openswmm`` wheel).

The surface is the case's grid of ``cell_size`` squares, triangulated two ways,
each scored as its own variant:

* ``openswmm-2d``: each square cut along one diagonal (two triangles);
* ``openswmm-2d-x``: each square cut along both diagonals (four triangles,
  the "rectangular cross" mesh the suite's ANUGA surface uses).

Usage::

    python scripts/run_openswmm_coupled.py --openswmm-python PATH [A12-010 ...] [--mesh diagonal cross]

Score cards go to ``out/coupled/openswmm-2d/`` and ``out/coupled/openswmm-2d-x/``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

TS = "2024-01-01T00:00:00Z"
CASES = ["A12-010", "A12-011", "A12-012"]
MESHES = {"diagonal": ("openswmm-2d", "two triangles per grid square"),
          "cross": ("openswmm-2d-x", "four triangles per grid square")}


def columns(m: dict, rec: dict) -> dict:
    """The run's records as results columns: probes (cell), exchange, volume accounts."""
    rows: dict[str, list] = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "Q", "z", "V", "element_id", "element_type")}
    nan = float("nan")

    def emit(t, x=nan, y=nan, h=nan, Q=nan, z=nan, V=nan, eid="", etype="cell"):
        for k, val in (("t", t), ("x", x), ("y", y), ("h", h), ("u", nan), ("v", nan), ("p", nan), ("Q", Q), ("z", z), ("V", V),
                       ("element_id", eid), ("element_type", etype)):
            rows[k].append(val)

    probes = {p["id"]: p for p in m["simulation"].get("probes") or []}
    for i, t in enumerate(rec["t"]):
        for pid, pr in rec["probes"].items():
            emit(t, probes[pid]["x"], probes[pid]["y"], pr["h"][i], z=pr["z"], eid=pid)
        for k, q in rec["exchange"].items():
            emit(t, Q=q[i], eid=k, etype="exchange")
        for acc in ("surface", "network", "inflow", "outflow"):
            emit(t, V=rec[acc][i], eid=acc, etype="account")
    return {k: (np.asarray(v, dtype=float) if k not in ("element_id", "element_type") else v) for k, v in rows.items()}


def main() -> int:
    from benchmark1d2d.signing import private_key as signing_key

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=CASES)
    ap.add_argument("--openswmm-python", required=True, help="a Python with the openswmm wheel")
    ap.add_argument("--mesh", nargs="*", default=list(MESHES), choices=list(MESHES))
    args = ap.parse_args()
    key = signing_key()  # BENCH_SIGNING_KEY, else the public development key
    child = REPO / "scripts" / "openswmm_coupled_model.py"
    for mesh in args.mesh:
        model_key, what = MESHES[mesh]
        out = REPO / "out" / "coupled" / model_key
        out.mkdir(parents=True, exist_ok=True)
        for tid in args.cases:
            m = load_manifest(tid, repo=REPO)
            work = out / f"{m['test_id']}_model"
            series = out / f"{m['test_id']}.run.json"
            t0 = time.perf_counter()
            env = {**os.environ, "OPENSWMM_MESH": mesh}
            r = subprocess.run([args.openswmm_python, str(child), str(m["_case_dir"]), str(series), str(work)],
                               env=env, capture_output=True, text=True)
            if r.returncode:
                print(r.stdout[-2000:], r.stderr[-4000:], file=sys.stderr)
                raise SystemExit(f"OpenSWMM run failed: {tid} ({mesh})")
            rec = json.loads(series.read_text(encoding="utf-8"))
            from benchmark1d2d import keep

            keep.inputs(model_key, tid, work, files=["model.inp"])
            ver = rec["version"]
            sol = {"name": f"OpenSWMM Engine v6 1D/2D ({what}) {ver}", "version": ver,
                   "adapter": f"OpenSWMM's own 1D/2D coupling, defaults; vertex-coupled manholes; {what}"}
            res = write_results_parquet(out / f"{m['test_id']}.parquet", columns(m, rec), wall_seconds=time.perf_counter() - t0)
            card = score_case(m, res, timestamp=TS, private_key=key, solver=sol)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            eng = rec["engine"]
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} {model_key} ({time.perf_counter() - t0:.0f} s; "
                  f"network continuity {eng['routing_continuity_pct']:.3f} %, surface {100 * eng['surface_continuity']:.1e} %)")
            for c in card["criteria_results"]:
                print(f"    [{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['observed']} {c['threshold']['units']} — {c.get('detail', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
