#!/usr/bin/env python3
"""Build and run one coupled 1D/2D case (A12-01x) in OpenSWMM Engine v6.

Runs in the Python that has the ``openswmm`` wheel (it needs only numpy and
openswmm) and is called by ``scripts/run_openswmm_coupled.py``, which scores
what it writes. The model is written the way a SWMM user would write it:

* the network is the case's ``network`` (``run_drainage_cases.write_inp``,
  dynamic wave, the engine's defaults), each manhole's rim at the case's
  crest;
* the surface is the case's rectangle on a mesh of ``cell_size`` squares, each
  cut into four triangles by its diagonals (a "rectangular cross" mesh, as the
  suite's ANUGA surface uses), ground levels at the vertices, Manning n per
  triangle, the initial pond as each triangle's initial depth;
* each manhole is coupled at the mesh vertex at its position
  (``[2D_VERTEX_NODE_MAP]``) with the case's orifice coefficient and grate
  area; the engine's own exchange law does the rest;
* the street's open foot is a ``NORMAL_FLOW`` boundary at the street's slope
  (Manning normal flow, the same condition the case defines); other edges
  are walls.

Every ``output_interval_s`` it records the depth at each probe (mean of the
four triangles nearest it), the exchange (m³/s, positive onto the surface),
and the volume accounts (surface, network, inflow, outflow; m³).

Usage::

    python openswmm_coupled_model.py CASE_DIR OUT_JSON [WORK_DIR]
"""

from __future__ import annotations

import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MESH = __import__("os").environ.get("OPENSWMM_MESH", "cross")  # "cross" (four triangles per square) or "diagonal" (two)
sys.path.insert(0, str(HERE))


def bed(spec: dict, x, y):
    b = spec["surface"]["bed"]
    x, y = np.asarray(x, float), np.asarray(y, float)
    if b["type"] == "flat":
        return np.full_like(x, b["z"])
    if b["type"] == "plane":
        return b["z0"] - b["slope_x"] * x
    if b["type"] == "cone":
        ax, ay = b["apex"]
        return b["z_apex"] + b["slope"] * np.hypot(x - ax, y - ay)
    raise ValueError(b["type"])


def mesh(spec: dict, style: str = "cross"):
    """Vertices (x, y, z) and triangles of a rectangular-cross mesh; the boundary edges of each side."""
    s = spec["surface"]
    dx = s["cell_size"]
    nx, ny = int(round((s["x1"] - s["x0"]) / dx)), int(round((s["y1"] - s["y0"]) / dx))
    xs = s["x0"] + dx * np.arange(nx + 1)
    ys = s["y0"] + dx * np.arange(ny + 1)
    vx, vy = [], []
    corner = {}
    for j in range(ny + 1):
        for i in range(nx + 1):
            corner[i, j] = len(vx)
            vx.append(xs[i])
            vy.append(ys[j])
    tris, sides = [], {"left": [], "right": [], "bottom": [], "top": []}
    if style == "diagonal":
        for j in range(ny):
            for i in range(nx):
                a, b, cc, d = corner[i, j], corner[i + 1, j], corner[i + 1, j + 1], corner[i, j + 1]
                # two triangles; edge 0 is opposite the first vertex: (d, a, b) has edge 0 = a–b (bottom),
                # (b, cc, d) has edge 0 = cc–d (top); left a–d and right b–cc are edges 1/2 below
                tris.append((d, a, b))
                if j == 0:
                    sides["bottom"].append((len(tris) - 1, 0))
                if i == 0:
                    sides["left"].append((len(tris) - 1, 2))  # edge 2 opposite b: d–a
                tris.append((b, cc, d))
                if j == ny - 1:
                    sides["top"].append((len(tris) - 1, 0))
                if i == nx - 1:
                    sides["right"].append((len(tris) - 1, 2))  # edge 2 opposite d: b–cc
        vx, vy = np.array(vx), np.array(vy)
        return vx, vy, bed(spec, vx, vy), tris, sides
    for j in range(ny):
        for i in range(nx):
            c = len(vx)
            vx.append(xs[i] + dx / 2)
            vy.append(ys[j] + dx / 2)
            a, b, cc, d = corner[i, j], corner[i + 1, j], corner[i + 1, j + 1], corner[i, j + 1]
            # four triangles, counter-clockwise, each with the square's side as its edge 0 (opposite the centre)
            for k, (p, q) in enumerate(((a, b), (b, cc), (cc, d), (d, a))):
                tris.append((c, p, q))
                side = (("bottom", j == 0), ("right", i == nx - 1), ("top", j == ny - 1), ("left", i == 0))[k]
                if side[1]:
                    sides[side[0]].append((len(tris) - 1, 0))
    vx, vy = np.array(vx), np.array(vy)
    return vx, vy, bed(spec, vx, vy), tris, sides


