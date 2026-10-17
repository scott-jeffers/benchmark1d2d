#!/usr/bin/env python3
"""Score HEC-RAS 7's pipe networks (its own 1D/2D storm-drain coupling) on the exact coupling cases (A12-01x).

HEC-RAS 7 keeps a pipe network in the geometry HDF: nodes, conduits and the
inlets that join a node to the 2D surface. RAS Mapper normally draws them; here
they are written straight into the HDF, in the layout of HEC's own Davis
example, after the 2D area has been built headless as in the other HEC-RAS 2D
runs (``run_hecras_2d.py``: GeoTIFF terrain, a mesh from seed points), and
HEC-RAS's geometry preprocessor builds the network's computational cells
itself. Then:

* each case's manhole is a node with a **top inlet** at the rim: orifice area
  and coefficient and weir length (the manhole's perimeter) from the case, and
  a weir coefficient of c_w √(2g), HEC-RAS's form of the case's weir law;
  flow can go both ways (not "surcharge only");
* the pipe inflow is a **flow hydrograph on the upstream node** and a free
  outfall is a **stage hydrograph** a metre below the outfall's invert (HEC's
  own tutorial's free outfall); the A12-010 manhole's capped stub is a closed
  end, so its node simply has no downstream conduit;
* nodes and conduits as the case gives them (inverts, diameters, Manning's
  n, no entrance or exit losses), the manhole's plan area SWMM's 1.167 m²;
  conduits cut into cells of at most a twentieth of their length;
* the surface: the case's bed as a terrain, square cells of the case's size,
  its Manning's n, walls, or a normal-depth outflow line for the street
  (A12-010); HEC-RAS's default full shallow-water equations (SWE-ELM) and its
  default pipe solver (diffusion wave) with the Courant-controlled time step.

Results carry the surface at the case's probes (water level over the cell's
terrain), the exchange at the manhole (HEC-RAS's top-inlet flow), and the
volume accounts: the surface from the 2D cells, the network from its cells'
volume tables and node areas, the inflow from the hydrograph, the outflow from
the outfall conduit (and the street's outflow line).

Usage (Windows, HEC-RAS 7.0.1, ras-commander, pythonnet)::

    python scripts/run_hecras_pipes.py --accept-hec-terms [A12-010 ...]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

import run_hecras_2d as base  # noqa: E402
from run_hecras_2d import AREA, START, TS, X0, Y0, _crlf, _xy16, compute, log  # noqa: E402

OUT = REPO / "out" / "coupled" / "hecras-pipes"
CASES = ["A12-010", "A12-011", "A12-012"]
NET = "Pipes"
G = 9.81
SWMM_NODE_AREA = 12.566 * 0.3048**2
# The pipe-node boundary's place on HEC-RAS's "Boundary Location=" line: the
# ninth field, "<network> [<node>]" (as pump stations name a pipe node).
BC_NODE_FIELD = 8


def interval(seconds: float) -> str:
    table = {1: "1SEC", 2: "2SEC", 5: "5SEC", 10: "10SEC", 15: "15SEC", 20: "20SEC", 30: "30SEC", 60: "1MIN",
             120: "2MIN", 300: "5MIN", 600: "10MIN", 900: "15MIN", 1800: "30MIN", 3600: "1HOUR"}
    return table[int(round(seconds))]


def date_clock(seconds: float) -> tuple[str, str]:
    import datetime as dt

    t = dt.datetime(2000, 1, 1) + dt.timedelta(seconds=round(seconds))
    return t.strftime("%d%b%Y").upper(), t.strftime("%H%M")


def f8(v: float) -> str:
    for p in (4, 3, 2, 1, 0):
        s = f"{v:8.{p}f}"
        if len(s) <= 8:
            return s
    raise ValueError(v)


def bed_function(bed: dict):
    kind = bed["type"]
    if kind == "flat":
        return lambda x, y: np.full_like(np.asarray(x, float), bed["z"])
    if kind == "plane":
        return lambda x, y: bed["z0"] - bed["slope_x"] * np.asarray(x, float)
    if kind == "cone":
        ax, ay = bed["apex"]
        return lambda x, y: bed["z_apex"] + bed["slope"] * np.hypot(np.asarray(x, float) - ax, np.asarray(y, float) - ay)
    raise ValueError(kind)


# ── text files ──────────────────────────────────────────────────────────────


def write_geometry(path: Path, title: str, s: dict, bc_lines: dict) -> np.ndarray:
    dx = s["cell_size"]
    x0, x1, y0, y1 = s["x0"], s["x1"], s["y0"], s["y1"]
    P = np.array([[x0, y1], [x1, y1], [x1, y0], [x0, y0], [x0, y1]], float) + (X0, Y0)
    xs = np.arange(x0 + dx / 2, x1 - dx / 4, dx)
    ys = np.arange(y0 + dx / 2, y1 - dx / 4, dx)
    seeds = np.array([(x, y) for y in ys[::-1] for x in xs])
    S = seeds + (X0, Y0)
    seed_lines = ["".join(_xy16(*p) for p in S[i:i + 2]) for i in range(0, len(S), 2)]
    c = P[:-1].mean(0)
    lines = [f"Geom Title={title}", "Program Version=7.00",
             f"Viewing Rectangle= {P[:, 0].min() - 60} , {P[:, 0].max() + 120} , {P[:, 1].max() + 60} , {P[:, 1].min() - 60} ", "",
             f"Storage Area={AREA:<16},{c[0]},{c[1]}", f"Storage Area Surface Line= {len(P)} ", *[_xy16(*p) for p in P],
             "Storage Area Type= 0 ", "Storage Area Area=", "Storage Area Min Elev=", "Storage Area Is2D=-1",
             f"Storage Area Point Generation Data=,,{dx:g},{dx:g}", f"Storage Area 2D Points= {len(S)} ", *seed_lines,
             "Storage Area 2D PointsPerimeterTime=01Jan2000 00:00:00", f"Storage Area Mannings={s['manning_n']:g}",
             "2D Cell Volume Filter Tolerance=0.003", "2D Cell Minimum Area Fraction=0.01",
             "2D Face Profile Filter Tolerance=0.003", "2D Face Area Elevation Profile Filter Tolerance=0.003",
             "2D Face Area Elevation Conveyance Ratio=0.02", "2D Face Area Laminar Depth=0.2", ""]
    for name, pts in bc_lines.items():
        Q = np.asarray(pts, float) + (X0, Y0)
        mid = Q.mean(0)
        arc = ["".join(_xy16(*p) for p in Q[i:i + 2]) for i in range(0, len(Q), 2)]
        lines += [f"BC Line Name={name:<32}", f"BC Line Storage Area={AREA:<16}",
                  f"BC Line Start Position= {Q[0][0]} , {Q[0][1]} ", f"BC Line Middle Position= {mid[0]} , {mid[1]} ",
                  f"BC Line End Position= {Q[-1][0]} , {Q[-1][1]} ", f"BC Line Arc= {len(Q)} ", *arc,
                  f"BC Line Text Position= {mid[0]} , {mid[1]} "]
    lines += ["LCMann Time=Dec/30/1899 00:00:00", "LCMann Region Time=Dec/30/1899 00:00:00", "LCMann Table=0",
              "Chan Stop Cuts=-1", "", ""]
    _crlf(path, lines)
    return seeds


def bc_location(area: str = "", bc_line: str = "", node: str = "") -> str:
    f = ["", "", "", "", "", area, "", bc_line, ""]
    widths = [16, 16, 8, 8, 16, 16, 16, 32, 32]
    if node:
        f[BC_NODE_FIELD] = f"{NET} [{node}]"
    return "Boundary Location=" + ",".join(v.ljust(w) for v, w in zip(f, widths))


def write_unsteady(path: Path, title: str, ic_level: float | None, bcs: list[dict]) -> None:
    lines = [f"Flow Title={title}", "Program Version=7.00", "Use Restart= 0 "]
    if ic_level is not None:
        lines += [f"Initial Storage Elev={AREA:<16},{ic_level:g}"]
    for bc in bcs:
        lines.append(bc_location(area=bc.get("area", ""), bc_line=bc.get("line", ""), node=bc.get("node", "")))
        if bc["kind"] == "normal":
            lines += [f"Friction Slope={bc['slope']:g},0"]
        else:
            vals = [f8(v) for v in bc["values"]]
            lines += [f"Interval={bc['interval']}", f"{'Flow' if bc['kind'] == 'flow' else 'Stage'} Hydrograph= {len(vals)} ",
                      *["".join(vals[i:i + 10]) for i in range(0, len(vals), 10)], "Stage Hydrograph TW Check=0"]
            if bc["kind"] == "stage":
                lines += ["Use Initial Stage=-1"]
        lines += ["DSS Path=", "Use DSS=False", "Use Fixed Start Time=False", "Fixed Start Date/Time=,",
                  "Is Critical Boundary=False", "Critical Boundary Flow="]
    lines += ["Precipitation Mode=Disable", "Wind Mode=No Wind Forces", "Air Density Mode=",
              "Met BC=Precipitation|Mode=None", "Met BC=Evapotranspiration|Mode=None"]
    _crlf(path, lines)


def add_pipe_solver(plan: Path) -> None:
    """The plan's pipe-network solver block ("PS ..."), as in HEC's Davis example: a default block, then one
    named for the network. HEC-RAS's defaults: the diffusion-wave equation (0), a Courant target of 0.9."""
    block = ["PS Theta= 1 ", "PS WS Tol= 0.01 ", "PS Volume Tol= 0.01 ", "PS Max Iterations= 20 ", "PS Equation= 0 ",
             "PS Advance Time Step=0", "PS Target Courant=0.9", "PS Time Slices= 1 ", "PS Iterate With 2D=0",
             "PS Project Initial WSE from DS=-1", "PS Ramp Up Initial WSE from US=-1", "PS Cores=0"]
    lines = plan.read_text(encoding="ascii").splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.startswith("UNET D1D2 MaxIter"))
    lines[at:at] = [*block, f"PS Name={NET}", *block]
    _crlf(plan, lines)


