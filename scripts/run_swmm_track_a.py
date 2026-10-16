#!/usr/bin/env python3
"""Score SWMM engines on the 1D open-channel physics cases (Track A).

SWMM is a link-node network model, so each case's channel is written as a
chain of rectangular open conduits, one per grid cell: nodes sit on the cell
faces, conduit *i* spans cell *i*, and the conduit's depth and velocity are
reported at the cell centre — the same points every other solver reports on.

Engines (each run with its own defaults; only the time-step limits below are
set so that a run can follow a 1 s wave on a 1.25 m grid):

* ``swmm524``      EPA SWMM 5.2.4 (``swmm-toolkit`` 0.17.0), dynamic wave
* ``openswmm-dw``  OpenSWMM Engine v6 (HydroCouple), dynamic wave
* ``openswmm-fv``  OpenSWMM Engine v6, its explicit finite-volume routing
                   (``FLOW_ROUTING FV``, one cell per conduit)
* ``hydra-uds``    NEER AI Hydra's urban-drainage engine (Preissmann-slot
                   dynamic wave), through its CLI (``--hydra-exe``)

Cases
-----
A1F-010 / A1F-011  dam breaks, frictionless (n = 0.0001, the smallest EPA
        SWMM accepts). The dam sits on a cell
        face; a conduit one-twentieth of a cell long straddles it, so every
        full cell starts at a single depth (SWMM sets a conduit's initial
        depth to the mean of its two end nodes).
A1F-001 MacDonald backwater: bed shaped to the exact profile, Manning
        n = 0.03, a 100 km wide channel so the hydraulic radius equals the
        depth (as the reference assumes), constant inflow upstream, fixed
        water level downstream, run for the case's hour.

A1F-040–043 SWASHES bump channel (frictionless, n = 0.0001): steady flow
        over the bump with inflow q upstream and a fixed stage (or free
        outfall) downstream; the lake at rest is held by a fixed stage at its
        own level. ``MIN_SURFAREA`` is set to 0.001 m²: on 5 cm conduits
        SWMM's default (1.17 m²) exceeds a node's own plan area. The routing
        step is dx/20 (0.01 s on the 0.2 m grid): SWMM's variable step is
        set by the flow velocity, so in still or slow deep water it stays at
        the routing step, far above the gravity-wave limit on short
        conduits, and a lake at rest starts to slosh (1.3 m/s on a 0.4 %
        slope with a 1 s step; 0.00007 m/s with 0.05 s).

A1F-020 (stationary jump) is not run: SWMM cannot hold both the depth and
the discharge of a supercritical inflow at its upstream boundary.

Settings beyond the defaults: ``ROUTING_STEP 1`` s with the default
variable step (``VARIABLE_STEP 0.75``) and ``MINIMUM_STEP 0.001`` s — SWMM's
default 0.5 s minimum would exceed the Courant limit on the finer grids.
``MIN_SURFAREA`` stays at its default; the 10 m dam-break channel makes it
negligible next to each node's share of the conduit surface.

Score cards go to ``out/swmm_track_a/<engine>/``. Usage::

    python scripts/run_swmm_track_a.py --openswmm-python /path/to/python-with-openswmm
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "swmm_track_a"
TS = "2024-01-01T00:00:00Z"
W_DAMBREAK = 10.0
W_WIDE = 100_000.0
# SWASHES bump: on 5 cm conduits a node's own plan area (0.5 m² at 10 m wide) is below
# SWMM's default MIN_SURFAREA (1.17 m²), which would add storage at every node; the
# bump cases set MIN_SURFAREA to 0.001 m² instead.
W_SWASHES = W_DAMBREAK
MIN_SURFAREA_SWASHES = 0.001
# EPA SWMM rejects a Manning n of zero (ERROR 113); 0.0001 adds a friction slope
# below 1e-7 at the dam breaks' depths and speeds, and is used for every engine.
N_MIN = 0.0001

ENGINES = {
    "swmm524": dict(label="EPA SWMM 5.2.4", routing="DYNWAVE"),
    "openswmm-dw": dict(label="OpenSWMM Engine v6 dynamic wave", routing="DYNWAVE"),
    "openswmm-fv": dict(label="OpenSWMM Engine v6 finite volume", routing="FV"),
    "hydra-uds": dict(label="Hydra urban drainage", routing="DYNWAVE"),
}


def _hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def write_inp(path: Path, faces: np.ndarray, z: np.ndarray, depth0: np.ndarray, width: float, n: float,
              t_end: float, routing: str, dx: float, inflow: float | None = None, stage_out: float | None = None,
              extra: tuple[str, ...] = (), routing_step: float = 1.0) -> list[str]:
    """Chain of conduits between face nodes; returns the conduit names in order."""
    nn = len(faces)
    nodes = [f"N{i:05d}" for i in range(nn)]
    links = [f"C{i:05d}" for i in range(nn - 1)]
    opts = ["[OPTIONS]", "FLOW_UNITS CMS", "INFILTRATION HORTON", f"FLOW_ROUTING {routing}", "LINK_OFFSETS ELEVATION",
            "START_DATE 01/01/2000", "START_TIME 00:00:00", "REPORT_START_DATE 01/01/2000", "REPORT_START_TIME 00:00:00",
            "END_DATE 01/01/2000", f"END_TIME {_hms(t_end)}", "SWEEP_START 01/01", "SWEEP_END 12/31", "DRY_DAYS 0",
            f"REPORT_STEP {_hms(min(t_end, 60.0) if t_end % 60 == 0 else 5)}", "WET_STEP 00:05:00", "DRY_STEP 01:00:00",
            f"ROUTING_STEP {routing_step:g}", "VARIABLE_STEP 0.75", "MINIMUM_STEP 0.001", "ALLOW_PONDING NO", "INERTIAL_DAMPING PARTIAL",
            "NORMAL_FLOW_LIMITED BOTH", "FORCE_MAIN_EQUATION H-W", "MAX_TRIALS 8", "HEAD_TOLERANCE 0.0005",
            "SYS_FLOW_TOL 5", "LAT_FLOW_TOL 5", "THREADS 1", *extra]
    if routing == "FV":
        opts += ["FV_MIN_CELLS 1"]
    lines = opts + ["", "[JUNCTIONS]", ";;Name Elev MaxDepth InitDepth SurDepth Aponded"]
    out_node = len(nodes) - 1
    for i, name in enumerate(nodes[:-1]):
        lines.append(f"{name} {z[i]:.9f} 50 {depth0[i]:.9f} 0 0")
    lines += ["", "[OUTFALLS]", ";;Name Elev Type Stage Gated"]
    if stage_out is not None:
        lines.append(f"{nodes[out_node]} {z[out_node]:.9f} FIXED {stage_out:.9f} NO")
    else:
        lines.append(f"{nodes[out_node]} {z[out_node]:.9f} FREE NO")
    lines += ["", "[CONDUITS]", ";;Name From To Length Roughness InOffset OutOffset InitFlow MaxFlow"]
    for i, name in enumerate(links):
        length = faces[i + 1] - faces[i]
        lines.append(f"{name} {nodes[i]} {nodes[i + 1]} {length:.9f} {n:g} {z[i]:.9f} {z[i + 1]:.9f} 0 0")
    lines += ["", "[XSECTIONS]", ";;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels"]
    lines += [f"{name} RECT_OPEN 50 {width:g} 0 0 1" for name in links]
    if inflow is not None:
        lines += ["", "[INFLOWS]", ";;Node Constituent TimeSeries Type Mfactor Sfactor Baseline",
                  f'{nodes[0]} FLOW "" FLOW 1.0 1.0 {inflow:.9f}']
    lines += ["", "[REPORT]", "INPUT NO", "CONTROLS NO", "NODES ALL", "LINKS ALL", "", "[COORDINATES]"]
    lines += [f"{name} {faces[i]:.6f} 0" for i, name in enumerate(nodes)]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return links


_RUN524 = (
    "import os, sys\n"
    "from swmm.toolkit import solver\n"
    "os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))\n"
    "solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n"
    "print(solver.swmm_version_info())\n"
)


HYDRA_EXE: str | None = None  # --hydra-exe


def run_engine(engine: str, inp: Path, td: Path, openswmm_python: str | None) -> tuple[Path, str]:
    rpt, out = td / "m.rpt", td / "m.out"
    if engine == "swmm524":
        p = subprocess.run([sys.executable, "-c", _RUN524, str(inp), str(rpt), str(out)], capture_output=True, text=True)
        if p.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError((p.stdout + p.stderr)[-800:] + (rpt.read_text(errors="replace")[-1500:] if rpt.is_file() else ""))
        return out, p.stdout.strip().split()[-1]
    if engine == "hydra-uds":
        from benchmark1d2d.adapters import hydra

        try:
            hydra.run(HYDRA_EXE, inp, rpt, out, "uds")
        except RuntimeError as exc:
            raise RuntimeError(f"{exc}\n" + (rpt.read_text(errors="replace")[-1500:] if rpt.is_file() else "")) from exc
        return out, hydra.version(HYDRA_EXE)
    from benchmark1d2d.adapters import openswmm

    try:
        version = openswmm.run(openswmm_python, inp, rpt, out)
    except RuntimeError as exc:
        raise RuntimeError(f"{exc}\n" + (rpt.read_text(errors="replace")[-1500:] if rpt.is_file() else "")) from exc
    return out, version


def read_links(out: Path, links: list[str], t_end: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Depth and velocity of each conduit at the last reporting time (SWMM binary output)."""
    from swmm.toolkit import output, shared_enum

    h_ = output.init()
    output.open(h_, str(out))
    try:
        n_link = output.get_proj_size(h_)[2]
        n_per = output.get_times(h_, shared_enum.Time.NUM_PERIODS)
        step = output.get_times(h_, shared_enum.Time.REPORT_STEP)
        names = {output.get_elem_name(h_, shared_enum.ElementType.LINK, i): i for i in range(n_link)}
        depth = output.get_link_attribute(h_, n_per - 1, shared_enum.LinkAttribute.FLOW_DEPTH)
        vel = output.get_link_attribute(h_, n_per - 1, shared_enum.LinkAttribute.FLOW_VELOCITY)
    finally:
        output.close(h_)
    idx = [names[k] for k in links]
    return np.asarray(depth, float)[idx], np.asarray(vel, float)[idx], float(n_per * step)