def write_model(case_dir: Path, work: Path) -> tuple[Path, dict]:
    from run_drainage_cases import write_inp

    spec = json.loads((case_dir / "inputs" / "coupling.json").read_text(encoding="utf-8"))
    net = json.loads(json.dumps(spec["network"]))
    net["duration_s"] = spec["duration_s"]
    crest = {mh["id"]: mh["crest"] for mh in spec["manholes"]}
    for j in net.get("junctions", []):
        if j["id"] in crest:  # the rim is the crest of the grate
            assert abs(j["invert"] + j["max_depth"] - crest[j["id"]]) < 1e-9, (j, crest)
    inp = work / "model.inp"
    write_inp(net, inp, "DYNWAVE", coordinates=False)

    vx, vy, vz, tris, sides = mesh(spec, MESH)
    s = spec["surface"]
    n = s["manning_n"]
    z_tri = [(vz[a] + vz[b] + vz[c]) / 3 for a, b, c in tris]
    init = [max(s["initial_level"] - z, 0.0) if "initial_level" in s else 0.0 for z in z_tri]
    L = ["", "[2D_OPTIONS]", f"OUTPUT_FILE {work / 'model.h5'}", "REPORT_2D NO",
         "", "[2D_VERTICES]", ";;X Y Z"]
    L += [f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in zip(vx, vy, vz)]
    L += ["", "[2D_TRIANGLES]", ";;V1 V2 V3 MANNINGS_N INIT_DEPTH"]
    L += [f"{a} {b} {c} {n:g} {h:.6f}" for (a, b, c), h in zip(tris, init)]
    L += ["", "[2D_VERTEX_NODE_MAP]", ";;VERTEX NODE CD AREA"]
    for mh in spec["manholes"]:
        v = int(np.argmin(np.hypot(vx - mh["x"], vy - mh["y"])))
        assert math.hypot(vx[v] - mh["x"], vy[v] - mh["y"]) < 1e-6, f"manhole {mh['id']} is not on a mesh vertex"
        L.append(f"{v} {mh['id']} {mh['co']:g} {mh['area']:.6f}")
    bcs = []
    for side, kind in s["boundaries"].items():
        if kind == "wall":
            continue
        if kind == "normal_depth":
            bcs += [f"{t} {e} NORMAL_FLOW {s['bed']['slope_x']:g} * *" for t, e in sides[side]]
        else:
            raise ValueError(kind)
    if bcs:
        L += ["", "[2D_BOUNDARY_CONDITIONS]", ";;TRI EDGE TYPE PARAM1 PARAM2 GROUP", *bcs]
    with inp.open("a", encoding="ascii") as f:
        f.write("\n".join(L) + "\n")
    return inp, spec


