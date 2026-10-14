#!/usr/bin/env python3
"""Score openTELEMAC-2D on the dam-break cases (an independent, production solver).

TELEMAC-2D (openTELEMAC v9.1, conda-forge ``opentelemac``) is run as a black
box on each refinement level of A1F-010 (Ritter, dry bed) and A1F-011
(Stoker, wet bed):

- mesh: a 2D strip two triangles-pairs wide, so the 1D problem is solved by a
  genuine 2D unstructured solver; slip walls all round (no wave reaches the
  ends before t_end)
- numerics: TELEMAC's default finite-volume set-up (kinetic scheme, first
  order), variable time step; no tuning to the case. HLLC and second-order
  variants were tried and leave the wet-front lag on A1F-010 unchanged.
- initial state: the dam-break step, written as a "previous computation" file

The centreline nodes at the final time become the results file; scoring is
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


def read_selafin_last(path: Path) -> tuple[float, dict[str, np.ndarray]]:
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
    last = None
    while pos < len(data):
        t_body = rec()
        t = struct.unpack(">f", t_body)[0] if len(t_body) == 4 else struct.unpack(">d", t_body)[0]
        vals = {}
        for nm in names:
            body = rec()
            fmt = "f" if len(body) == 4 * npoin else "d"
            vals[nm] = np.array(struct.unpack(f">{npoin}{fmt}", body))
        last = (t, vals)
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
TIME STEP = 0.01
DURATION = {t_end}
GRAPHIC PRINTOUT PERIOD = 100000000
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
    ap.add_argument("cases", nargs="*", default=list(CASES))
    args = ap.parse_args()
    env, py = telemac_env(args.telemac_prefix)
    meta = json.loads(next((args.telemac_prefix / "conda-meta").glob("opentelemac-*.json")).read_text())
    version = meta["version"]
    solver = {"name": f"openTELEMAC-2D {version}", "version": version, "adapter": "telemac2d (Selafin, centreline nodes)"}
    OUT.mkdir(parents=True, exist_ok=True)
    ok = True
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        paths = []
        for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
            cols = run_level(tid, m, float(dx), env, py)
            paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx}.parquet", cols))
            print(f"  {tid} dx={dx}: t={cols['t'][0]:.3f} s")
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=KEY, solver=solver)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{'PASS' if card['passed'] else 'FAIL'} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        c = card.get("convergence_result") or {}
        print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
        ok &= card["passed"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