# ── cases ───────────────────────────────────────────────────────────────────


def dam_break(m: dict, dx: float, routing: str, inp: Path) -> tuple[list[str], np.ndarray, list[int]]:
    p = m["reference"]["generator"]["parameters"]
    if m["test_id"].startswith("A1F-010"):
        xmin, xmax, x0, hl, hr = 0.0, 2000.0, float(p.get("x0", 1000.0)), float(p.get("h0", 1.0)), 0.0
    else:
        xmin, xmax, x0, hl, hr = -1000.0, 1000.0, float(p.get("x0", 0.0)), float(p.get("hl", 1.0)), float(p.get("hr", 0.1))
    eps = dx / 20
    up = np.arange(xmin, x0 + dx / 4, dx)          # faces up to the dam
    down = np.arange(x0, xmax + dx / 4, dx)         # faces from the dam
    faces = np.concatenate([up[:-1], [x0 - eps / 2, x0 + eps / 2], down[1:]])
    depth0 = np.where(faces < x0, hl, hr)
    # downstream end held at the undisturbed level (a free outfall would drain the 0.1 m layer)
    links = write_inp(inp, faces, np.zeros_like(faces), depth0, W_DAMBREAK, N_MIN, float(m["simulation"]["t_end"]), routing, dx,
                      stage_out=hr if hr > 0 else None)
    centres = 0.5 * (faces[1:] + faces[:-1])
    keep = [i for i in range(len(links)) if faces[i + 1] - faces[i] > dx / 2]  # every full cell, not the dam link
    return links, centres, keep