def run(case_dir: Path, out_json: Path, work: Path) -> None:
    import openswmm
    from openswmm.engine import Solver

    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    probes = manifest["simulation"].get("probes") or []
    work.mkdir(parents=True, exist_ok=True)
    inp, spec = write_model(case_dir, work)
    t_end, t_out = float(spec["duration_s"]), float(spec["output_interval_s"])
    net = spec["network"]
    rec: dict = {"t": [], "probes": {p["id"]: {"h": [], "z": None} for p in probes},
                 "exchange": {mh["id"]: [] for mh in spec["manholes"]},
                 "surface": [], "network": [], "inflow": [], "outflow": [], "boundary_out": []}
    with Solver(str(inp), str(work / "model.rpt"), str(work / "model.out")) as s:
        sf = s.surface2d
        assert sf.is_active, "the 2D module is not active"
        cx = np.array([sf.get_triangle_centroid(i)[0] for i in range(sf.n_triangles)])
        cy = np.array([sf.get_triangle_centroid(i)[1] for i in range(sf.n_triangles)])
        cz = np.array([sf.get_triangle_centroid(i)[2] for i in range(sf.n_triangles)])
        pidx = {p["id"]: np.argsort(np.hypot(cx - p["x"], cy - p["y"]))[:4] for p in probes}
        for p in probes:
            rec["probes"][p["id"]]["z"] = float(cz[pidx[p["id"]]].mean())
        nodes = s.nodes
        ids = list(nodes.ids)
        src = [ids.index(i["node"]) for i in net.get("inflows", [])]
        outf = [ids.index(o["id"]) for o in net.get("outfalls", [])]
        tri_bc = [te for side, kind in spec["surface"]["boundaries"].items() if kind != "wall"
                  for te in mesh(spec, MESH)[4][side]]
        from openswmm.engine._enums import RoutingTotal

        FT3 = 0.3048 ** 3  # the 1D engine keeps its ledgers in ft³ whatever the project's units
        mb = s.mass_balance
        acc = {"inflow": 0.0}
        last = [0.0]
        prev = {"t": 0.0, "net_up": 0.0}

        def accumulate():
            t = s.elapsed.total_seconds()
            dt = t - last[0]
            if dt > 0 and src:
                acc["inflow"] += dt * float(np.sum(np.asarray(nodes.lateral_inflows)[src]))
            last[0] = t

        def record():
            t = s.elapsed.total_seconds()
            d = np.asarray(sf.get_depths())
            rec["t"].append(t)
            for p in probes:
                rec["probes"][p["id"]]["h"].append(float(d[pidx[p["id"]]].mean()))
            # the 2D side's ledger of net water moved up through each coupling point, m³
            net_up = float(np.sum(np.asarray(sf.get_coupling_volume_bulk())))
            q = (net_up - prev["net_up"]) / (t - prev["t"]) if t > prev["t"] else 0.0
            prev.update(t=t, net_up=net_up)
            for k in rec["exchange"]:
                rec["exchange"][k].append(q / len(rec["exchange"]))
            rec["surface"].append(float(sf.total_volume))
            rec["network"].append(float(np.sum(nodes.volumes) + np.sum(s.links.volumes)))
            bout = float(sum(sf.get_edge_bc_cum_flux(t_, e) for t_, e in tri_bc))
            rec["boundary_out"].append(bout)
            rec["inflow"].append(acc["inflow"])
            rec["outflow"].append(float(mb.routing_total(RoutingTotal.OUTFLOW)) * FT3 + bout)

        record()
        next_out = t_out
        while True:
            dt = s.step()
            if not dt and s.elapsed.total_seconds() <= last[0]:
                break
            accumulate()
            if s.elapsed.total_seconds() + 1e-6 >= next_out:
                record()
                next_out += t_out
            if s.elapsed.total_seconds() >= t_end - 1e-6:
                break
        val = lambda x: x() if callable(x) else x  # noqa: E731 - properties in some builds, methods in others
        rec["engine"] = {"routing_continuity_pct": 100.0 * float(val(mb.routing_continuity_error)),
                         "surface_continuity": float(val(sf.continuity_error)),
                         "surface_mass_balance": {k: float(v) for k, v in val(sf.get_mass_balance).items()}}
    rec["version"] = openswmm.__version__
    out_json.write_text(json.dumps(rec), encoding="utf-8")


if __name__ == "__main__":
    case_dir, out_json = Path(sys.argv[1]), Path(sys.argv[2])
    work = Path(sys.argv[3]) if len(sys.argv) > 3 else out_json.parent / (out_json.stem + "_work")
    run(case_dir, out_json, work)