# ── the pipe network, written into the geometry HDF ────────────────────────


def layout_network(spec: dict) -> tuple[dict, list[dict]]:
    """Plan positions of the nodes (case coordinates): the manholes where the case puts them, the rest
    along a straight run at their conduits' lengths (west of the first manhole upstream, east downstream)."""
    net = spec["network"]
    mh = {m["id"]: (m["x"], m["y"]) for m in spec["manholes"]}
    pos = dict(mh)
    conduits = [c for c in net["conduits"] if not (c["to"] in {o["id"] for o in net.get("outfalls", [])}
                                                    and any(o["id"] == c["to"] and o.get("gated") and o.get("type") == "FIXED" for o in net["outfalls"]))]
    changed = True
    while changed:
        changed = False
        for c in conduits:
            a, b = c["from"], c["to"]
            if a in pos and b not in pos:
                pos[b] = (pos[a][0] + c["length"], pos[a][1]); changed = True
            elif b in pos and a not in pos:
                pos[a] = (pos[b][0] - c["length"], pos[b][1]); changed = True
    return pos, conduits


EXAMPLES = "https://github.com/HydrologicEngineeringCenter/hec-downloads/releases/download/1.0.45/Example_Projects_7_0.zip"
PIPE_GROUPS = ("Pipe Nodes", "Pipe Conduits", "Pipe Networks")


