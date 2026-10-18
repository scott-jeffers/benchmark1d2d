#!/usr/bin/env python3
"""Seeded MacDonald beds on EPA SWMM 5.2.4 under each NORMAL_FLOW_LIMITED option (review F14).

Draws exact steady cases from references/macdonald_random.py (seeds x Froude caps), writes each as
the same chain of wide rectangular conduits A1F-001 uses (scripts/run_swmm_track_a.py), runs 12 h
of constant inflow with each option set, and reports the mean |depth error| at the nodes against
the exact profile, and how far the profile still moved over the last hour.

    python scripts/macdonald_family_swmm.py --out out/macdonald_family
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

from benchmark1d2d.adapters.swmm5 import read_out  # noqa: E402
from benchmark1d2d.engine_report import swmm_report  # noqa: E402
from references.macdonald_random import draw  # noqa: E402

import run_swmm_track_a as rs  # noqa: E402

OPTION_SETS = {
    "BOTH (default)": {},
    "SLOPE": {"NORMAL_FLOW_LIMITED": "SLOPE"},
    "FROUDE": {"NORMAL_FLOW_LIMITED": "FROUDE"},
    "BOTH, INERTIAL_DAMPING NONE": {"INERTIAL_DAMPING": "NONE"},
}
T_END = 12 * 3600.0
RUN = ("import os, sys\nfrom swmm.toolkit import solver\nos.chdir(os.path.dirname(sys.argv[1]))\n"
       "solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n")


def set_options(inp: Path, opts: dict) -> None:
    lines = inp.read_text(encoding="ascii").splitlines()
    for k, v in opts.items():
        lines = [f"{k} {v}" if ln.split()[:1] == [k] else ln for ln in lines]
    inp.write_text("\n".join(lines) + "\n", encoding="ascii")


def one(case: dict, dx: float, opts: dict, td: Path) -> dict:
    L, B, Q, n = case["L"], case["B"], case["Q"], case["n_manning"]
    faces = np.linspace(0.0, L, int(round(L / dx)) + 1)
    z = case["bed"](faces)
    h_out = case["h_downstream"]
    inp = td / "m.inp"
    rs.write_inp(inp, faces, z, np.full_like(faces, h_out), rs.W_WIDE, n, T_END, "DYNWAVE", dx,
                 inflow=Q / B * rs.W_WIDE, stage_out=float(z[-1] + h_out))
    set_options(inp, opts)
    subprocess.run([sys.executable, "-c", RUN, str(inp), str(td / "m.rpt"), str(td / "m.out")], check=True, capture_output=True)
    o = read_out(td / "m.out")
    names = sorted(o["nodes"])
    H = np.array([o["nodes"][k] for k in names])  # node x time
    t = o["t"]
    exact = case["depth"](faces)
    last = H[:, -1]
    hour = H[:, np.searchsorted(t, t[-1] - 3600.0)]
    inner = slice(1, -1)  # the inflow node and the fixed-stage outfall are boundary values
    rep = swmm_report(td / "m.rpt") or {}
    return {"mean_abs_error_m": float(np.abs(last - exact)[inner].mean()),
            "max_abs_error_m": float(np.abs(last - exact)[inner].max()),
            "moved_last_hour_m": float(np.abs(last - hour)[inner].max()),
            "steps_not_converging_pct": rep.get("steps_not_converging_pct"),
            "routing_continuity_pct": rep.get("routing_continuity_pct")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--caps", type=float, nargs="+", default=[0.5, 0.9])
    ap.add_argument("--dx", type=float, nargs="+", default=[10.0, 5.0, 2.5])
    ap.add_argument("--out", type=Path, default=REPO / "out" / "macdonald_family")
    args = ap.parse_args()
    rows = []
    for seed in args.seeds:
        for cap in args.caps:
            case = draw(seed, cap)
            for dx in args.dx:
                for name, opts in OPTION_SETS.items():
                    with tempfile.TemporaryDirectory() as tdn:
                        r = one(case, dx, opts, Path(tdn))
                    r.update(seed=seed, froude_cap=cap, conduits=int(round(case["L"] / dx)), options=name)
                    rows.append(r)
                    print(f"seed {seed} Fr {cap} {r['conduits']:4d} conduits  {name:28s} mean |dh| {r['mean_abs_error_m']:.5f} m "
                          f"({r['mean_abs_error_m'] / 0.3048:.4f} ft), moved {r['moved_last_hour_m']:.2e} m in the last hour", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "macdonald_family_swmm524.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
