#!/usr/bin/env python3
"""Score EPA EPANET 2.2 on the Track A pressurized-network verification cases.

EPANET is the candidate here, not the reference: each case's truth is an
exact solution (Colebrook–White pipe friction for A1P-001; the Todini–Pilati
network solved to 1e-12 m for A1P-010). The model is written as an EPANET
input file from the case inputs and run with the EPANET 2.2 library bundled
in WNTR, so this is the real engine a utility would use.

Score cards go to ``out/networks/``.

Usage::

    python scripts/run_network_cases.py
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import warnings

import numpy as np

warnings.filterwarnings("ignore", message="Changing the headloss formula")

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from benchmark1d2d.catalog import load_manifest  # noqa: E402
from benchmark1d2d.io.results import write_results_parquet  # noqa: E402
from benchmark1d2d.scoring.scorer import score_case  # noqa: E402

OUT = REPO / "out" / "networks"
KEY = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
TS = "2024-01-01T00:00:00Z"
# EPANET's built-in water viscosity (1.1e-5 ft²/s); [OPTIONS] VISCOSITY is relative to it.
EPANET_NU = 1.1e-5 * 0.3048**2
SOLVER = {"name": "EPA EPANET 2.2", "version": "2.2", "adapter": "epanet (WNTR 1.5.0, libepanet22)"}


HYDRA_EXE: str | None = None  # set by --hydra-exe: run NEER AI Hydra's wds engine instead of EPANET 2.2


def _with_coordinates(text: str) -> str:
    """Add a schematic map (no effect on the run) before [END], so the file opens as a network in EPANET."""
    from benchmark1d2d.io.layout import coordinates_section, layout

    sec, nodes, links = None, [], []
    for line in text.splitlines():
        s = line.split(";", 1)[0].strip()
        if s.startswith("["):
            sec = s.strip("[]").upper()
        elif s and sec in ("JUNCTIONS", "RESERVOIRS", "TANKS"):
            nodes.append(s.split()[0])
        elif s and sec in ("PIPES", "PUMPS", "VALVES"):
            t = s.split()
            links.append((t[1], t[2], float(t[3]) if sec == "PIPES" else None))
    return text.replace("[END]", "\n".join(coordinates_section(layout(nodes, links))[1:]) + "\n[END]")


def _run_inp(text: str, test: str = ""):
    import wntr

    text = _with_coordinates(text)
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "model.inp"
        inp.write_text(text, encoding="utf-8")
        if test:
            from benchmark1d2d import keep as kept

            kept.inputs("hydra-wds" if HYDRA_EXE else "epanet22", test, Path(td), "model", files=["model.inp"])
        if HYDRA_EXE:
            from benchmark1d2d.adapters import hydra

            hydra.run(HYDRA_EXE, inp, Path(td) / "m.rpt", Path(td) / "m.out", "wds")
            return hydra.epanet_results(Path(td) / "m.out")
        wn = wntr.network.WaterNetworkModel(str(inp))
        res = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(Path(td) / "run"), version=2.2)
    return res


def _frame(rows: list[dict]) -> dict:
    cols = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "Q", "element_id", "element_type")}
    for r in rows:
        for k in cols:
            cols[k].append(r.get(k, np.nan) if k not in ("element_id", "element_type") else r[k])
    return {k: (np.asarray(v, dtype=float) if k not in ("element_id", "element_type") else v) for k, v in cols.items()}


def single_pipe(case_dir: Path, segments: int = 10) -> dict:
    """A1P-001: reservoir, a pipe split into equal segments, withdrawal at the end."""
    prm = json.loads((case_dir / "inputs" / "params.json").read_text(encoding="utf-8"))
    L, D, eps = prm["pipe"]["L_m"], prm["pipe"]["D_m"], prm["pipe"]["roughness_m"]
    nu = prm["fluid"]["kinematic_viscosity_m2s"]
    H0 = prm["boundaries"]["upstream"]["head_m"]
    Q = prm["boundaries"]["downstream"]["velocity_ms"] * math.pi * D * D / 4.0
    j = [f"N{i}" for i in range(1, segments + 1)]
    lines = ["[TITLE]", "A1P-001 single pipe", "[JUNCTIONS]"]
    lines += [f"{n} 0 {Q * 1000.0 if i == segments - 1 else 0.0:.9f}" for i, n in enumerate(j)]
    lines += ["[RESERVOIRS]", f"R {H0}", "[PIPES]"]
    nodes = ["R"] + j
    for i in range(segments):
        lines.append(f"P{i + 1} {nodes[i]} {nodes[i + 1]} {L / segments} {D * 1000.0} {eps * 1000.0} 0 Open")
    lines += ["[OPTIONS]", "Units LPS", "Headloss D-W", f"Viscosity {nu / EPANET_NU:.9f}", "Accuracy 0.000001",
              "[TIMES]", "Duration 0", "[END]"]
    res = _run_inp("\n".join(lines) + "\n", "A1P-001")
    head = res.node["head"].iloc[0]
    rows = [{"t": 0.0, "x": L * i / segments, "y": 0.0, "h": float(head[n]), "p": float(head[n]) * 9810.0,
             "element_id": n, "element_type": "node"} for i, n in enumerate(nodes)]
    flow = res.link["flowrate"].iloc[0]
    rows += [{"t": 0.0, "x": L * (i + 0.5) / segments, "y": 0.0, "Q": float(flow[f"P{i + 1}"]),
              "element_id": f"P{i + 1}", "element_type": "link"} for i in range(segments)]
    # Score heads at nodes only: drop link rows from the analytic comparison.
    return _frame([r for r in rows if r["element_type"] == "node"])


def two_loop(case_dir: Path) -> dict:
    """A1P-010: the Alperovits–Shamir two-loop network as an EPANET input file."""
    net = json.loads((case_dir / "inputs" / "network.json").read_text(encoding="utf-8"))
    lines = ["[TITLE]", "A1P-010 two-loop network", "[JUNCTIONS]"]
    lines += [f"{j['id']} {j['elevation']} {j['demand_m3s'] * 1000.0:.9f}" for j in net["junctions"]]
    lines += ["[RESERVOIRS]"] + [f"{r['id']} {r['head']}" for r in net["reservoirs"]]
    lines += ["[PIPES]"] + [f"{p['id']} {p['from']} {p['to']} {p['L']} {p['D'] * 1000.0} {p['C']} 0 Open" for p in net["pipes"]]
    lines += ["[OPTIONS]", "Units LPS", "Headloss H-W", "Accuracy 0.000001", "[TIMES]", "Duration 0", "[END]"]
    res = _run_inp("\n".join(lines) + "\n", "A1P-010")
    head, flow = res.node["head"].iloc[0], res.link["flowrate"].iloc[0]
    nodes = [r["id"] for r in net["reservoirs"]] + [j["id"] for j in net["junctions"]]
    rows = [{"t": 0.0, "x": float(i), "y": 0.0, "h": float(head[n]), "element_id": n, "element_type": "node"}
            for i, n in enumerate(nodes)]
    rows += [{"t": 0.0, "x": float(len(nodes) + i), "y": 0.0, "Q": float(flow[p["id"]]), "element_id": p["id"],
              "element_type": "link"} for i, p in enumerate(net["pipes"])]
    return _frame(rows)


def main() -> int:
    import argparse

    global HYDRA_EXE
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hydra-exe", help="score NEER AI Hydra's water-distribution engine (the hydra CLI) instead of EPANET 2.2")
    args = ap.parse_args()
    HYDRA_EXE = args.hydra_exe
    out_dir, solver, tag = OUT, SOLVER, "epanet22"
    if HYDRA_EXE:
        from benchmark1d2d.adapters import hydra

        ver = hydra.version(HYDRA_EXE)
        out_dir, tag = REPO / "out" / "hydra_networks", "hydra"
        solver = {"name": f"Hydra {ver.split('/')[0]} water distribution", "version": ver,
                  "adapter": f"hydra CLI {ver.split('/')[-1]} (wds engine, EPANET-format binary output)"}
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for tid, build in (("A1P-001", single_pipe), ("A1P-010", two_loop)):
        m = load_manifest(tid, repo=REPO)
        res = out_dir / f"{m['test_id']}.{tag}.parquet"
        write_results_parquet(res, build(Path(m["_case_dir"])))
        card = score_case(m, res, timestamp=TS, private_key=KEY, solver=solver)
        (out_dir / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']:.4g} {r['threshold']['units']} — {r.get('detail', '')}")
        ok &= card["passed"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