def davis_template() -> Path | None:
    """HEC's Davis example geometry (HEC-RAS 7.0 examples), whose pipe layers RAS Mapper wrote: the template
    for the attributes and layout HEC-RAS expects. None when it can't be fetched."""
    import urllib.request
    import zipfile

    cache = REPO / ".cache" / "hecras"
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / "DavisStormSystem.g02.hdf"
    if dst.is_file():
        return dst
    zp = cache / "Example_Projects_7_0.zip"
    try:
        if not zp.is_file():
            urllib.request.urlretrieve(EXAMPLES, zp)
        with zipfile.ZipFile(zp) as z:
            name = next(i for i in z.namelist() if i.endswith("Pipes/Davis/DavisStormSystem.g02.hdf"))
            dst.write_bytes(z.read(name))
        return dst
    except Exception as exc:  # noqa: BLE001
        log(f"    Davis template: {type(exc).__name__}: {exc}"[:300])
        return None


def _attr_map(f, root: str) -> dict:
    """{relative path: {attr: value}} for every group and dataset under ``root``."""
    out = {"": dict(f[root].attrs)}

    def visit(name, obj):
        out[name] = dict(obj.attrs)

    f[root].visititems(visit)
    return out


def apply_template(ghdf: Path, tmpl: Path) -> list[str]:
    """Give the written pipe layers every attribute Davis's carry (and Davis's extra conduit datasets, empty)."""
    import h5py

    notes = []
    with h5py.File(tmpl, "r") as t, h5py.File(ghdf, "a") as f:
        for grp in PIPE_GROUPS:
            if f"Geometry/{grp}" not in t or f"Geometry/{grp}" not in f:
                continue
            tm, fm = _attr_map(t, f"Geometry/{grp}"), _attr_map(f, f"Geometry/{grp}")
            for rel, attrs in tm.items():
                if rel.split("/")[0] == "Davis":
                    continue  # the compiled network: HEC-RAS builds ours
                path = f"Geometry/{grp}" + (f"/{rel}" if rel else "")
                if rel not in fm:
                    obj = t[path]
                    if isinstance(obj, h5py.Dataset):
                        f.create_dataset(path, shape=(0,) + obj.shape[1:], dtype=obj.dtype, maxshape=(None,) + obj.shape[1:])
                        notes.append(f"+{path}")
                    else:
                        continue
                for k, v in attrs.items():
                    if k not in f[path].attrs:
                        f[path].attrs[k] = v
                        notes.append(f"{path}@{k}")
    return notes


def layer_report(ghdf: Path, tmpl: Path | None) -> None:
    """Diagnostics: every attribute on Davis's pipe layers and on ours, side by side."""
    import h5py

    if not tmpl:
        return
    with h5py.File(tmpl, "r") as t, h5py.File(ghdf, "r") as f:
        for grp in PIPE_GROUPS:
            tm = _attr_map(t, f"Geometry/{grp}") if f"Geometry/{grp}" in t else {}
            fm = _attr_map(f, f"Geometry/{grp}") if f"Geometry/{grp}" in f else {}
            for rel in sorted(set(tm) | set(fm)):
                if rel.split("/")[0] == "Davis":
                    continue
                a, b = tm.get(rel), fm.get(rel)
                if repr(a) != repr(b):
                    log(f"    attrs {grp}/{rel}: Davis={ {k: str(v)[:60] for k, v in (a or {}).items()} } ours={ {k: str(v)[:60] for k, v in (b or {}).items()} }"[:500])
        for k in ("", "Geometry"):
            a = {x: str(v)[:50] for x, v in (t[k] if k else t).attrs.items()}
            b = {x: str(v)[:50] for x, v in (f[k] if k else f).attrs.items()}
            log(f"    attrs /{k}: Davis={a} ours={b}"[:700])


def _file_type(dt: np.dtype, data: np.ndarray):
    """The HDF5 type RAS Mapper writes for ``dt``: strings null-terminated and as long as the longest value
    (HEC's own .NET writer; h5py's default is null-padded), compounds packed in order."""
    import h5py

    if dt.names:
        parts = []
        for n in dt.names:
            parts.append((n, _file_type(dt.fields[n][0], data[n] if data.size else data[n])))
        tid = h5py.h5t.create(h5py.h5t.COMPOUND, sum(t.get_size() for _, t in parts))
        off = 0
        for n, t in parts:
            tid.insert(n.encode(), off, t)
            off += t.get_size()
        return tid
    if dt.kind == "S":
        n = max([len(x) for x in data.ravel()] + [1]) if data.size else max(dt.itemsize, 1)
        tid = h5py.h5t.C_S1.copy()
        tid.set_size(n)
        tid.set_strpad(h5py.h5t.STR_NULLTERM)
        return tid
    return h5py.h5t.py_create(dt)


def _np_twin(tid) -> np.dtype:
    """The packed numpy dtype with the same bytes as the HDF5 type ``tid``."""
    import h5py

    if isinstance(tid, h5py.h5t.TypeCompoundID):
        return np.dtype({"names": [tid.get_member_name(i).decode() for i in range(tid.get_nmembers())],
                         "formats": [_np_twin(tid.get_member_type(i)) for i in range(tid.get_nmembers())],
                         "offsets": [tid.get_member_offset(i) for i in range(tid.get_nmembers())],
                         "itemsize": tid.get_size()})
    if isinstance(tid, h5py.h5t.TypeStringID):
        return np.dtype(f"S{tid.get_size()}")
    return tid.dtype


