#!/usr/bin/env python3
"""EPANET parity: score a candidate water-distribution engine against EPANET 2.2 on a set of networks.

The networks are the example networks bundled with WNTR 1.5.0 (Net1, Net2,
Net3, Net6, ky4, ky10: EPANET's own examples and two Kentucky utility
networks), so the set is independent of any candidate's own test fixtures.
For each network the pinned reference (EPANET 2.2, WNTR's ``libepanet22``) and
the candidate run the same ``.inp``; both results are read in SI units and
scored element by element, as the catalog's B-EPANET-001 case is:

- ``peak_pressure``: worst node, relative difference in peak pressure
- ``volume``: worst link, relative difference in the time integral of |Q|
- ``timing``: worst link, difference in the time of peak |Q| [s]

Candidates: ``hydra`` (NEER AI Hydra's ``wds`` engine; ``--candidate`` is the
``hydra`` CLI) or ``epanet20`` (EPANET 2.00.12 in WNTR, for scale).

Writes ``<out>/<label>.parquet`` (one row per network) and a summary JSON.

Usage::

    python scripts/epanet_parity.py --candidate-engine hydra --candidate /path/to/hydra --label hydra
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

from benchmark1d2d.scoring.scorer import parity_from_series  # noqa: E402

NETWORKS = ["Net1", "Net2", "Net3", "Net6", "ky4", "ky10"]
RHO_G = 1000.0 * 9.81


def library_inp(name: str) -> Path:
    import wntr

    return Path(wntr.__file__).parent / "library" / "networks" / f"{name}.inp"


def run_wntr(inp: Path, version: float):
    import wntr

    wn = wntr.network.WaterNetworkModel(str(inp))
    with tempfile.TemporaryDirectory() as td:
        return wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(Path(td) / "run"), version=version)


def run_candidate(engine: str, exe: str | None, inp: Path, timeout: float, extra: list[str] | None = None):
    if engine == "epanet20":
        return run_wntr(inp, 2.0), "2.00.12"
    from benchmark1d2d.adapters import hydra

    with tempfile.TemporaryDirectory() as td:
        rpt, out = Path(td) / "m.rpt", Path(td) / "m.out"
        hydra.run(exe, inp, rpt, out, "wds", timeout=timeout, extra=extra)
        return hydra.epanet_results(out), hydra.version(exe)


def series(df: pd.DataFrame, scale: float = 1.0) -> dict:
    t = df.index.to_numpy(float)
    return {str(c): (t, df[c].to_numpy(float) * scale) for c in sorted(df.columns, key=str)}


def score(ref, cand) -> dict:
    row = {}
    row["peak_pressure_pct"], row["peak_pressure_detail"] = parity_from_series(
        "relative_peak", series(cand.node["pressure"], RHO_G), series(ref.node["pressure"], RHO_G))
    row["volume_pct"], row["volume_detail"] = parity_from_series(
        "relative_volume", series(cand.link["flowrate"]), series(ref.link["flowrate"]))
    row["timing_s"], row["timing_detail"] = parity_from_series(
        "timing_error", series(cand.link["flowrate"]), series(ref.link["flowrate"]))
    row["n_nodes"], row["n_links"] = int(ref.node["pressure"].shape[1]), int(ref.link["flowrate"].shape[1])
    row["n_times_ref"], row["n_times_cand"] = int(len(ref.node["pressure"].index)), int(len(cand.node["pressure"].index))
    row["worst_pct"] = max(abs(row["peak_pressure_pct"]), abs(row["volume_pct"]))
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--candidate-engine", choices=["hydra", "epanet20"], required=True)
    ap.add_argument("--candidate", help="the hydra CLI (for --candidate-engine hydra)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--candidate-args", nargs=argparse.REMAINDER, default=[],
                    help="further hydra CLI options, last on the line (e.g. --tank-tolerance 0)")
    ap.add_argument("--networks", nargs="+", default=NETWORKS)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--out", type=Path, default=REPO / "out" / "epanet_parity")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows, cand_version = [], None
    for name in args.networks:
        inp = library_inp(name)
        row = {"network": name, "status": "scored"}
        t0 = time.perf_counter()
        ref = run_wntr(inp, 2.2)
        row["ref_runtime_s"] = round(time.perf_counter() - t0, 3)
        t0 = time.perf_counter()
        try:
            cand, cand_version = run_candidate(args.candidate_engine, args.candidate, inp, args.timeout, args.candidate_args)
        except Exception as exc:  # noqa: BLE001 — record and continue
            rows.append({**row, "status": "candidate_error", "detail": str(exc)[:300]})
            print(f"  {name}: candidate error {exc}")
            continue
        row["cand_runtime_s"] = round(time.perf_counter() - t0, 3)
        try:
            row.update(score(ref, cand))
        except Exception as exc:  # noqa: BLE001
            row.update(status="harness_error", detail=f"{type(exc).__name__}: {exc}"[:300])
        rows.append(row)
        print(f"  {name}: worst {row.get('worst_pct', float('nan')):.3g} % "
              f"(pressure {row.get('peak_pressure_pct', float('nan')):+.3g} %, volume {row.get('volume_pct', float('nan')):+.3g} %, "
              f"timing {row.get('timing_s', float('nan')):+.0f} s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(args.out / f"{args.label}.parquet", index=False)
    sc = df[df["status"] == "scored"]
    summ = {"reference": "EPANET 2.2 (WNTR 1.5.0 libepanet22)", "candidate": args.label, "candidate_engine": args.candidate_engine,
            "candidate_args": args.candidate_args,
            "candidate_version": cand_version, "networks": len(df),
            "status": {k: int(v) for k, v in df["status"].value_counts().items()},
            "within_1pct": int((sc["worst_pct"].abs() <= 1).sum()) if len(sc) else 0,
            "metrics": "peak_pressure = worst node, relative peak pressure; volume = worst link, relative integral of |Q|; timing = worst link, time of peak |Q|"}
    (args.out / f"{args.label}.summary.json").write_text(json.dumps(summ, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
