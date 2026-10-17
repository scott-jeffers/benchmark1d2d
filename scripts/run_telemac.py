#!/usr/bin/env python3
"""Score openTELEMAC-2D on the dam breaks, the Thacker bowl and the 2D MacDonald channel.

TELEMAC-2D (openTELEMAC v9.1, conda-forge ``opentelemac``) is run as a black
box on each refinement level of A1F-010 (Ritter, dry bed) and A1F-011
(Stoker, wet bed):

- mesh: a 2D strip two triangles-pairs wide, so the 1D problem is solved by a
  genuine 2D unstructured solver; slip walls all round (no wave reaches the
  ends before t_end)
- numerics: TELEMAC's default finite-volume set-up (kinetic scheme, first
  order), variable time step at Courant 0.45; no tuning to the case.
  ``TIME STEP`` is the largest step TELEMAC may take (``caldt`` starts from
  it and lowers it to the Courant limit), so it is set to the whole run and
  the Courant condition alone sets the step; with a graphic printout period
  of 1 the results are written at t = 0 and at the end. HLLC and second-order
  variants were tried and leave the wet-front lag on A1F-010 unchanged.
- initial state: the dam-break step, written as a "previous computation" file

A2A-020 (oblique jump): the upstream supercritical state is set on the west
and north edges node by node in the boundary file (depth and both velocity
components), free outflow east, slip wall south. TELEMAC's default kinetic
scheme goes unstable with this inflow, so the HLLC scheme is used and named
on the score card.

The EA inter-comparison tests A2C-EA1, 2, 4 and 5 are run once each (see
``run_ea``). A2A-001 (Thacker) and A2A-010 (MacDonald 2D) use a triangle mesh whose nodes
are the case's cell centres (walls all round; for A2A-010 a prescribed
discharge west, a prescribed level east, Manning friction).

The centreline nodes (dam breaks) or all nodes (2D cases) at the final time
become the results file; scoring is
the same as for any other solver. Score cards go to ``out/telemac/``.

Usage::

    python scripts/run_telemac.py --telemac-prefix /path/to/conda/env
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
import time
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from benchmark1d2d.catalog import load_manifest  # noqa: E402
from benchmark1d2d.io.results import write_results_parquet  # noqa: E402
from benchmark1d2d.scoring.scorer import score_case  # noqa: E402

OUT = REPO / "out" / "telemac"
KEY = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
TS = "2024-01-01T00:00:00Z"

# ── Selafin (TELEMAC binary) I/O: big-endian Fortran records ────────────────


def _rec(fh, payload: bytes) -> None:
    fh.write(struct.pack(">i", len(payload)) + payload + struct.pack(">i", len(payload)))


def write_selafin(path: Path, x, y, ikle, ipobo, variables: dict[str, np.ndarray], title: str = "benchmark1d2d") -> None:
    names = list(variables)
    with open(path, "wb") as fh:
        _rec(fh, title.ljust(80)[:80].encode())
        _rec(fh, struct.pack(">ii", len(names), 0))
        for n in names:
            _rec(fh, n.ljust(32)[:32].encode())
        _rec(fh, struct.pack(">10i", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        _rec(fh, struct.pack(">4i", len(ikle), len(x), 3, 1))
        _rec(fh, struct.pack(f">{ikle.size}i", *(ikle.ravel() + 1)))
        _rec(fh, struct.pack(f">{len(ipobo)}i", *ipobo))
        _rec(fh, struct.pack(f">{len(x)}f", *x))
        _rec(fh, struct.pack(f">{len(y)}f", *y))
        _rec(fh, struct.pack(">f", 0.0))
        for n in names:
            _rec(fh, struct.pack(f">{len(x)}f", *variables[n]))


def iter_selafin(path: Path):
    """(time, {variable: values}) for every record of a Selafin file."""
    data = path.read_bytes()
    pos = 0

    def rec():
        nonlocal pos
        (n,) = struct.unpack(">i", data[pos:pos + 4])
        body = data[pos + 4:pos + 4 + n]
        pos += n + 8
        return body

    rec()
    nbv1, nbv2 = struct.unpack(">ii", rec())
    names = [rec().decode().strip() for _ in range(nbv1 + nbv2)]
    iparam = struct.unpack(">10i", rec())
    if iparam[9] == 1:
        rec()
    nelem, npoin, ndp, _ = struct.unpack(">4i", rec())
    for _ in range(4):  # ikle, ipobo, x, y
        rec()
    while pos < len(data):
        t_body = rec()
        t = struct.unpack(">f", t_body)[0] if len(t_body) == 4 else struct.unpack(">d", t_body)[0]
        vals = {}
        for nm in names:
            body = rec()
            vals[nm] = np.frombuffer(body, dtype=">f4" if len(body) == 4 * npoin else ">f8").astype(float)
        yield t, vals


def read_selafin_last(path: Path) -> tuple[float, dict[str, np.ndarray]]:
    last = None
    for last in iter_selafin(path):
        pass
    if last is None:
        raise RuntimeError(f"{path} holds no time steps")
    return last


# ── case set-up ─────────────────────────────────────────────────────────────


def strip_mesh(xmin: float, xmax: float, dx: float, ny: int = 2):
    nx = int(round((xmax - xmin) / dx))
    xs = np.linspace(xmin, xmax, nx + 1)
    ys = np.linspace(0.0, ny * dx, ny + 1)
    X, Y = np.meshgrid(xs, ys)
    x, y = X.ravel(), Y.ravel()
    node = lambda i, j: j * (nx + 1) + i  # noqa: E731
    tri = []
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1)
            tri += [(a, b, c), (a, c, d)]  # counter-clockwise
    loop = [node(i, 0) for i in range(nx + 1)] + [node(nx, j) for j in range(1, ny + 1)]
    loop += [node(i, ny) for i in range(nx - 1, -1, -1)] + [node(0, j) for j in range(ny - 1, 0, -1)]
    ipobo = np.zeros(len(x), dtype=int)
    for k, n in enumerate(loop, 1):
        ipobo[n] = k
    return x, y, np.array(tri), ipobo, loop, node(0, ny // 2), nx


CASES = {
    # short id: (xmin, xmax, x0, h_left, h_right)
    "A1F-010": lambda p: (0.0, 2000.0, float(p.get("x0", 1000.0)), float(p.get("h0", 1.0)), 0.0),
    "A1F-011": lambda p: (-1000.0, 1000.0, float(p.get("x0", 0.0)), float(p.get("hl", 1.0)), float(p.get("hr", 0.1))),
}

STEERING = """TITLE = '{title}'
GEOMETRY FILE = 'geo.slf'
BOUNDARY CONDITIONS FILE = 'geo.cli'
PREVIOUS COMPUTATION FILE = 'ini.slf'
INITIAL TIME SET TO ZERO = YES
RESULTS FILE = 'res.slf'
EQUATIONS = 'SAINT-VENANT FV'
FINITE VOLUME SCHEME = 1
VARIABLE TIME-STEP = YES
DESIRED COURANT NUMBER = 0.45
TIME STEP = {t_end}
DURATION = {t_end}
GRAPHIC PRINTOUT PERIOD = 1
LISTING PRINTOUT PERIOD = 100000000
VARIABLES FOR GRAPHIC PRINTOUTS = 'U,V,H,B'
TIDAL FLATS = YES
LAW OF BOTTOM FRICTION = 0
"""


def run_level(tid: str, m: dict, dx: float, env: dict, py: str) -> dict:
    prm = m["reference"]["generator"]["parameters"]
    xmin, xmax, x0, hl, hr = CASES[tid](prm)
    t_end = float(m["simulation"]["t_end"])
    x, y, ikle, ipobo, loop, mid0, nx = strip_mesh(xmin, xmax, dx)
    # Node values: the dam node holds the mean so the stored volume is exact.
    h = np.where(x < x0, hl, hr).astype(float)
    h[np.isclose(x, x0)] = 0.5 * (hl + hr)
    zero = np.zeros_like(x)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        write_selafin(d / "geo.slf", x, y, ikle, ipobo, {"BOTTOM          M               ": zero})
        write_selafin(d / "ini.slf", x, y, ikle, ipobo, {
            "VELOCITY U      M/S             ": zero, "VELOCITY V      M/S             ": zero,
            "WATER DEPTH     M               ": h, "BOTTOM          M               ": zero})
        (d / "geo.cli").write_text("".join(f"2 2 2 0.0 0.0 0.0 0.0 2 0.0 0.0 0.0 {n + 1} {k}\n" for k, n in enumerate(loop, 1)))
        (d / "t2d.cas").write_text(STEERING.format(title=tid, t_end=t_end))
        from benchmark1d2d import keep

        keep.inputs("telemac", tid, d, dx)
        proc = subprocess.run([py, str(Path(env["HOMETEL"]) / "scripts/python3/telemac2d.py"), "t2d.cas"],
                              cwd=d, env=env, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0 or not (d / "res.slf").is_file():
            raise RuntimeError(f"TELEMAC failed on {tid} dx={dx}:\n{proc.stdout[-3000:]}\n{proc.stderr[-2000:]}")
        t, vals = read_selafin_last(d / "res.slf")
    centre = np.arange(nx + 1) + mid0  # middle row of nodes
    hv = next(v for k, v in vals.items() if k.startswith("WATER DEPTH"))
    uv = next(v for k, v in vals.items() if k.startswith("VELOCITY U"))
    n = nx + 1
    nan = np.full(n, np.nan)
    return {"t": np.full(n, t), "x": x[centre], "y": nan.copy(), "h": hv[centre], "u": uv[centre],
            "v": nan.copy(), "p": nan.copy(), "Q": hv[centre] * uv[centre]}


# ── 2D cases: a structured triangle mesh whose nodes are the case's cell centres ─


def rect_mesh(xs: np.ndarray, ys: np.ndarray):
    nx, ny = len(xs) - 1, len(ys) - 1
    X, Y = np.meshgrid(xs, ys)
    x, y = X.ravel(), Y.ravel()
    node = lambda i, j: j * (nx + 1) + i  # noqa: E731
    tri = []
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1)
            tri += [(a, b, c), (a, c, d)] if (i + j) % 2 == 0 else [(a, b, d), (b, c, d)]  # alternate diagonals
    loop = [node(i, 0) for i in range(nx + 1)] + [node(nx, j) for j in range(1, ny + 1)]
    loop += [node(i, ny) for i in range(nx - 1, -1, -1)] + [node(0, j) for j in range(ny - 1, 0, -1)]
    ipobo = np.zeros(len(x), dtype=int)
    for k, n in enumerate(loop, 1):
        ipobo[n] = k
    return x, y, np.array(tri), ipobo, loop


STEERING_2D = """TITLE = '{title}'
GEOMETRY FILE = 'geo.slf'
BOUNDARY CONDITIONS FILE = 'geo.cli'
PREVIOUS COMPUTATION FILE = 'ini.slf'
INITIAL TIME SET TO ZERO = YES
RESULTS FILE = 'res.slf'
EQUATIONS = 'SAINT-VENANT FV'
FINITE VOLUME SCHEME = 1
VARIABLE TIME-STEP = YES
DESIRED COURANT NUMBER = 0.45
TIME STEP = {t_end}
DURATION = {t_end}
GRAPHIC PRINTOUT PERIOD = 1
LISTING PRINTOUT PERIOD = 100000000
VARIABLES FOR GRAPHIC PRINTOUTS = 'U,V,H,B'
TIDAL FLATS = YES
{extra}
"""


def open_boundary_order(loop, codes: dict, ipobo: np.ndarray) -> tuple[list, list]:
    """Start the boundary loop on a wall node and list the open boundaries' codes in loop order.

    TELEMAC numbers the open boundaries in the order it meets them along the
    boundary loop, so an open segment must not wrap round the loop's start,
    and prescribed values (keywords or a liquid boundaries file) are listed in
    that order. ``ipobo`` is renumbered in place.
    """
    k0 = next(k for k, nn in enumerate(loop) if nn not in codes)
    loop = list(loop[k0:]) + list(loop[:k0])
    for k, nn in enumerate(loop, 1):
        ipobo[nn] = k
    order = [codes[nn] for k, nn in enumerate(loop) if nn in codes and (k == 0 or loop[k - 1] not in codes)]
    return loop, order


def run_level_2d(tid: str, m: dict, dx: float, env: dict, py: str) -> dict:
    prm = m["reference"]["generator"]["parameters"]
    t_end = float(m["simulation"]["t_end"])
    codes = None  # per boundary node: (LIHBOR, LIUBOR, LIVBOR) else wall 2 2 2
    bvals = None  # per boundary node: (HBOR, UBOR, VBOR) values written to the boundary file
    scheme = 1  # TELEMAC's default finite-volume scheme (kinetic)
    extra = "LAW OF BOTTOM FRICTION = 0"
    if tid == "A2A-001":
        from references.thacker import bed_elevation, depth_velocity

        dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
        xs = np.arange(dom["xmin"] + dx / 2, dom["xmax"] - dx / 4, dx)
        ys = np.arange(dom["ymin"] + dx / 2, dom["ymax"] - dx / 4, dx)
        x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
        z = bed_elevation(x, y, prm["h0"], prm["L"])
        r0 = depth_velocity(x, y, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", 9.81))
        h, u, v = np.maximum(r0["h"], 0.0), np.where(r0["h"] > 0, r0["u"], 0.0), np.where(r0["h"] > 0, r0["v"], 0.0)
    elif tid == "A2A-010":
        from references.macdonald_2d import bed_elevation, depth_profile

        L, W, q, n = prm["L"], prm["W"], prm["q"], prm["n_manning"]
        xs = np.arange(dx / 2, L - dx / 4, dx)
        ys = np.arange(dx / 2, W - dx / 4, dx)
        x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
        z = bed_elevation(x, L=L, q=q, n_manning=n)
        h_out = float(depth_profile(xs[-1]))
        z_out = float(bed_elevation(xs[-1], L=L, q=q, n_manning=n))
        h = np.full_like(x, h_out)  # uniform depth: the steady profile must emerge
        u = v = np.zeros_like(x)
        wid = ys[-1] - ys[0]
        codes = {}
        for nn in loop:
            if np.isclose(x[nn], xs[0]):
                codes[nn] = (4, 5, 5)   # inflow: prescribed discharge
            elif np.isclose(x[nn], xs[-1]):
                codes[nn] = (5, 4, 4)   # outflow: prescribed elevation
        loop, order = open_boundary_order(loop, codes, ipobo)
        flows = ";".join(f"{q * wid:.9f}" if c == (4, 5, 5) else "0." for c in order)
        levels = ";".join(f"{z_out + h_out:.9f}" if c == (5, 4, 4) else "0." for c in order)
        extra = (f"LAW OF BOTTOM FRICTION = 4\nFRICTION COEFFICIENT = {n}\n"
                 f"PRESCRIBED FLOWRATES = {flows}\nPRESCRIBED ELEVATIONS = {levels}")
    elif tid == "A2A-020":
        from references.oblique_jump import states

        dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
        st = states(prm["Fr1"], prm["theta_deg"], prm["h1"], prm.get("g", 9.81))
        h1, u1, v1 = st["h1"], st["u1"], st["v1"]
        xs = np.arange(dom["xmin"] + dx / 2, dom["xmax"] - dx / 4, dx)
        ys = np.arange(dom["ymin"] + dx / 2, dom["ymax"] - dx / 4, dx)
        x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
        z = np.zeros_like(x)
        h, u, v = np.full_like(x, h1), np.full_like(x, u1), np.full_like(x, v1)
        codes, bvals = {}, {}
        for nn in loop:
            if np.isclose(x[nn], xs[0]) or np.isclose(y[nn], ys[-1]):
                codes[nn] = (5, 6, 6)  # supercritical inflow: depth and both velocity components set
                bvals[nn] = (h1, u1, v1)
            elif np.isclose(x[nn], xs[-1]):
                codes[nn] = (4, 4, 4)  # free (supercritical) outflow
        loop, _order = open_boundary_order(loop, codes, ipobo)
        # The default kinetic scheme goes unstable with this prescribed
        # supercritical inflow (velocities of thousands of m/s within 50 s);
        # HLLC (scheme 5) runs, so it is used here and named on the card.
        scheme = 5
    elif tid in SWASHES:
        from references.swashes import bed

        sp = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())
        L = sp["domain"]["xmax"]
        xs = np.arange(dx / 2, L - dx / 4, dx)
        ys = np.arange(dx / 2, 3 * dx, dx)  # a strip three nodes wide
        x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
        z = bed(x)
        h = np.maximum(sp["initial"]["level_m"] - z, 0.0)
        u = v = np.zeros_like(x)
        up, down = sp["upstream"], sp["downstream"]
        codes = {}
        for nn in loop:
            if np.isclose(x[nn], xs[0]) and "discharge_m2s" in up:
                codes[nn] = (4, 5, 5)
            elif np.isclose(x[nn], xs[-1]) and "depth_m" in down:
                codes[nn] = (5, 4, 4)
            elif np.isclose(x[nn], xs[-1]) and down.get("free_outflow"):
                codes[nn] = (4, 4, 4)
        if codes:
            loop, order = open_boundary_order(loop, codes, ipobo)
            wid = ys[-1] - ys[0]
            flows = ";".join(f"{up['discharge_m2s'] * wid:.9f}" if c == (4, 5, 5) else "0." for c in order)
            levels = ";".join(f"{down['depth_m']:.9f}" if c == (5, 4, 4) else "0." for c in order)
            extra += f"\nPRESCRIBED FLOWRATES = {flows}\nPRESCRIBED ELEVATIONS = {levels}"
    elif tid == "A1F-001":  # MacDonald backwater on a strip three nodes wide, Manning on the bed
        from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

        L, B, Q, n = (float(M1_PARAMS[k]) for k in ("L", "B", "Q", "n_manning"))
        fine = np.linspace(0.0, L, 200001)
        zfine = bed_elevation(fine)
        xs = np.arange(dx / 2, L - dx / 4, dx)
        ys = np.arange(dx / 2, 3 * dx, dx)
        x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
        z = np.interp(x, fine, zfine)
        h_out = float(depth_profile(np.array([xs[-1]]))[0])
        z_out = float(np.interp(xs[-1], fine, zfine))
        h = np.full_like(x, h_out)
        u = v = np.zeros_like(x)
        codes = {}
        for nn in loop:
            if np.isclose(x[nn], xs[0]):
                codes[nn] = (4, 5, 5)
            elif np.isclose(x[nn], xs[-1]):
                codes[nn] = (5, 4, 4)
        loop, order = open_boundary_order(loop, codes, ipobo)
        wid = ys[-1] - ys[0]
        flows = ";".join(f"{Q / B * wid:.9f}" if c == (4, 5, 5) else "0." for c in order)
        levels = ";".join(f"{z_out + h_out:.9f}" if c == (5, 4, 4) else "0." for c in order)
        extra = (f"LAW OF BOTTOM FRICTION = 4\nFRICTION COEFFICIENT = {n}\n"
                 f"PRESCRIBED FLOWRATES = {flows}\nPRESCRIBED ELEVATIONS = {levels}")
    elif tid == "A1F-020":  # standing jump on a strip: supercritical inflow (depth and velocity set), sequent depth held
        from references.belanger import sequent_depths

        sp = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())
        L = sp["domain"]["xmax"]
        upb = sp["boundaries"]["upstream"]
        ref = sequent_depths(np.array([0.0]), Fr1=upb["Fr"], h1=upb["h_m"], L=L)
        h1, h2, q = ref["h1"], ref["h2"], ref["q"]
        xs = np.arange(dx / 2, L - dx / 4, dx)
        ys = np.arange(dx / 2, 3 * dx, dx)
        x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
        z = np.zeros_like(x)
        h = np.where(x < L / 2, h1, h2)
        u, v = q / h, np.zeros_like(x)
        codes, bvals = {}, {}
        for nn in loop:
            if np.isclose(x[nn], xs[0]):
                codes[nn] = (5, 6, 6)
                bvals[nn] = (h1, q / h1, 0.0)
            elif np.isclose(x[nn], xs[-1]):
                codes[nn] = (5, 4, 4)
        loop, order = open_boundary_order(loop, codes, ipobo)
        levels = ";".join(f"{h1:.9f}" if c == (5, 6, 6) else f"{h2:.9f}" for c in order)
        extra += f"\nPRESCRIBED ELEVATIONS = {levels}"
        scheme = 5  # HLLC: the default kinetic scheme is unstable with a prescribed supercritical inflow (as on A2A-020)
    else:
        raise KeyError(tid)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        write_selafin(d / "geo.slf", x, y, ikle, ipobo, {"BOTTOM          M               ": z})
        write_selafin(d / "ini.slf", x, y, ikle, ipobo, {
            "VELOCITY U      M/S             ": u, "VELOCITY V      M/S             ": v,
            "WATER DEPTH     M               ": h, "BOTTOM          M               ": z})
        rows = []
        for k, nn in enumerate(loop, 1):
            a, b, c = (codes or {}).get(nn, (2, 2, 2))
            hb, ub, vb = (bvals or {}).get(nn, (0.0, 0.0, 0.0))
            rows.append(f"{a} {b} {c} {hb:.9f} {ub:.9f} {vb:.9f} 0.0 {2 if a == 2 else 4} 0.0 0.0 0.0 {nn + 1} {k}\n")
        (d / "geo.cli").write_text("".join(rows))
        (d / "t2d.cas").write_text(STEERING_2D.format(title=tid, t_end=t_end, extra=extra)
                                   .replace("FINITE VOLUME SCHEME = 1", f"FINITE VOLUME SCHEME = {scheme}"))
        from benchmark1d2d import keep

        keep.inputs("telemac", tid, d, dx)
        proc = subprocess.run([py, str(Path(env["HOMETEL"]) / "scripts/python3/telemac2d.py"), "t2d.cas"],
                              cwd=d, env=env, capture_output=True, text=True, timeout=7200)
        if proc.returncode != 0 or not (d / "res.slf").is_file():
            raise RuntimeError(f"TELEMAC failed on {tid} dx={dx}:\n{proc.stdout[-3000:]}\n{proc.stderr[-2000:]}")
        t, vals = read_selafin_last(d / "res.slf")
    hv = next(v for k, v in vals.items() if k.startswith("WATER DEPTH"))
    uv = next(v for k, v in vals.items() if k.startswith("VELOCITY U"))
    vv = next(v for k, v in vals.items() if k.startswith("VELOCITY V"))
    if tid in STRIPS:  # a 1D case: the strip's middle row of nodes
        mid = np.isclose(y, ys[1])
        n1 = int(mid.sum())
        nan = np.full(n1, np.nan)
        return {"t": np.full(n1, t), "x": x[mid], "y": nan.copy(), "h": np.maximum(hv[mid], 0.0), "u": uv[mid], "v": nan.copy(),
                "p": nan.copy(), "Q": np.maximum(hv[mid], 0.0) * uv[mid]}
    nnod = len(x)
    return {"t": np.full(nnod, t), "x": x, "y": y, "h": np.maximum(hv, 0.0), "u": uv, "v": vv,
            "p": np.full(nnod, np.nan), "z": z}


SWASHES = {"A1F-040", "A1F-041", "A1F-042", "A1F-043"}
STRIPS = SWASHES | {"A1F-001", "A1F-020"}
CASES_2D = {"A2A-001", "A2A-010", "A2A-020"} | STRIPS


# ── EA inter-comparison tests ───────────────────────────────────────────────

EA_CASES = ("A2C-EA1", "A2C-EA2", "A2C-EA4", "A2C-EA5")
EA_DX = {"A2C-EA4": 10.0}  # the specification's allowed alternative resolution (as the demo and ANUGA)


def run_ea(tid: str, m: dict, env: dict, py: str) -> tuple[dict, float | None]:
    """A2C-EA1/2/4/5: mesh nodes at the demo grid's cell centres.

    The grid (DEM block means, active area, inflow cells, probes) is the demo
    solver's. TELEMAC is vertex-centred, so a node on the mesh boundary owns
    only part of a cell; the mesh is therefore ringed by one row of wall nodes
    (50 m above the highest ground), and cells outside the active area are
    walls too, so every active cell keeps its full area. EA1's west edge is an
    open boundary following the boundary level table (liquid boundaries file);
    there the ring is left out. Inflows are TELEMAC point sources on the
    inflow cells, the hydrograph shared equally (sources file). Results are
    written every probe interval; the scorer gets the whole field hourly and
    the probe cells in between. The largest step (``TIME STEP``) is 1 s: on a
    dry start the Courant condition sets no limit, and a long first step
    samples the inflow hydrograph too coarsely (LISFLOOD-FP has the same cap).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_demo_2d", REPO / "scripts" / "run_demo_2d.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    dx_alt = next((v for k, v in EA_DX.items() if tid.startswith(k)), None)
    case, _h, probe_dt = demo.build_ea(m, dx_alt)
    gx, gy = np.asarray(case.grid.x, float), np.asarray(case.grid.y, float)
    dx = float(gx[1] - gx[0])
    act = np.asarray(case.grid.active, bool)
    zc = np.asarray(case.grid.z, float)
    wall = float(zc[act].max()) + 50.0
    prm = json.loads((Path(m["_case_dir"]) / "inputs/case.json").read_text())
    bc = prm["boundaries"]
    west_open = "west" in bc
    # extended grid: a ring of wall cells (none on an open west edge)
    pad_w = 0 if west_open else 1
    xs = np.concatenate([[gx[0] - dx] if pad_w else [], gx, [gx[-1] + dx]])
    ys = np.concatenate([[gy[0] - dx], gy, [gy[-1] + dx]])
    Z = np.full((ys.size, xs.size), wall)
    Hd = np.zeros_like(Z)
    A = np.zeros_like(Z, dtype=bool)
    sl = (slice(1, 1 + gy.size), slice(pad_w, pad_w + gx.size))
    Z[sl] = np.where(act, zc, wall)
    Hd[sl] = np.where(act, np.asarray(case.h, float), 0.0)
    A[sl] = act
    x, y, ikle, ipobo, loop = rect_mesh(xs, ys)
    z, h, a = Z.ravel(), Hd.ravel(), A.ravel()
    codes = {}
    if west_open:
        for nn in loop:
            if np.isclose(x[nn], xs[0]) and a[nn]:
                codes[nn] = (5, 4, 4)
    extra = [f"LAW OF BOTTOM FRICTION = 4", f"FRICTION COEFFICIENT = {float(prm['manning_n'])}"]
    files = {}
    if codes:
        loop, order = open_boundary_order(loop, codes, ipobo)
        tt, lv = demo.read_table(Path(m["_case_dir"]) / "inputs" / bc["west"]["table"])
        files["liq.txt"] = "#\nT SL(1)\ns m\n" + "".join(f"{t:.6f} {v:.6f}\n" for t, v in zip(tt, lv))
        extra.append("LIQUID BOUNDARIES FILE = 'liq.txt'")
    if "inflow" in bc:
        tt, qq = demo.read_table(Path(m["_case_dir"]) / "inputs" / bc["inflow"]["table"])
        cells = np.argwhere(np.asarray(case.inflow_cells, bool))
        n = len(cells)
        # one value per line: TELEMAC truncates long steering-file lines
        sx = ";\n".join(f"{gx[i]:.3f}" for _, i in cells)
        sy = ";\n".join(f"{gy[j]:.3f}" for j, _ in cells)
        extra += [f"ABSCISSAE OF SOURCES =\n{sx}", f"ORDINATES OF SOURCES =\n{sy}",
                  "WATER DISCHARGE OF SOURCES =\n" + ";\n".join(["0."] * n), "SOURCES FILE = 'src.txt'"]
        head = "#\nT " + " ".join(f"Q({k + 1})" for k in range(n)) + "\ns " + " ".join(["m3/s"] * n) + "\n"
        # TELEMAC asks for the value one step before t = 0, so the series starts a day early.
        tt, qq = np.r_[-86400.0, tt], np.r_[qq[0], qq]
        files["src.txt"] = head + "".join(f"{t:.6f} " + " ".join([f"{q / n:.9f}"] * n) + "\n" for t, q in zip(tt, qq))
    t_end = float(prm["t_end_s"])
    cas = (STEERING_2D.format(title=tid, t_end=t_end, extra="\n".join(extra))
           .replace(f"TIME STEP = {t_end}", "TIME STEP = 1.")
           .replace("GRAPHIC PRINTOUT PERIOD = 1", f"GRAPHIC PRINTOUT PERIOD = {int(round(probe_dt))}")
           .replace("VARIABLES FOR GRAPHIC PRINTOUTS = 'U,V,H,B'", "VARIABLES FOR GRAPHIC PRINTOUTS = 'U,V,H'"))
    # probe cells and the active field, as indices into the extended grid
    probes = m["simulation"]["probes"]
    pidx = []
    for p in probes:
        i = int(np.clip((p["x"] - (gx[0] - dx / 2)) // dx, 0, gx.size - 1))
        j = int(np.clip((p.get("y", 0.0) - (gy[0] - dx / 2)) // dx, 0, gy.size - 1))
        pidx.append((1 + j) * xs.size + pad_w + i)
    pidx = np.array(pidx)
    fidx = np.flatnonzero(a)
    frames = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        write_selafin(d / "geo.slf", x, y, ikle, ipobo, {"BOTTOM          M               ": z})
        write_selafin(d / "ini.slf", x, y, ikle, ipobo, {
            "VELOCITY U      M/S             ": np.zeros_like(z), "VELOCITY V      M/S             ": np.zeros_like(z),
            "WATER DEPTH     M               ": h, "BOTTOM          M               ": z})
        rows = []
        for k, nn in enumerate(loop, 1):
            c1, c2, c3 = codes.get(nn, (2, 2, 2))
            rows.append(f"{c1} {c2} {c3} 0.0 0.0 0.0 0.0 {2 if c1 == 2 else 4} 0.0 0.0 0.0 {nn + 1} {k}\n")
        (d / "geo.cli").write_text("".join(rows))
        for name, text in files.items():
            (d / name).write_text(text)
        (d / "t2d.cas").write_text(cas)
        from benchmark1d2d import keep

        keep.inputs("telemac", tid, d, dx)
        proc = subprocess.run([py, str(Path(env["HOMETEL"]) / "scripts/python3/telemac2d.py"), "t2d.cas"],
                              cwd=d, env=env, capture_output=True, text=True, timeout=6 * 3600)
        if proc.returncode != 0 or not (d / "res.slf").is_file():
            raise RuntimeError(f"TELEMAC failed on {tid}:\n{proc.stdout[-3000:]}\n{proc.stderr[-2000:]}")
        for t, vals in iter_selafin(d / "res.slf"):
            hv = next(v for k, v in vals.items() if k.startswith("WATER DEPTH"))
            uv = next(v for k, v in vals.items() if k.startswith("VELOCITY U"))
            vv = next(v for k, v in vals.items() if k.startswith("VELOCITY V"))
            idx = fidx if abs(t / 3600.0 - round(t / 3600.0)) < 1e-6 else pidx
            n = idx.size
            frames.append({"t": np.full(n, t), "x": x[idx], "y": y[idx], "h": np.maximum(hv[idx], 0.0), "u": uv[idx],
                           "v": vv[idx], "p": np.full(n, np.nan), "z": z[idx]})
    return {c: np.concatenate([f[c] for f in frames]) for c in frames[0]}, dx_alt


def telemac_env(prefix: Path) -> tuple[dict, str]:
    home = prefix / "opentelemac"
    env = dict(os.environ)
    env.update({
        "HOMETEL": str(home), "SYSTELCFG": str(home / "systel.cfg"),
        "PATH": f"{home / 'bin'}:{home / 'scripts/python3'}:{prefix / 'bin'}:{env.get('PATH', '')}",
        "PYTHONPATH": f"{home / 'scripts/python3'}:{home / 'lib'}",
        "LD_LIBRARY_PATH": f"{home / 'lib'}:{prefix / 'lib'}:{env.get('LD_LIBRARY_PATH', '')}",
        # Containers often run as root; OpenMPI needs explicit consent (no effect otherwise).
        "OMPI_ALLOW_RUN_AS_ROOT": "1", "OMPI_ALLOW_RUN_AS_ROOT_CONFIRM": "1",
        "PRTE_ALLOW_RUN_AS_ROOT": "1", "PRTE_ALLOW_RUN_AS_ROOT_CONFIRM": "1",
    })
    return env, str(prefix / "bin" / "python")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--telemac-prefix", type=Path, default=Path(os.environ.get("TELEMAC_PREFIX", "")),
                    help="conda environment with opentelemac installed")
    ap.add_argument("cases", nargs="*", default=list(CASES) + sorted(CASES_2D))
    args = ap.parse_args()
    env, py = telemac_env(args.telemac_prefix)
    meta = json.loads(next((args.telemac_prefix / "conda-meta").glob("opentelemac-*.json")).read_text())
    version = meta["version"]
    solver = {"name": f"openTELEMAC-2D {version}", "version": version, "adapter": "telemac2d (Selafin, centreline nodes)"}
    OUT.mkdir(parents=True, exist_ok=True)
    ok = True
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        if tid.startswith(EA_CASES):
            t0 = time.perf_counter()
            cols, dx_alt = run_ea(tid, m, env, py)
            p = write_results_parquet(OUT / f"{m['test_id']}.parquet", cols, wall_seconds=time.perf_counter() - t0)
            sv = dict(solver, adapter="telemac2d (Selafin, nodes at the grid's cell centres)")
            if dx_alt:
                sv["name"] += f" at {dx_alt:g} m (spec alternative resolution)"
            card = score_case(m, p, timestamp=TS, private_key=KEY, solver=sv)
            (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({sv['name']})", flush=True)
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}  {r.get('detail', '')}", flush=True)
            ok &= card["passed"]
            continue
        paths = []
        for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
            t0 = time.perf_counter()
            cols = (run_level_2d if tid in CASES_2D else run_level)(tid, m, float(dx), env, py)
            paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx}.parquet", cols, wall_seconds=time.perf_counter() - t0))
            print(f"  {tid} dx={dx}: t={cols['t'][0]:.3f} s")
        sv = solver if tid not in ("A2A-020", "A1F-020") else dict(solver, adapter=solver["adapter"] + "; HLLC scheme (the default kinetic scheme is unstable here)")
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=KEY, solver=sv)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        c = card.get("convergence_result") or {}
        print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
        ok &= card["passed"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