def h5_write(g, name: str, data: np.ndarray):
    """A dataset laid out as RAS Mapper lays out its feature tables: chunked, gzip level 1, unlimited, with
    null-terminated strings."""
    import h5py

    shape = data.shape
    dcpl = h5py.h5p.create(h5py.h5p.DATASET_CREATE)
    dcpl.set_chunk(tuple(max(1, min(n, 4096)) if n else (4096 if i == 0 else 2) for i, n in enumerate(shape)))
    dcpl.set_deflate(1)
    if data.dtype.kind == "f":
        dcpl.set_fill_value(np.array(np.nan, data.dtype))
    space = h5py.h5s.create_simple(shape, (h5py.h5s.UNLIMITED,) * len(shape))
    tid = _file_type(data.dtype, data)
    dsid = h5py.h5d.create(g.id, name.encode(), tid, space, dcpl=dcpl)
    if data.size:
        # the bytes as they lie in the file (no conversion: HDF5's to null-terminated would cut each
        # full-length string's last character to make room for a terminator)
        raw = np.empty(shape, dtype=_np_twin(tid))
        if data.dtype.names:
            for n in data.dtype.names:
                raw[n] = data[n]
        else:
            raw[...] = data
        dsid.write(h5py.h5s.ALL, h5py.h5s.ALL, raw, mtype=tid)
    return g[name]


def write_network(ghdf: Path, spec: dict) -> dict:
    """Nodes, conduits and the manholes' top inlets, in HEC-RAS 7's geometry-HDF layout (as HEC's Davis example)."""
    import h5py

    net = spec["network"]
    pos, conduits = layout_network(spec)
    crest = {m["id"]: m for m in spec["manholes"]}
    juncs = {j["id"]: j for j in net.get("junctions", [])}
    outs = {o["id"]: o for o in net.get("outfalls", []) if any(c["to"] == o["id"] for c in conduits)}
    ids = list(juncs) + list(outs)
    n_up = {i: sum(1 for c in conduits if c["to"] == i) for i in ids}
    n_dn = {i: sum(1 for c in conduits if c["from"] == i) for i in ids}

    # HEC's Davis example uses two node types: "Start" (no conduit in) and "Junction" (everything else,
    # its outlet a junction with no conduit out); the status reads "US Junction" at a start
    def ntype(i: str) -> str:
        return "Start" if n_up[i] == 0 else "Junction"

    def nstatus(i: str) -> str:
        return ("US Junction" if n_up[i] == 0 else "Junction") + (" -with top inlet " if i in crest else "")

    node_dt = np.dtype([("Name", "S16"), ("System Name", "S16"), ("Node Type", "S16"), ("Node Status", "S40"),
                        ("Condtui Connections (US:DS)", "S8"), ("Invert Elevation", "<f4"), ("Base Area", "<f4"),
                        ("Terrain Elevation", "<f4"), ("Terrain Elevation Override", "<f4"), ("Depth", "<f4"),
                        ("Top Inlet Type", "S16"), ("Top Inlet Elevation", "<f4"), ("Side Inlet Type", "S16"),
                        ("Side Inlet Elevation", "<f4"), ("Total Connection Count", "<i4")])
    # a node with a boundary (the inflow, the outfall) is HEC-RAS's "External" node, which has no storage
    bc_nodes = {f["node"] for f in net.get("inflows", [])} | set(outs)
    rows = []
    for i in ids:
        inv = float((juncs.get(i) or outs.get(i))["invert"])
        top = float(crest[i]["crest"]) if i in crest else inv + float((juncs.get(i) or {}).get("max_depth", 1.0))
        rows.append((i, NET, ntype(i), nstatus(i), f"{n_up[i]}:{n_dn[i]}", inv,
                     0.0 if i in bc_nodes else SWMM_NODE_AREA, top, np.nan, top - inv,
                     "Manhole" if i in crest else "", float(crest[i]["crest"]) if i in crest else np.nan, "", np.nan, n_up[i] + n_dn[i]))
    nodes = np.array(rows, dtype=node_dt)
    pts = np.array([[pos[i][0] + X0, pos[i][1] + Y0] for i in ids], float)

    cdt = np.dtype([("Name", "S16"), ("System Name", "S16"), ("US Node", "S16"), ("DS Node", "S16"), ("Modeling Approach", "S16"),
                    ("Conduit Length", "<f8"), ("Max Cell Length", "<f4"), ("Shape", "S16"), ("Rise", "<f4"), ("Span", "<f4"),
                    ("Manning's n", "<f4"), ("US Offset", "<f4"), ("DS Offset", "<f4"), ("US Elevation", "<f4"), ("DS Elevation", "<f4"),
                    ("Slope", "<f4"), ("US Entrance Loss Coefficient", "<f4"), ("DS Exit Loss Coefficient", "<f4"),
                    ("US Backflow Loss Coefficient", "<f4"), ("DS Backflow Loss Coefficient", "<f4"), ("DS Gate Type", "S8"),
                    ("Major Group", "S16"), ("Minor Group", "S8"), ("DS Flap Gate", "u1")])
    crow, info, parts, cpts = [], [], [], []
    for c in conduits:
        a, b = c["from"], c["to"]
        zi = float((juncs.get(a) or outs.get(a))["invert"]) + float(c.get("in_offset", 0.0))
        zo = float((juncs.get(b) or outs.get(b))["invert"]) + float(c.get("out_offset", 0.0))
        L = float(c["length"])
        crow.append((c["id"], NET, a, b, "Hydraulic", L, L / 20.0, "Circular", c["D"], c["D"], c["n"],
                     c.get("in_offset", 0.0), c.get("out_offset", 0.0), zi, zo, (zi - zo) / L, 0.0, 0.0, 0.0, 0.0, "None", "", "", 0))
        info.append([len(cpts), 2, len(parts), 1])
        parts.append([0, 2])
        cpts += [[pos[a][0] + X0, pos[a][1] + Y0], [pos[b][0] + X0, pos[b][1] + Y0]]

    tdt = np.dtype([("Name", "S16"), ("Orifice Area", "<f4"), ("Orifice Coef", "<f4"), ("Weir Length", "<f4"),
                    ("Weir Coef", "<f4"), ("Surcharge Only", "S5")])
    m0 = spec["manholes"][0]
    tops = np.array([("Manhole", m0["area"], m0["co"], m0["perimeter"], m0["cw"] * math.sqrt(2 * G), "False")], dtype=tdt)
    tpts = np.array([[pos[m["id"]][0] + X0, pos[m["id"]][1] + Y0] for m in spec["manholes"]], float)
    sdt = np.dtype([("Name", "S16"), ("Inlet Shape", "S8"), ("Rise", "<f4"), ("Span", "<f4"), ("Orifice Coef", "<f4"),
                    ("Weir Coef", "<f4"), ("Surcharge Only", "S5")])

    def ds(g, name, data, attrs=None):
        if name in g:
            del g[name]
        d = h5_write(g, name, np.asarray(data))
        for k, v in (attrs or {}).items():
            d.attrs[k] = v
        return d

    with h5py.File(ghdf, "a") as f:
        geo = f.require_group("Geometry")
        for name in ("Pipe Nodes", "Pipe Conduits", "Pipe Networks"):
            if name in geo:
                del geo[name]
        gn = geo.create_group("Pipe Nodes"); gn.attrs["Version"] = np.bytes_("1.0.1")
        ds(gn, "Attributes", nodes)
        ds(gn, "Points", pts, {"Column": np.array([b"X", b"Y"]), "Feature Type": np.bytes_("Point"), "Row": np.bytes_("Points")})
        gt = gn.create_group("Top Inlets")
        ds(gt, "Attributes", tops)
        ds(gt, "Points Info", np.array([[0, len(tpts)]], np.int32), {"Column": np.array([b"Point Starting Index", b"Point Count"]),
                                                                       "Feature Type": np.bytes_("MultiPoint"), "Row": np.bytes_("Feature")})
        ds(gt, "Points Points", tpts, {"Column": np.array([b"X", b"Y"]), "Row": np.bytes_("Points")})
        gs = gn.create_group("Side Inlets")
        ds(gs, "Attributes", np.array([("Side Inlet", "Box", 0.15, 0.9, 0.67, 1.66, "False")], dtype=sdt))
        ds(gs, "Points Info", np.array([[0, 0]], np.int32), {"Column": np.array([b"Point Starting Index", b"Point Count"]),
                                                              "Feature Type": np.bytes_("MultiPoint"), "Row": np.bytes_("Feature")})
        ds(gs, "Points Points", np.zeros((0, 2)), {"Column": np.array([b"X", b"Y"]), "Row": np.bytes_("Points")})
        gc = geo.create_group("Pipe Conduits"); gc.attrs["Version"] = np.bytes_("1.0.1")
        ds(gc, "Attributes", np.array(crow, dtype=cdt))
        ds(gc, "Polyline Info", np.array(info, np.int32), {"Column": np.array([b"Point Starting Index", b"Point Count", b"Part Starting Index", b"Part Count"]),
                                                           "Feature Type": np.bytes_("Polyline"), "Row": np.bytes_("Feature")})
        ds(gc, "Polyline Parts", np.array(parts, np.int32), {"Column": np.array([b"Point Starting Index", b"Point Count"]), "Row": np.bytes_("Part")})
        ds(gc, "Polyline Points", np.array(cpts, float), {"Column": np.array([b"X", b"Y"]), "Row": np.bytes_("Points")})
        gp = geo.create_group("Pipe Networks")
        ds(gp, "Attributes", np.array([(NET,)], dtype=[("Name", "S16")]))
    log(f"    pipe network: {len(ids)} nodes ({', '.join(f'{i} {ntype(i)}' for i in ids)}), {len(crow)} conduits, top inlet at {list(crest)}")
    return {"ids": ids, "pos": pos, "conduits": conduits, "outs": list(outs)}


