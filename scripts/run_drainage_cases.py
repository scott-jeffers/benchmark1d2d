#!/usr/bin/env python3
"""Score SWMM-family engines on the exact drainage-network cases (A1D-*).

Each case's network (``inputs/network.json``) is written as a SWMM input file
— the same file for every engine — and run with:

* ``swmm524``      EPA SWMM 5.2.4 (``swmm-toolkit`` 0.17.0), dynamic wave
* ``openswmm-dw``  OpenSWMM Engine v6, dynamic wave (``--openswmm-python``)
* ``openswmm-fv``  OpenSWMM Engine v6, finite-volume routing
* ``hydra-uds``    NEER AI Hydra's urban-drainage engine (``--hydra-exe``)

Node depths, conduit depths and link flows at the final reporting time are
scored against the case's exact answer (``references.drainage``). Options
beyond the engines' defaults: ``ROUTING_STEP 1`` s with the default variable
step, ``MINIMUM_STEP 0.01`` s, ``LINK_OFFSETS DEPTH``, junction rims 10 m
above the invert (nothing floods), and no losses at junctions. OpenSWMM's
finite-volume routing keeps its default cells per pipe (the channel cases
force one cell per conduit to match their grids).

Score cards go to ``out/swmm_track_a/<engine>/``, next to the open-channel
cases. Usage::

    python scripts/run_drainage_cases.py [A1D-001 ...] [--engines swmm524 ...]
        [--openswmm-python PY] [--hydra-exe EXE]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

OUT = REPO / "out" / "swmm_track_a"  # same engines and score-card folders as the open-channel cases
TS = "2024-01-01T00:00:00Z"
CASES = ["A1D-001", "A1D-002", "A1D-003", "A1D-004", "A1D-005"]


def _hms(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def write_inp(net: dict, path: Path, routing: str, variable_step: float = 0.75, extra_options: tuple = (), coordinates: bool = True) -> None:
    """A SWMM 5 input file for a drainage network.json.

    An inflow is constant (``Q``) or a hydrograph (``series``: [[t_s, Q], …],
    linear between points). ``variable_step=0`` fixes the routing step at 1 s
    (the coupled cases exchange water with the surface every second).
    """
    opts = ["[OPTIONS]", "FLOW_UNITS CMS", "INFILTRATION HORTON", f"FLOW_ROUTING {routing}", "LINK_OFFSETS DEPTH",
            "START_DATE 01/01/2000", "START_TIME 00:00:00", "REPORT_START_DATE 01/01/2000", "REPORT_START_TIME 00:00:00",
            "END_DATE 01/01/2000", f"END_TIME {_hms(net['duration_s'])}", "DRY_DAYS 0",
            f"REPORT_STEP {_hms(net['report_step_s'])}", "WET_STEP 00:05:00", "DRY_STEP 01:00:00",
            "ROUTING_STEP 1", f"VARIABLE_STEP {variable_step:g}", *extra_options, "MINIMUM_STEP 0.01", "ALLOW_PONDING NO", "INERTIAL_DAMPING PARTIAL",
            "NORMAL_FLOW_LIMITED BOTH", "MAX_TRIALS 8", "HEAD_TOLERANCE 0.0005", "SYS_FLOW_TOL 5", "LAT_FLOW_TOL 5", "THREADS 1"]
    L = opts + ["", "[JUNCTIONS]", ";;Name Elev MaxDepth InitDepth SurDepth Aponded"]
    L += [f"{j['id']} {j['invert']:.6f} {j.get('max_depth', 10.0):g} {j.get('init_depth', 0.0):g} {j.get('surcharge_depth', 0):g} 0" for j in net.get("junctions", [])]
    L += ["", "[OUTFALLS]", ";;Name Elev Type Stage Gated"]
    for o in net.get("outfalls", []):
        gate = "YES" if o.get("gated") else "NO"
        L.append(f"{o['id']} {o['invert']:.6f} {o['type']} {o['stage']:.6f} {gate}" if o["type"] == "FIXED"
                 else f"{o['id']} {o['invert']:.6f} {o['type']} {gate}")
    if net.get("storages"):
        L += ["", "[STORAGE]", ";;Name Elev MaxDepth InitDepth Shape Coeff Expon Const SurDepth Fevap"]
        L += [f"{s['id']} {s['invert']:.6f} {s['max_depth']:g} {s['init_depth']:g} FUNCTIONAL {s['area']:g} 0 0 0 0"
              for s in net["storages"]]
    if net.get("conduits"):
        L += ["", "[CONDUITS]", ";;Name From To Length Roughness InOffset OutOffset InitFlow MaxFlow"]
        L += [f"{c['id']} {c['from']} {c['to']} {c['length']:g} {c['n']:g} {c.get('in_offset', 0):g} {c.get('out_offset', 0):g} 0 0"
              for c in net["conduits"]]
        L += ["", "[XSECTIONS]", ";;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels"]
        L += [f"{c['id']} CIRCULAR {c['D']:g} 0 0 0 1" for c in net["conduits"]]
    if net.get("outlets"):
        L += ["", "[OUTLETS]", ";;Name From To Offset Type Coeff Expon Gated"]
        L += [f"{o['id']} {o['from']} {o['to']} {o.get('offset', 0):g} FUNCTIONAL/DEPTH {o['C']:g} {o['exponent']:g} NO"
              for o in net["outlets"]]
    if net.get("pumps"):
        L += ["", "[PUMPS]", ";;Name From To Curve Status Startup Shutoff"]
        L += [f"{p['id']} {p['from']} {p['to']} {p['id']}_CURVE ON 0 0" for p in net["pumps"]]
        L += ["", "[CURVES]", ";;Name Type X Y"]
        for p in net["pumps"]:
            for k, (head, q) in enumerate(sorted(p["curve"])):
                L.append(f"{p['id']}_CURVE {'PUMP3' if k == 0 else ''} {head:g} {q:g}")
    if net.get("inflows"):
        L += ["", "[INFLOWS]", ";;Node Constituent TimeSeries Type Mfactor Sfactor Baseline"]
        L += [f'{i["node"]} FLOW "" FLOW 1.0 1.0 {i["Q"]:g}' if "series" not in i else f'{i["node"]} FLOW TS_{i["node"]} FLOW 1.0 1.0 0'
              for i in net["inflows"]]
        series = [i for i in net["inflows"] if "series" in i]
        if series:
            L += ["", "[TIMESERIES]", ";;Name Date Time Value"]
            L += [f"TS_{i['node']} {t / 3600.0:.6f} {q:g}" for i in series for t, q in i["series"]]
    L += ["", "[REPORT]", "INPUT NO", "CONTROLS NO", "NODES ALL", "LINKS ALL"]
    if coordinates:  # a schematic map (no effect on the run), so the file opens as a network in EPA SWMM
        from benchmark1d2d.io.layout import coordinates_section, layout

        nodes = [n["id"] for k in ("junctions", "outfalls", "storages") for n in net.get(k, [])]
        links = [(c["from"], c["to"], c["length"]) for c in net.get("conduits", [])]
        links += [(o["from"], o["to"], None) for k in ("outlets", "pumps") for o in net.get(k, [])]
        L += coordinates_section(layout(nodes, links))
    path.write_text("\n".join(L) + "\n", encoding="ascii")


def read_final(out: Path) -> tuple[float, dict]:
    """Node depths, link depths and link flows at the last reporting period."""
    from swmm.toolkit import output, shared_enum as se

    h = output.init()
    output.open(h, str(out))
    try:
        _, n_node, n_link, *_ = output.get_proj_size(h)
        n_per = output.get_times(h, se.Time.NUM_PERIODS)
        step = output.get_times(h, se.Time.REPORT_STEP)
        nodes = [output.get_elem_name(h, se.ElementType.NODE, i) for i in range(n_node)]
        links = [output.get_elem_name(h, se.ElementType.LINK, i) for i in range(n_link)]
        nd = np.asarray(output.get_node_attribute(h, n_per - 1, se.NodeAttribute.INVERT_DEPTH), float)
        ld = np.asarray(output.get_link_attribute(h, n_per - 1, se.LinkAttribute.FLOW_DEPTH), float)
        lq = np.asarray(output.get_link_attribute(h, n_per - 1, se.LinkAttribute.FLOW_RATE), float)
    finally:
        output.close(h)
    return float(n_per * step), {"nodes": nodes, "node_h": nd, "links": links, "link_h": ld, "link_q": lq}


def read_series(out: Path, max_elements: int = 12) -> dict | None:
    """Every reporting period of node depths and link flows, for small networks (the site's time charts)."""
    from swmm.toolkit import output, shared_enum as se

    h = output.init()
    output.open(h, str(out))
    try:
        _, n_node, n_link, *_ = output.get_proj_size(h)
        if n_node + n_link > max_elements:
            return None
        n_per = output.get_times(h, se.Time.NUM_PERIODS)
        step = output.get_times(h, se.Time.REPORT_STEP)
        nodes = [output.get_elem_name(h, se.ElementType.NODE, i) for i in range(n_node)]
        links = [output.get_elem_name(h, se.ElementType.LINK, i) for i in range(n_link)]
        nd = {n: [float(v) for v in output.get_node_series(h, i, se.NodeAttribute.INVERT_DEPTH, 0, n_per - 1)] for i, n in enumerate(nodes)}
        lq = {n: [float(v) for v in output.get_link_series(h, i, se.LinkAttribute.FLOW_RATE, 0, n_per - 1)] for i, n in enumerate(links)}
    finally:
        output.close(h)
    return {"t": [float((k + 1) * step) for k in range(n_per)], "node_h": nd, "link_q": lq}


def to_columns(t: float, r: dict) -> dict:
    nn, nl = len(r["nodes"]), len(r["links"])
    nan = np.full(nn + nl, np.nan)
    return {"t": np.full(nn + nl, t), "x": np.arange(nn + nl, dtype=float), "y": nan.copy(),
            "h": np.concatenate([r["node_h"], r["link_h"]]), "u": nan.copy(), "v": nan.copy(), "p": nan.copy(),
            "Q": np.concatenate([np.full(nn, np.nan), r["link_q"]]),
            "element_id": list(r["nodes"]) + list(r["links"]), "element_type": ["node"] * nn + ["link"] * nl}


def main() -> int:
    from run_swmm_track_a import ENGINES, run_engine  # same engine wrappers as the open-channel cases
    import run_swmm_track_a

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=CASES)
    ap.add_argument("--engines", nargs="+", choices=list(ENGINES), default=list(ENGINES))
    ap.add_argument("--openswmm-python", help="Python with the openswmm wheel")
    ap.add_argument("--hydra-exe", help="the hydra CLI (NEER AI Hydra)")
    ap.add_argument("--swmm51-python", help="Python with swmm-toolkit==0.10.0 (EPA SWMM 5.1.15)")
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    run_swmm_track_a.HYDRA_EXE = args.hydra_exe
    run_swmm_track_a.SWMM51_PYTHON = args.swmm51_python
    engines = [e for e in args.engines
               if e == "swmm524" or (e == "hydra-uds" and args.hydra_exe) or (e.startswith("openswmm") and args.openswmm_python)
               or (e == "swmm515" and args.swmm51_python)]
    for engine in engines:
        out = OUT / engine
        out.mkdir(parents=True, exist_ok=True)
        for tid in args.cases:
            m = load_manifest(tid, repo=REPO)
            net = json.loads((Path(m["_case_dir"]) / "inputs" / "network.json").read_text(encoding="utf-8"))
            with tempfile.TemporaryDirectory() as tdn:
                td = Path(tdn)
                write_inp(net, td / "m.inp", ENGINES[engine]["routing"])
                from benchmark1d2d import keep

                keep.inputs(engine, tid, td, files=["m.inp"])
                try:
                    o, version = run_engine(engine, td / "m.inp", td, args.openswmm_python)
                    t, r = read_final(o)
                    series = read_series(o)
                except Exception as exc:  # noqa: BLE001 - an engine that cannot run a case is a finding
                    print(f"  {engine} {tid}: did not run: {str(exc)[-600:]}")
                    continue
            res = write_results_parquet(out / f"{m['test_id']}.parquet", to_columns(t, r))
            if series:  # time series of small networks, for the site's charts
                (out / f"{m['test_id']}.series.json").write_text(json.dumps(series, separators=(",", ":")) + "\n", encoding="utf-8")
            ver = version.replace("openswmm", "").strip()
            solver = {"name": f"{ENGINES[engine]['label']}" + (f" ({ver})" if engine not in ("swmm524", "swmm515") else ""), "version": ver,
                      "adapter": f"swmm ({ENGINES[engine]['routing']} routing, network.json as a SWMM input file)"}
            card = score_case(m, res, timestamp=TS, private_key=key, solver=solver)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
            for c in card["criteria_results"]:
                print(f"    [{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['observed']} {c['threshold']['units']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
