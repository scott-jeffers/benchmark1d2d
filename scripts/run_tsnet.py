#!/usr/bin/env python3
"""Score TSNet, an open-source water-hammer solver (method of characteristics), on A1P-020.

TSNet (Xing and Sela, 2020; ``pip install tsnet``) builds a transient model on
top of an EPANET network (through WNTR) and solves the water-hammer equations
along every pipe by the method of characteristics. A1P-020 is written as an
EPANET network: a reservoir, the 1 km pipe split into reaches of the grid's
length (so heads are reported at every grid point), and a throttle valve at the
far end discharging to a lower reservoir. Friction is made negligible
(Hazen-Williams C = 10,000: 0.3 mm of head over the pipe at 1 m/s), the wave
speed is 1,000 m/s, and the valve's opening is chosen so the steady velocity is
1.000 m/s. The valve closes in one time step at t = 0.

TSNet 0.3.1 needs NumPy 1.x, so it runs in its own environment
(``--tsnet-python``: a Python with ``tsnet==0.3.1`` and ``numpy<2``); this
script, under the suite's own Python, writes the network, reads TSNet's heads
and velocities back and scores them.

Score cards go to ``out/tsnet/``. Usage::

    python3.11 -m venv .venv-tsnet && .venv-tsnet/bin/pip install "numpy<2" "tsnet==0.3.1"
    python scripts/run_tsnet.py --tsnet-python .venv-tsnet/bin/python
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "tsnet"
from benchmark1d2d.clock import run_timestamp  # noqa: E402

TS = run_timestamp()  # when this run happened (BENCH_TIMESTAMP pins it)
G = 9.81
D = 1.0  # pipe diameter [m]: any; only the velocity matters
C_HW = 10000.0


def network(L: float, dx: float, V0: float) -> tuple[str, list[str]]:
    n = int(round(L / dx))
    A = math.pi * D * D / 4
    Q = V0 * A
    # head drop across a TCV of loss coefficient K: K V²/2g; the pipe's own loss is negligible
    K = 100.0  # most of the head drop is in the valve, so the small pipe loss hardly moves the steady velocity
    h_up = 100.0
    hf = 10.67 * L * Q**1.852 / (C_HW**1.852 * D**4.87)
    h_dn = h_up - hf - K * V0 * V0 / (2 * G)
    nodes = [f"J{i}" for i in range(1, n + 1)]
    lines = ["[TITLE]", "A1P-020 water hammer", "[JUNCTIONS]"] + [f"{j} 0 0" for j in nodes]
    lines += ["[RESERVOIRS]", f"R1 {h_up:.9f}", f"R2 {h_dn:.9f}", "[PIPES]"]
    chain = ["R1"] + nodes
    for i in range(n):
        lines.append(f"P{i + 1} {chain[i]} {chain[i + 1]} {L / n:.9f} {D * 1000:.3f} {C_HW:g} 0 Open")
    lines += ["[VALVES]", f"V1 {nodes[-1]} R2 {D * 1000:.3f} TCV {K:g} 0"]
    lines += ["[OPTIONS]", "Units LPS", "Headloss H-W", "Accuracy 0.0000001", "[TIMES]", "Duration 0", "[COORDINATES]"]
    lines += [f"R1 0 0"] + [f"{j} {L * (i + 1) / n:.6f} 0" for i, j in enumerate(nodes)] + [f"R2 {L + 10:.6f} 0", "[END]"]
    return "\n".join(lines) + "\n", ["R1"] + nodes


_WORKER = r"""
import sys, json, numpy as np, tsnet
inp, out, a, t_end, dt, n = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
tm = tsnet.network.TransientModel(inp)
tm.set_wavespeed(a)
tm.set_time(t_end + dt, dt)  # include t_end itself
tm.valve_closure("V1", [dt, 0.0, 0.0, 1])  # shut in one time step, starting at t = 0
tm = tsnet.simulation.Initializer(tm, 0.0, "DD")
tm = tsnet.simulation.MOCSimulator(tm, out + ".results", "steady")
t = np.asarray(tm.simulation_timestamps, float)
k = int(np.argmin(np.abs(t - t_end)))
nodes = ["R1"] + ["J%d" % i for i in range(1, n + 1)]
head = [float(tm.get_node(nd).head[k] - tm.get_node(nd).head[0]) for nd in nodes]
vel = [float(tm.get_link("P%d" % (i + 1)).start_node_velocity[k]) for i in range(n)]
vel.append(float(tm.get_link("P%d" % n).end_node_velocity[k]))
json.dump({"t": float(t[k]), "head": head, "u": vel, "dt": float(tm.time_step)}, open(out, "w"))
"""


def run(m: dict, dx: float, td: Path, tsnet_python: str) -> dict:
    import subprocess

    prm = json.loads((Path(m["_case_dir"]) / "inputs" / "params.json").read_text(encoding="utf-8"))
    L, a, V0, rho = prm["pipe"]["L_m"], prm["pipe"]["wave_speed_ms"], prm["initial_condition"]["V0_ms"], prm["fluid"]["rho_kgm3"]
    t_end = float(m["simulation"]["t_end"])
    text, nodes = network(L, dx, V0)
    inp = td / "model.inp"
    inp.write_text(text, encoding="ascii")
    from benchmark1d2d import keep

    keep.inputs("tsnet", m["test_id"].split("_")[0], td, f"dx{dx:g}", files=["model.inp"])
    dt = dx / a / 2.0  # TSNet needs at least two characteristic steps per reach
    out = td / "res.json"
    p = subprocess.run([tsnet_python, "-c", _WORKER, str(inp), str(out), str(a), str(t_end), str(dt), str(len(nodes) - 1)],
                       capture_output=True, text=True, cwd=td)
    if p.returncode != 0 or not out.is_file():
        raise RuntimeError((p.stdout + p.stderr)[-1500:])
    r = json.loads(out.read_text())
    return {"t": r["t"], "x": np.linspace(0.0, L, len(nodes)), "p": rho * G * np.asarray(r["head"]), "u": np.asarray(r["u"])}


def main() -> int:
    from benchmark1d2d.signing import private_key as signing_key
    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tsnet-python", required=True, help="a Python with tsnet==0.3.1 and numpy<2")
    args = ap.parse_args()
    key = signing_key()  # BENCH_SIGNING_KEY, else the public development key
    m = load_manifest("A1P-020", repo=REPO)
    OUT.mkdir(parents=True, exist_ok=True)
    import subprocess

    version = subprocess.run([args.tsnet_python, "-c", "import importlib.metadata as m; print(m.version('tsnet'))"],
                             capture_output=True, text=True, check=True).stdout.strip()
    paths = []
    for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as tdn:
            r = run(m, float(dx), Path(tdn), args.tsnet_python)
        n = len(r["x"])
        nan = np.full(n, np.nan)
        paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx:g}.parquet",
                                           {"t": np.full(n, r["t"]), "x": r["x"], "y": nan, "h": nan, "u": r["u"], "v": nan, "p": r["p"]}, wall_seconds=time.perf_counter() - t0))
        print(f"  tsnet dx={dx}: {time.perf_counter() - t0:.1f}s, peak {np.nanmax(r['p']) / 1e6:.4f} MPa at t={r['t']:g}")
    solver = {"name": f"TSNet {version}", "version": version,
              "adapter": "tsnet (method of characteristics on a WNTR network; the pipe split into reaches of the grid length)"}
    card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
    (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
    for c in card["criteria_results"]:
        print(f"    [{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['observed']} {c['threshold']['units']}  {c.get('detail', '')}")
    print(f"    convergence {card.get('convergence_result', {}).get('observed_order')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