def compiled(ghdf: Path) -> list[str]:
    import h5py

    with h5py.File(ghdf, "r") as g:
        return [k for k in g.get("Geometry/Pipe Networks", {}).keys() if k != "Attributes"]


def compile_network(folder: Path, ras_exe: Path, ghdf: Path) -> None:
    """Have HEC-RAS build the network's computational cells and property tables from the layers written above.

    Tries, in order, until the compiled network appears in the geometry HDF: RasMapperLib's own calls (the ones
    RAS Mapper makes), then HEC-RAS's geometry preprocessor through ras-commander.
    """
    from ras_commander.geom.GeomMesh import _imports, _load_dlls

    _load_dlls(str(ras_exe.parent))
    import System  # type: ignore
    from System.Collections.Generic import List  # type: ignore

    ns = _imports()

    def cnt(layer):
        try:
            return int(layer.FeatureCount())
        except Exception as exc:  # noqa: BLE001
            return f"? ({type(exc).__name__}: {str(exc)[:80]})"

    tmpl = davis_template()
    if tmpl:
        # does RasMapperLib read Davis's own layers this way? (tells a reading problem from a writing one)
        copy = folder / "_davis_probe.g02.hdf"
        shutil.copy2(tmpl, copy)
        try:
            dg = ns["RASGeometry"](str(copy))
            log("    Davis via RasMapperLib: " + "; ".join(f"{n}={cnt(getattr(dg, n))}" for n in ("PipeNodes", "PipeLinks", "PipeNetworks")))
        except Exception as exc:  # noqa: BLE001
            log(f"    Davis via RasMapperLib: {type(exc).__name__}: {exc}"[:300])
        layer_report(ghdf, tmpl)
        added = apply_template(ghdf, tmpl)
        log(f"    from the Davis template: {added}"[:600])
    geom =ns["RASGeometry"](str(ghdf))
    steps = []

    for lname in ("PipeNodes", "PipeLinks"):
        for m in ("IsOlderVersion", "Is1_0_0Version"):
            try:
                steps.append(f"{lname}.{m}={getattr(getattr(geom, lname), m)()}")
            except Exception as exc:  # noqa: BLE001
                steps.append(f"{lname}.{m}: {type(exc).__name__}")
    for lname in ("PipeNodes", "PipeLinks", "PipeTopInlets", "PipeSideInlets", "PipeNetworks"):
        try:
            steps.append(f"{lname}={cnt(getattr(geom, lname))}")
        except Exception as exc:  # noqa: BLE001
            steps.append(f"{lname}: {type(exc).__name__}: {str(exc)[:120]}")
    pn = geom.PipeNetworks
    idxs = List[System.Int32]()
    for i in range(max(1, int(pn.FeatureCount()) if isinstance(cnt(pn), int) else 1)):
        idxs.Add(i)
    for label, call in (
        ("load all layers", lambda: geom.LoadSaveAllLayers()),
        ("node types", lambda: geom.PipeNodes.UpdateNodeType(List[System.Int32]([i for i in range(int(geom.PipeNodes.FeatureCount()))]) if False else None)),
        ("reconcile network names", lambda: pn.ReconcileNetworksWithPipeLinkSystemNames()),
        ("out-of-date meshes", lambda: list(pn.GetOutOfDateMeshes())),
        ("compute meshes from inputs", lambda: pn.ComputeMeshesFromInputs(idxs, False)),
        ("complete for computations", lambda: pn.CompleteForComputations(None)),
        ("property tables", lambda: pn.EnsurePropertyTables(True, True, False, None)),
        ("save", lambda: geom.Save()),
    ):
        try:
            r = call()
            steps.append(f"{label}: {r!r}"[:200])
        except Exception as exc:  # noqa: BLE001 - diagnostics: which of HEC-RAS's steps works headless
            steps.append(f"{label}: {type(exc).__name__}: {exc}"[:300])
    steps.append(f"networks after={cnt(pn)}")
    log("    RasMapperLib pipe network: " + "; ".join(steps))
    if compiled(ghdf):
        return
    try:
        from ras_commander import init_ras_project
        from ras_commander.geom.GeomPreprocessor import GeomPreprocessor

        ras = init_ras_project(folder, str(ras_exe))
        r = GeomPreprocessor.run_geometry_preprocessor("01", ras_object=ras, max_wait=900, force=False)
        log(f"    geometry preprocessor (force=False): success={getattr(r, 'success', '?')} {getattr(r, 'error', '')}"[:600])
    except Exception as exc:  # noqa: BLE001
        log(f"    geometry preprocessor (force=False): {type(exc).__name__}: {exc}"[:600])