def macdonald(m: dict, dx: float, routing: str, inp: Path) -> tuple[list[str], np.ndarray, list[int]]:
    from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

    L, B, Q = (float(M1_PARAMS[k]) for k in ("L", "B", "Q"))
    n = float(M1_PARAMS["n_manning"])
    faces = np.linspace(0.0, L, int(round(L / dx)) + 1)
    fine = np.linspace(0.0, L, 200001)
    z = np.interp(faces, fine, bed_elevation(fine))
    h_out = float(depth_profile(np.array([L]))[0])
    depth0 = np.full_like(faces, h_out)
    links = write_inp(inp, faces, z, depth0, W_WIDE, n, float(m["simulation"]["t_end"]), routing, dx,
                      inflow=Q / B * W_WIDE, stage_out=float(z[-1] + h_out))
    return links, 0.5 * (faces[1:] + faces[:-1]), list(range(len(links)))


def swashes(m: dict, dx: float, routing: str, inp: Path) -> tuple[list[str], np.ndarray, list[int]]:
    """A1F-040–043 (SWASHES bump): bed shaped to the bump at the faces, inflow q upstream."""
    from references.swashes import bed

    prm = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())
    L = prm["domain"]["xmax"]
    faces = np.linspace(0.0, L, int(round(L / dx)) + 1)
    z = bed(faces)
    level = prm["initial"]["level_m"]
    depth0 = np.maximum(level - z, 0.0)
    up, down = prm["upstream"], prm["downstream"]
    inflow = up["discharge_m2s"] * W_SWASHES if "discharge_m2s" in up else None
    stage = down.get("depth_m", level if down.get("wall") else None)
    links = write_inp(inp, faces, z, depth0, W_SWASHES, N_MIN, float(m["simulation"]["t_end"]), routing, dx,
                      inflow=inflow, stage_out=None if stage is None else float(z[-1] + stage),
                      extra=(f"MIN_SURFAREA {MIN_SURFAREA_SWASHES}",), routing_step=dx / 20.0)
    return links, 0.5 * (faces[1:] + faces[:-1]), list(range(len(links)))


