#!/usr/bin/env python3
"""Score real candidate engines on the Track B catalog cases.

Demonstrates Track B with engines that genuinely differ from the references:

- **EPA SWMM 5.1.15** (``swmm-toolkit`` 0.10.0) on the SWMM cases, scored
  against the pinned SWMM 5.2.4 reference. Needs a Python 3.10 environment with
  ``swmm-toolkit==0.10.0``; pass it with ``--swmm51-python``.
- **OpenSWMM Engine v6** (HydroCouple's SWMM 6, the new C++20 engine in the
  ``openswmm`` wheel) on the SWMM cases, against SWMM 5.2.4; pass a Python with
  ``openswmm`` installed as ``--openswmm-python``.
- **Hydra** (NEER AI, Rust; ``--hydra-exe``): its urban-drainage engine on the
  SWMM cases against SWMM 5.2.4 and its water-distribution engine on the
  EPANET case against EPANET 2.2.
- **EPANET 2.0** (the 2.00.12 library bundled with WNTR) on the EPANET case,
  scored against EPANET 2.2.

Score cards land in ``out/track_b/``. These are demonstrations of how parity
differences are reported, not judgments of either engine.

Usage::

    python scripts/run_track_b.py --swmm51-python /path/to/py310/bin/python
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

from benchmark1d2d.clock import run_timestamp  # noqa: E402
from benchmark1d2d.signing import private_key as signing_key  # noqa: E402

from benchmark1d2d.adapters import swmm5  # noqa: E402
from benchmark1d2d.catalog import load_manifest  # noqa: E402
from benchmark1d2d.scoring.scorer import score_case  # noqa: E402

OUT = REPO / "out" / "track_b"
KEY = signing_key()  # BENCH_SIGNING_KEY, else the public development key
TS = run_timestamp()  # when this run happened (BENCH_TIMESTAMP pins it)

_RUN51 = (
    "import os, sys\n"
    "from swmm.toolkit import solver\n"
    "os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))\n"
    "solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n"
    "print(solver.swmm_version_info())\n"
)


def run_swmm51(py: str, inp: Path, out_parquet: Path) -> str:
    with tempfile.TemporaryDirectory() as td:
        rpt, out = Path(td) / "m.rpt", Path(td) / "m.out"
        res = subprocess.run([py, "-c", _RUN51, str(inp.resolve()), str(rpt), str(out)], capture_output=True, text=True, check=True)
        version = res.stdout.strip().split()[-1].split("data")[-1]
        swmm5.adapt_out_to_parquet(out, out_parquet)
    return version


def run_epanet20(inp: Path, out_parquet: Path, wntr_sim: bool = False) -> None:
    """EPANET 2.0 through WNTR, or (``wntr_sim``) WNTR's own Python hydraulic solver, the WNTRSimulator."""
    import numpy as np
    import wntr

    from benchmark1d2d.io.results import write_results_parquet

    wn = wntr.network.WaterNetworkModel(str(inp))
    with tempfile.TemporaryDirectory() as td:  # keep WNTR scratch files out of the repo
        res = (wntr.sim.WNTRSimulator(wn).run_sim() if wntr_sim
               else wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(Path(td) / "run"), version=2.0))
    head, pres, flow, vel = res.node["head"], res.node["pressure"], res.link["flowrate"], res.link["velocity"]
    t = head.index.to_numpy(float)
    n = len(t)
    cols: dict[str, list] = {k: [] for k in ("t", "x", "h", "u", "p", "Q", "element_id", "element_type")}
    k = 0
    for name in head.columns:
        cols["t"].append(t); cols["h"].append(head[name].to_numpy(float)); cols["p"].append(pres[name].to_numpy(float) * 9810.0)
        cols["u"].append(np.full(n, np.nan)); cols["Q"].append(np.full(n, np.nan))
        cols["element_id"].append([str(name)] * n); cols["element_type"].append(["node"] * n); cols["x"].append(np.full(n, float(k))); k += 1
    for name in flow.columns:
        cols["t"].append(t); cols["h"].append(np.full(n, np.nan)); cols["p"].append(np.full(n, np.nan))
        cols["u"].append(vel[name].to_numpy(float)); cols["Q"].append(flow[name].to_numpy(float))
        cols["element_id"].append([str(name)] * n); cols["element_type"].append(["link"] * n); cols["x"].append(np.full(n, float(k))); k += 1
    flat = {c: (np.concatenate(v) if c not in ("element_id", "element_type") else sum(v, [])) for c, v in cols.items()}
    flat["y"] = np.zeros(len(flat["t"]))
    flat["v"] = np.full(len(flat["t"]), np.nan)
    write_results_parquet(out_parquet, flat)