def event_dump(hdf: Path) -> None:
    """Diagnostics: the boundaries as HEC-RAS wrote them into the plan (groups, datasets and attributes)."""
    import h5py

    try:
        with h5py.File(hdf, "r") as f:
            if "Event Conditions" not in f:
                log("    event conditions: none")
                return

            def visit(name, obj):
                kind = "D" if isinstance(obj, h5py.Dataset) else "G"
                extra = f" {obj.shape} {obj.dtype}" if kind == "D" else ""
                log(f"    EC {kind} {name}{extra} {{{', '.join(f'{k}={str(v)[:60]}' for k, v in obj.attrs.items())}}}"[:400])
                if kind == "D" and obj.size and obj.size < 12:
                    log(f"       = {obj[()]!r}"[:300])

            f["Event Conditions"].visititems(visit)
            for grp in ("Geometry/Pipe Networks", "Geometry/Pipe Nodes", "Geometry/Pipe Conduits"):
                if grp in f:
                    log(f"    {grp}: {sorted(f[grp].keys())} {dict((k, str(v)[:40]) for k, v in f[grp].attrs.items())}"[:600])
                    for k in f[grp]:
                        o = f[f"{grp}/{k}"]
                        if isinstance(o, h5py.Group):
                            log(f"      {k}: {len(o)} items {dict((a, str(v)[:40]) for a, v in o.attrs.items())}"[:400])
            pp = "Plan Data/Plan Parameters"
            if pp in f:
                log("    plan parameters: " + "; ".join(f"{k}={str(v)[:30]}" for k, v in f[pp].attrs.items()
                                                      if not k.startswith(("1D", "2D")))[:2500])
            pp = "Plan Data/Plan Information"
            if pp in f:
                log("    plan info: " + ", ".join(f"{k}={str(v)[:40]}" for k, v in f[pp].attrs.items())[:800])
    except Exception as exc:  # noqa: BLE001
        log(f"    event conditions: {type(exc).__name__}: {exc}")


# ── results ─────────────────────────────────────────────────────────────────


def read_run(hdf: Path, ghdf: Path) -> dict:
    import h5py

    ts = "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series"
    out: dict = {}
    with h5py.File(ghdf, "r") as g:
        b = f"Geometry/2D Flow Areas/{AREA}"
        n_real = int(g["Geometry/2D Flow Areas/Cell Points"].shape[0])
        out["centres"] = g[f"{b}/Cells Center Coordinate"][()][:n_real] - (X0, Y0)
        out["n_real"] = n_real
        pn = f"Geometry/Pipe Networks/{NET}"
        if pn in g:
            out["pcell_min"] = g[f"{pn}/Cell Property Table"]["Min Elevation"][()]
            out["pcell_info_idx"] = g[f"{pn}/Cell Property Table"]["Info Index"][()]
            out["ptab_info"] = g[f"{pn}/Cell Property Table Info"][()]
            out["ptab_vals"] = g[f"{pn}/Cell Property Table Values"][()]
            out["node_names"] = [n.decode().strip() for n in g["Geometry/Pipe Nodes/Attributes"]["Name"]]
            out["node_base"] = g["Geometry/Pipe Nodes/Attributes"]["Base Area"][()]
            out["conduit_names"] = [n.decode().strip() for n in g["Geometry/Pipe Conduits/Attributes"]["Name"]]
            out["conduit_ds"] = [n.decode().strip() for n in g["Geometry/Pipe Conduits/Attributes"]["DS Node"]]
    with h5py.File(hdf, "r") as f:
        days = f[f"{ts}/Time"][()]
        out["t"] = (days - days[0]) * 86400.0
        a = f[f"{ts}/2D Flow Areas/{AREA}"]
        out["ws"] = a["Water Surface"][()][:, :out["n_real"]]
        out["bc"] = {k: a["Boundary Conditions"][k][()] for k in a.get("Boundary Conditions", {})}
        p = f.get(f"{ts}/Pipe Networks/{NET}")
        if p is not None:
            out["node_ws"] = p["Nodes/Water Surface"][()]
            out["node_inlet"] = p["Nodes/Top + Side Inlet Flow"][()]
            out["pipe_q_ds"] = p["Pipes/Pipe Flow DS"][()]
            out["pcell_ws"] = p["Cell Water Surface"][()]
        out["messages"] = f["Results/Summary/Compute Messages (text)"][0].decode(errors="replace")
        acc = []

        def visit(name, obj):
            if hasattr(obj, "attrs") and any("Vol Acc" in k for k in obj.attrs):
                acc.append(f"{name}: " + ", ".join(f"{k}={v}" for k, v in obj.attrs.items() if "Vol" in k))
        f.visititems(visit)
        out["accounting"] = acc
    return out