CASES = {"A1F-010": dam_break, "A1F-011": dam_break, "A1F-001": macdonald,
         "A1F-040": swashes, "A1F-041": swashes, "A1F-042": swashes, "A1F-043": swashes}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    ap.add_argument("--engines", nargs="+", choices=list(ENGINES), default=list(ENGINES))
    ap.add_argument("--openswmm-python", help="Python with the openswmm wheel")
    ap.add_argument("--hydra-exe", help="the hydra CLI (NEER AI Hydra)")
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    global HYDRA_EXE
    HYDRA_EXE = args.hydra_exe
    engines = [e for e in args.engines
               if e == "swmm524" or (e == "hydra-uds" and args.hydra_exe) or (e.startswith("openswmm") and args.openswmm_python)]
    failed = 0
    for engine in engines:
        out = OUT / engine
        out.mkdir(parents=True, exist_ok=True)
        for tid in args.cases:
            m = load_manifest(tid, repo=REPO)
            t_end = float(m["simulation"]["t_end"])
            paths, version = [], ""
            for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
                t0 = time.perf_counter()
                with tempfile.TemporaryDirectory() as tdn:
                    td = Path(tdn)
                    inp = td / "m.inp"
                    links, centres, keep = CASES[tid](m, float(dx), ENGINES[engine]["routing"], inp)
                    from benchmark1d2d import keep as kept

                    kept.inputs(engine, tid, td, dx, files=["m.inp"])
                    try:
                        o, version = run_engine(engine, inp, td, args.openswmm_python)
                        h, u, t_last = read_links(o, links, t_end)
                    except Exception as exc:  # noqa: BLE001 - an engine that cannot run a case is a finding
                        print(f"  {engine} {tid} dx={dx}: did not run: {str(exc)[-600:]}")
                        failed += 1
                        paths = []
                        break
                x = centres[keep]
                h, u = np.maximum(h[keep], 0.0), u[keep]
                nan = np.full(len(x), np.nan)
                cols = {"t": np.full(len(x), t_last), "x": x, "y": nan.copy(), "h": h, "u": u, "v": nan.copy(), "p": nan.copy(), "Q": h * u}
                paths.append(write_results_parquet(out / f"{m['test_id']}_dx{dx:g}.parquet", cols))
                print(f"  {engine} {tid} dx={dx}: {time.perf_counter() - t0:.1f}s, t={t_last:g}")
            if len(paths) < 2:
                continue
            ver = version.replace("openswmm", "").strip()
            solver = {"name": f"{ENGINES[engine]['label']}" + (f" ({ver})" if engine != "swmm524" else ""), "version": ver,
                      "adapter": f"swmm ({ENGINES[engine]['routing']} routing, conduit per grid cell)"}
            card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
            c = card.get("convergence_result") or {}
            print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