def save(card: dict) -> None:
    p = OUT / f"{card['test_id']}.scorecard.json"
    p.write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {card['test_id']} ({card['solver']['name']})")
    for r in card["criteria_results"]:
        print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']} — {r.get('detail', '')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--swmm51-python", help="Python with swmm-toolkit==0.10.0 (EPA SWMM 5.1.15)")
    ap.add_argument("--openswmm-python", help="Python with the openswmm wheel (OpenSWMM Engine v6)")
    ap.add_argument("--only-openswmm", action="store_true", help="run only the OpenSWMM v6 cases")
    ap.add_argument("--hydra-exe", help="the hydra CLI (NEER AI Hydra): its drainage and water-distribution engines")
    ap.add_argument("--only-hydra", action="store_true", help="run only the Hydra cases")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.hydra_exe:
        from benchmark1d2d.adapters import hydra

        outh = REPO / "out" / "hydra"
        outh.mkdir(parents=True, exist_ok=True)
        ver = hydra.version(args.hydra_exe)
        names = {"uds": "urban drainage", "wds": "water distribution"}
        for tid, eng in (("B-EXTRAN-001", "uds"), ("B-RTC-001", "uds"), ("B-EPANET-001", "wds")):
            m = load_manifest(tid, repo=REPO)
            inp = Path(m["_case_dir"]) / "inputs/network.inp"
            if not inp.is_file():
                subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_inputs.py"), tid], check=True)
            res = hydra.adapt(inp, outh / f"{m['test_id']}.hydra.parquet", exe=args.hydra_exe, engine=eng)
            card = score_case(m, res, timestamp=TS, private_key=KEY,
                              solver={"name": f"Hydra {ver.split('/')[0]} {names[eng]}", "version": ver,
                                      "adapter": f"hydra CLI {ver.split('/')[-1]} ({eng} engine, {'EPANET' if eng == 'wds' else 'SWMM'}-format binary output)"})
            (outh / f"{card['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {card['test_id']} ({card['solver']['name']})")
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']} — {r.get('detail', '')}")
    if args.only_hydra:
        return 0
    if args.openswmm_python:
        from benchmark1d2d.adapters import openswmm

        out6 = REPO / "out" / "openswmm"
        out6.mkdir(parents=True, exist_ok=True)
        for tid in ("B-EXTRAN-001", "B-RTC-001"):
            m = load_manifest(tid, repo=REPO)
            inp = Path(m["_case_dir"]) / "inputs/network.inp"
            if not inp.is_file():
                subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_inputs.py"), tid], check=True)
            res = out6 / f"{m['test_id']}.openswmm.parquet"
            with tempfile.TemporaryDirectory() as td:
                version = openswmm.run(args.openswmm_python, inp, Path(td) / "m.rpt", Path(td) / "m.out")
                swmm5.adapt_out_to_parquet(Path(td) / "m.out", res)
            card = score_case(m, res, timestamp=TS, private_key=KEY,
                              solver={"name": f"OpenSWMM Engine {version}", "version": version, "adapter": "openswmm (v6 engine, SWMM binary output)"})
            (out6 / f"{card['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {card['test_id']} ({card['solver']['name']})")
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']} — {r.get('detail', '')}")
        # the same engine with its new finite-volume routing (FLOW_ROUTING FV): a different numerical method,
        # so differences from SWMM 5.2.4 are expected; reported as a finding
        import corpus_parity

        outf = REPO / "out" / "openswmm_fv"
        outf.mkdir(parents=True, exist_ok=True)
        for tid in ("B-EXTRAN-001", "B-RTC-001"):
            m = load_manifest(tid, repo=REPO)
            inp = Path(m["_case_dir"]) / "inputs/network.inp"
            res = outf / f"{m['test_id']}.openswmm-fv.parquet"
            with tempfile.TemporaryDirectory() as td:
                fv_inp, _ = corpus_parity.with_routing(inp, "FV", Path(td))
                try:
                    version = openswmm.run(args.openswmm_python, fv_inp, Path(td) / "m.rpt", Path(td) / "m.out")
                    swmm5.adapt_out_to_parquet(Path(td) / "m.out", res)
                except Exception as exc:  # noqa: BLE001 - an engine that cannot run a model is a finding
                    print(f"OpenSWMM FV did not run {tid}: {str(exc)[-400:]}")
                    continue
            ver = version.replace("openswmm", "").strip()
            card = score_case(m, res, timestamp=TS, private_key=KEY,
                              solver={"name": f"OpenSWMM Engine v6 finite volume ({ver})", "version": ver,
                                      "adapter": "openswmm (v6 engine, FLOW_ROUTING FV, SWMM binary output)"})
            (outf / f"{card['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {card['test_id']} ({card['solver']['name']})")
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']} — {r.get('detail', '')}")
    if args.only_openswmm:
        return 0
    for tid in ("B-EXTRAN-001", "B-RTC-001"):
        if not args.swmm51_python:
            print(f"skip {tid}: no --swmm51-python")
            continue
        m = load_manifest(tid, repo=REPO)
        inp = Path(m["_case_dir"]) / "inputs/network.inp"
        if not inp.is_file():
            subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_inputs.py"), tid], check=True)
        res = OUT / f"{m['test_id']}.swmm515.parquet"
        version = run_swmm51(args.swmm51_python, inp, res)
        save(score_case(m, res, timestamp=TS, private_key=KEY,
                        solver={"name": f"EPA SWMM {version}", "version": version, "adapter": "swmm5 (swmm-toolkit 0.10.0)"}))
    m = load_manifest("B-EPANET-001", repo=REPO)
    res = OUT / f"{m['test_id']}.epanet20.parquet"
    run_epanet20(Path(m["_case_dir"]) / "inputs/network.inp", res)
    save(score_case(m, res, timestamp=TS, private_key=KEY, solver={"name": "EPANET 2.0", "version": "2.00.12", "adapter": "epanet (wntr libepanet2)"}))
    # WNTR's own hydraulic solver (an independent implementation of the network equations, in Python)
    import wntr

    outw = REPO / "out" / "wntr"
    outw.mkdir(parents=True, exist_ok=True)
    res = outw / f"{m['test_id']}.wntr.parquet"
    try:
        run_epanet20(Path(m["_case_dir"]) / "inputs/network.inp", res, wntr_sim=True)
        card = score_case(m, res, timestamp=TS, private_key=KEY,
                          solver={"name": f"WNTR {wntr.__version__} WNTRSimulator", "version": wntr.__version__,
                                  "adapter": "wntr.sim.WNTRSimulator (WNTR's own Newton solver, in Python)"})
        (outw / f"{card['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {card['test_id']} ({card['solver']['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']} — {r.get('detail', '')}")
    except Exception as exc:  # noqa: BLE001 - a solver that cannot run the network is a finding
        print(f"WNTRSimulator did not run B-EPANET-001: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