def network_volume(r: dict) -> np.ndarray:
    """Water in the pipe network at each output time: its cells' volume tables at their water levels (node cells included)."""
    vals, info, idx, zmin = r["ptab_vals"], r["ptab_info"], r["pcell_info_idx"], r["pcell_min"]
    vol = np.zeros(len(r["t"]))
    for c in range(r["pcell_ws"].shape[1]):
        s, n = info[idx[c]]
        v, d = vals[s:s + n, 0], vals[s:s + n, 1]
        depth = np.maximum(r["pcell_ws"][:, c] - zmin[c], 0.0)
        if len(v):
            vol += np.interp(depth, d, v)
    return vol


def cumulative(t: np.ndarray, q: np.ndarray) -> np.ndarray:
    out = np.zeros_like(t)
    out[1:] = np.cumsum(0.5 * (q[1:] + q[:-1]) * np.diff(t))
    return out


# ── a case ──────────────────────────────────────────────────────────────────


def run_case(m: dict, ras_exe: Path) -> tuple[dict, dict]:
    spec = json.loads((Path(m["_case_dir"]) / "inputs" / "coupling.json").read_text(encoding="utf-8"))
    s, net = spec["surface"], spec["network"]
    tid = m["test_id"].split("_")[0]
    t_end, t_out = float(spec["duration_s"]), float(spec["output_interval_s"])
    folder = OUT / "work" / tid
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    name = "Case"
    base.write_project(folder, name, tid, ["01"], ["01"])
    base.write_rasmap(folder, name)
    bc_lines = {}
    if s["boundaries"].get("right") == "normal_depth":
        e = 0.01 * s["cell_size"]
        bc_lines["Outflow"] = np.array([[s["x1"] + e, s["y0"]], [s["x1"] + e, s["y1"]]])
    seeds = write_geometry(folder / f"{name}.g01", tid, s, bc_lines)
    # terrain: the bed at a quarter of the cell size, two cells beyond the area
    z = bed_function(s["bed"])
    pix = s["cell_size"] / 4
    margin = 2 * s["cell_size"]
    px = np.arange(s["x0"] - margin + pix / 2, s["x1"] + margin, pix)
    py = np.arange(s["y0"] - margin + pix / 2, s["y1"] + margin, pix)
    PX, PY = np.meshgrid(px, py)
    zpix = z(PX, PY)
    terrain = base.create_terrain(folder, ras_exe.parent, zpix[::-1], s["x0"] - margin, s["y1"] + margin, pix)
    # boundaries
    bcs = []
    hours = max(1, math.ceil(t_end / 3600.0)) + 1
    for inf in net.get("inflows", []):
        if "series" in inf:
            tt, qq = np.array(inf["series"], float).T
            step = 60.0
            tq = np.arange(0.0, t_end + 2 * step, step)
            bcs.append(dict(node=inf["node"], kind="flow", interval=interval(step), values=list(np.interp(tq, tt, qq))))
        else:
            bcs.append(dict(node=inf["node"], kind="flow", interval="1HOUR", values=[float(inf["Q"])] * (hours + 1)))
    pos, conduits = layout_network(spec)
    for o in net.get("outfalls", []):
        if any(c["to"] == o["id"] for c in conduits):
            bcs.append(dict(node=o["id"], kind="stage", interval="1HOUR", values=[float(o["invert"]) - 1.0] * (hours + 1)))
    if "Outflow" in bc_lines:
        bcs.append(dict(area=AREA, line="Outflow", kind="normal", slope=s["bed"]["slope_x"]))
    write_unsteady(folder / f"{name}.u01", tid, s.get("initial_level"), bcs)
    d1, c1 = date_clock(t_end)
    base.write_plan(folder / f"{name}.p01", "Main", "main", "01", "0000", c1, "1SEC", interval(t_out), False, 1,
                    end_date=d1, map_dt=interval(t_out))
    add_pipe_solver(folder / f"{name}.p01")
    log(f"    project {tid}: {len(seeds)} cells, {len(bcs)} boundary conditions")
    base.preprocess_and_associate(folder, ras_exe, terrain)
    ghdf = folder / f"{name}.g01.hdf"
    netinfo = write_network(ghdf, spec)
    if os.environ.get("PIPES_RASMAPPER"):  # diagnostics only: HEC-RAS's compute builds the network itself
        compile_network(folder, ras_exe, ghdf)
    log(f"    compiled pipe network: {compiled(ghdf)}")
    from benchmark1d2d import keep

    keep.inputs("hecras-pipes", m["test_id"], folder, None)
    t0 = time.perf_counter()
    hdf = compute(folder, ras_exe, "01", 4 * 3600)
    log(f"    run: {time.perf_counter() - t0:.0f} s")
    log(base.messages(folder))
    b01 = folder / f"{name}.b01"
    if b01.is_file():
        txt = b01.read_text(errors="replace")
        i = txt.find("Stage and Flow Boundary")
        log("    b01 boundaries: " + txt[i:i + 600].replace("\n", " | ") if i >= 0 else "    b01: no boundary section")
    if hdf is None:
        log(base.listing(folder))
        log(base.messages(folder))
        raise RuntimeError("no results")
    event_dump(hdf)
    r = read_run(hdf, ghdf)
    log("    " + r["messages"][-1500:].replace("\n", "\n    "))
    log("    HEC-RAS volume accounting:\n      " + "\n      ".join(r["accounting"][:10]))
    if "node_ws" not in r:
        raise RuntimeError("the results have no pipe network")
    t = r["t"]
    # surface: water level over each cell's terrain pixels
    import run_hecras_2d_cases as cases

    dxc = s["cell_size"]
    gx = np.arange(s["x0"] + dxc / 2, s["x1"] - dxc / 4, dxc)
    gy = np.arange(s["y0"] + dxc / 2, s["y1"] - dxc / 4, dxc)
    pixels = cases.Pixels(zpix, s["x0"] - margin, s["y0"] - margin, pix, gx, gy)
    jj = np.clip(np.round((r["centres"][:, 1] - gy[0]) / dxc).astype(int), 0, gy.size - 1)
    ii = np.clip(np.round((r["centres"][:, 0] - gx[0]) / dxc).astype(int), 0, gx.size - 1)
    surf_vol = np.array([pixels.depth(jj, ii, r["ws"][k]).sum() * dxc * dxc for k in range(len(t))])
    names = r["node_names"]
    mh = spec["manholes"][0]["id"]
    k_mh = names.index(mh)
    inlet = r["node_inlet"][:, k_mh]
    # HEC-RAS reports inlet flow positive into the network; the cases' exchange is positive out of it
    exch = -inlet
    netv = network_volume(r)
    qin = np.zeros_like(t)
    for bc in bcs:
        if bc["kind"] == "flow":
            step = {"1MIN": 60.0, "1HOUR": 3600.0}[bc["interval"]]
            qin += np.interp(t, np.arange(len(bc["values"])) * step, bc["values"])
    q_out = np.zeros_like(t)
    for ci, ds_node in enumerate(r["conduit_ds"]):
        if ds_node in netinfo["outs"]:
            q_out += r["pipe_q_ds"][:, ci]
    street = np.zeros_like(t)
    for k, v in r["bc"].items():
        if k.startswith("Outflow") and v.ndim == 2 and v.shape[1] >= 2 and "per Face" not in k:
            street = np.abs(v[:, 1])
    rows: dict[str, list] = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "Q", "z", "V", "element_id", "element_type")}

    def emit(tt, x=np.nan, y=np.nan, h=np.nan, Q=np.nan, z=np.nan, V=np.nan, eid="", etype="cell"):
        for kk, val in (("t", tt), ("x", x), ("y", y), ("h", h), ("u", np.nan), ("v", np.nan), ("p", np.nan), ("Q", Q),
                        ("z", z), ("V", V), ("element_id", eid), ("element_type", etype)):
            rows[kk].append(val)

    probes = m["simulation"].get("probes") or []
    cum_in, cum_out = cumulative(t, qin), cumulative(t, q_out + street)
    for k in range(len(t)):
        for pr in probes:
            d = np.hypot(r["centres"][:, 0] - pr["x"], r["centres"][:, 1] - pr["y"])
            near = np.argsort(d)[:4]
            hh = pixels.depth(jj[near], ii[near], r["ws"][k][near]).mean()
            emit(t[k], pr["x"], pr["y"], float(hh), z=float(pixels.zmean(jj[near], ii[near]).mean()), eid=pr["id"])
        emit(t[k], Q=float(exch[k]), eid=mh, etype="exchange")
        emit(t[k], V=float(surf_vol[k]), eid="surface", etype="account")
        emit(t[k], V=float(netv[k]), eid="network", etype="account")
        emit(t[k], V=float(cum_in[k]), eid="inflow", etype="account")
        emit(t[k], V=float(cum_out[k]), eid="outflow", etype="account")
    cols = {k: (np.asarray(v, dtype=float) if k not in ("element_id", "element_type") else v) for k, v in rows.items()}
    log(f"    end: surface {surf_vol[-1]:.2f} m³, network {netv[-1]:.2f} m³, in {cum_in[-1]:.2f}, out {cum_out[-1]:.2f}; "
        f"exchange peak {exch.max():+.4f} / {exch.min():+.4f} m³/s")
    return cols, {"version": ras_exe.parent.name}


def main() -> int:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case
    from run_hecras import accept_terms, find_ras_exe

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=CASES)
    ap.add_argument("--accept-hec-terms", action="store_true")
    args = ap.parse_args()
    ras_exe = find_ras_exe()
    if args.accept_hec_terms:
        accept_terms(ras_exe)
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))
    ver = ras_exe.parent.name
    sol = {"name": f"HEC-RAS {ver} pipe networks 1D/2D", "version": ver,
           "adapter": "hecras pipe network written into the geometry HDF (nodes, conduits, top inlets), 2D SWE-ELM surface, defaults"}
    OUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        log(f"== {tid}")
        try:
            t0 = time.perf_counter()
            cols, _ = run_case(m, ras_exe)
            res = write_results_parquet(OUT / f"{m['test_id']}.parquet", cols, wall_seconds=time.perf_counter() - t0)
        except Exception:  # noqa: BLE001 - a case HEC-RAS cannot run is a finding
            traceback.print_exc()
            failed += 1
            continue
        card = score_case(m, res, timestamp=TS, private_key=key, solver=sol)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        log(f"{card.get('verdict', '').upper()} {m['test_id']}")
        for c in card["criteria_results"]:
            log(f"    {c['id']}: {c['observed']} {c['threshold']['units']} — {c.get('detail', '')}")
    return 1 if failed == len(args.cases) else 0


if __name__ == "__main__":
    raise SystemExit(main())
