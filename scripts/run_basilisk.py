#!/usr/bin/env python3
"""Score Basilisk's Saint-Venant solver on the catalog's grid tests.

Basilisk (Popinet; http://basilisk.fr, GPL) is an open-source solver
framework for PDEs on adaptive Cartesian grids. Its ``saint-venant.h`` is a
second-order, well-balanced finite-volume shallow-water solver (Kurganov
central-upwind fluxes, hydrostatic reconstruction; Popinet 2011). Each test
is written as a small Basilisk C program (generated below), compiled with
``qcc`` and run on a uniform grid at each refinement level: ``cartesian1D``
for the 1D tests, ``multigrid`` with ``dimensions()`` for the rectangular 2D
domains. The solver's own defaults are kept (CFL 0.5, generalised minmod
limiter, dry depth 1e-10 m); only what a test needs is set:

* inflow of a unit discharge: the normal velocity held at q / h on the
  boundary (Basilisk's ``discharge.h`` works only in 2D, so the same rule is
  used in 1D and 2D);
* a held depth: ``h`` and ``eta`` set on the boundary, the velocity free;
* a supercritical inflow: depth and velocity both set;
* walls: Basilisk's default (symmetry, i.e. free-slip walls);
* Manning friction (A1F-001, A2A-010): Basilisk's Saint-Venant solver has
  none built in; the usual semi-implicit term ``u /= 1 + g n² dt |u| / h^(4/3)``
  is applied after every step, as in Basilisk's own examples.

Basilisk is distributed as a rolling source snapshot; the card names the
snapshot by the SHA-256 of the tarball that was built.

Score cards go to ``out/basilisk/``. Usage::

    curl -O https://basilisk.fr/basilisk/basilisk.tar.gz && tar xzf basilisk.tar.gz
    (cd basilisk/src && ln -s config.gcc config && make -k; make)
    python scripts/run_basilisk.py --basilisk basilisk/src [--snapshot SHA] [CASE ...]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "basilisk"
from benchmark1d2d.clock import run_timestamp  # noqa: E402

TS = run_timestamp()  # when this run happened (BENCH_TIMESTAMP pins it)
G = 9.81

FRICTION = """
event friction (i++) {{
  foreach() {{
    double un = sqrt({usq});
    double a = h[] < dry ? HUGE : 1. + G*sq({n})*dt*un/pow(h[], 4./3.);
    foreach_dimension() u.x[] /= a;
  }}
}}
"""


def _table(name: str, xs: np.ndarray, zs: np.ndarray) -> str:
    """A bed given as a table, interpolated linearly (C)."""
    vals = ",".join(f"{v:.12g}" for v in zs)
    return (f"static const double {name}_x0 = {xs[0]:.12g}, {name}_dx = {xs[1] - xs[0]:.12g};\n"
            f"static const int {name}_n = {len(xs)};\nstatic const double {name}_z[] = {{{vals}}};\n"
            f"static double {name} (double x) {{ double s = (x - {name}_x0)/{name}_dx; int k = (int) floor(s);\n"
            f"  if (k < 0) return {name}_z[0]; if (k >= {name}_n - 1) return {name}_z[{name}_n - 1];\n"
            f"  return {name}_z[k] + (s - k)*({name}_z[k + 1] - {name}_z[k]); }}\n")


def program(tid: str, m: dict) -> tuple[str, dict]:
    """(Basilisk C source, layout) for a test; layout: dim, x0, y0, L, W, levels' cell counts."""
    case = Path(m["_case_dir"])
    t_end = float(m["simulation"]["t_end"])
    head1 = '#include "grid/cartesian1D.h"\n#include "saint-venant.h"\n'
    head2 = '#include "grid/multigrid.h"\n#include "saint-venant.h"\n'
    out1 = 'event end (t = %g) { foreach() printf ("%%.12g %%.12g %%.12g %%.12g\\n", x, h[], u.x[], zb[]); }\n' % t_end
    out2 = 'event end (t = %g) { foreach() printf ("%%.12g %%.12g %%.12g %%.12g %%.12g %%.12g\\n", x, y, h[], u.x[], u.y[], zb[]); }\n' % t_end
    main1 = 'int main (int argc, char * argv[]) {{ size ({L:.12g}); origin ({x0:.12g}); G = 9.81; init_grid (atoi (argv[1])); run(); }}\n'
    if tid in ("A1F-010", "A1F-011"):
        p = json.loads((case / "inputs/params.json").read_text())
        dom, ic = p["domain"], p["initial_condition"]
        L, x0 = dom["xmax"] - dom["xmin"], dom["xmin"]
        src = (head1 + main1.format(L=L, x0=x0)
               + f"event init (i = 0) {{ foreach() {{ zb[] = 0.; h[] = x < {ic['dam_x_m']:.12g} ? {ic['h_left_m']:.12g} : {ic['h_right_m']:.12g}; u.x[] = 0.; }} }}\n"
               + out1)
        return src, {"dim": 1, "x0": x0, "L": L}
    if tid == "A1F-020":
        from references.belanger import sequent_depths

        p = json.loads((case / "inputs/params.json").read_text())
        L = p["domain"]["xmax"]
        up = p["boundaries"]["upstream"]
        r = sequent_depths(np.array([0.0]), Fr1=up["Fr"], h1=up["h_m"], L=L)
        h1, h2, q = r["h1"], r["h2"], r["q"]
        src = (head1
               + f"h[left] = dirichlet ({h1:.12g}); eta[left] = dirichlet ({h1:.12g}); u.n[left] = dirichlet ({q / h1:.12g});\n"
               + f"h[right] = dirichlet ({h2:.12g}); eta[right] = dirichlet ({h2:.12g}); u.n[right] = neumann (0.);\n"
               + main1.format(L=L, x0=0.0)
               + f"event init (i = 0) {{ foreach() {{ zb[] = 0.; h[] = x < {L / 2:.12g} ? {h1:.12g} : {h2:.12g}; u.x[] = {q:.12g}/h[]; }} }}\n"
               + out1)
        return src, {"dim": 1, "x0": 0.0, "L": L}
    if tid in ("A1F-040", "A1F-041", "A1F-042", "A1F-043"):
        p = json.loads((case / "inputs/params.json").read_text())
        L = p["domain"]["xmax"]
        up, down = p["upstream"], p["downstream"]
        bc = ""
        if "discharge_m2s" in up:
            bc += f"u.n[left] = dirichlet ({up['discharge_m2s']:.12g}/max (h[], 1e-6));\n"
        if "depth_m" in down and not down.get("applies"):
            bc += f"h[right] = dirichlet ({down['depth_m']:.12g}); eta[right] = dirichlet ({down['depth_m']:.12g}); u.n[right] = neumann (0.);\n"
        elif "depth_m" in down:  # SWASHES: held only while the outflow is subcritical; at steady state it is supercritical
            hd = down["depth_m"]  # the bed is flat (z = 0) at the outlet, so eta = h there
            bc += (f"h[right] = sq(u.x[]) < G*h[] ? 2.*{hd:.12g} - h[] : h[]; eta[right] = sq(u.x[]) < G*h[] ? 2.*{hd:.12g} - eta[] : eta[];"
                   " u.n[right] = neumann (0.);\n")
        level = p["initial"]["level_m"]
        src = (head1 + bc + main1.format(L=L, x0=0.0)
               + f"event init (i = 0) {{ foreach() {{ zb[] = (x > 8. && x < 12.) ? 0.2 - 0.05*sq(x - 10.) : 0.; h[] = max ({level:.12g} - zb[], 0.); u.x[] = 0.; }} }}\n"
               + out1)
        return src, {"dim": 1, "x0": 0.0, "L": L}
    if tid == "A1F-001":
        from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

        L, B, Q, n = (float(M1_PARAMS[k]) for k in ("L", "B", "Q", "n_manning"))
        xs = np.linspace(0.0, L, 4001)
        zs = bed_elevation(xs)
        h_out = float(depth_profile(np.array([L]))[0])
        src = (head1 + _table("bed", xs, zs)
               + f"u.n[left] = dirichlet ({Q / B:.12g}/max (h[], 1e-6));\n"
               + f"h[right] = dirichlet ({h_out:.12g}); eta[right] = dirichlet ({zs[-1] + h_out:.12g}); u.n[right] = neumann (0.);\n"
               + main1.format(L=L, x0=0.0)
               + f"event init (i = 0) {{ foreach() {{ zb[] = bed (x); h[] = {h_out:.12g}; u.x[] = 0.; }} }}\n"
               + FRICTION.format(usq="sq(u.x[])", n=n) + out1)
        return src, {"dim": 1, "x0": 0.0, "L": L}
    if tid == "A2A-001":
        from references.thacker import bed_elevation

        prm = m["reference"]["generator"]["parameters"]
        dom = json.loads((case / "inputs/params.json").read_text())["domain"]
        h0, L, eta = prm["h0"], prm["L"], prm["eta"]
        assert np.isclose(bed_elevation(0.0, 0.0, h0, L), -h0)
        size = dom["xmax"] - dom["xmin"]
        src = (head2
               + "int main (int argc, char * argv[]) {{ dimensions (nx = atoi (argv[2]), ny = atoi (argv[2])); size ({s:.12g}); origin ({x0:.12g}, {y0:.12g}); G = 9.81; init_grid (atoi (argv[1])); run(); }}\n".format(s=size, x0=dom["xmin"], y0=dom["ymin"])
               + f"event init (i = 0) {{ foreach() {{ zb[] = {h0:.12g}*((sq(x) + sq(y))/{L * L:.12g} - 1.); "
               + f"h[] = max ({eta * h0 / L ** 2:.12g}*(2.*x - {eta:.12g}) - zb[], 0.); u.x[] = u.y[] = 0.; }} }}\n"
               + out2)
        return src, {"dim": 2, "x0": dom["xmin"], "y0": dom["ymin"], "L": size, "W": size}
    if tid == "A2A-010":
        from references.macdonald_2d import bed_elevation, depth_profile

        prm = m["reference"]["generator"]["parameters"]
        L, W, q, n = prm["L"], prm["W"], prm["q"], prm["n_manning"]
        xs = np.linspace(0.0, L, 4001)
        zs = bed_elevation(xs, L=L, q=q, n_manning=n)
        h_out = float(depth_profile(L))
        src = (head2 + _table("bed", xs, zs)
               + f"u.n[left] = dirichlet ({q:.12g}/max (h[], 1e-6)); u.t[left] = dirichlet (0.);\n"
               + f"h[right] = dirichlet ({h_out:.12g}); eta[right] = dirichlet ({zs[-1] + h_out:.12g}); u.n[right] = neumann (0.);\n"
               + "int main (int argc, char * argv[]) {{ dimensions (nx = atoi (argv[2]), ny = atoi (argv[3])); size ({L:.12g}); origin (0., 0.); G = 9.81; init_grid (atoi (argv[1])); run(); }}\n".format(L=L)
               + f"event init (i = 0) {{ foreach() {{ zb[] = bed (x); h[] = {h_out:.12g}; u.x[] = u.y[] = 0.; }} }}\n"
               + FRICTION.format(usq="sq(u.x[]) + sq(u.y[])", n=n) + out2)
        return src, {"dim": 2, "x0": 0.0, "y0": 0.0, "L": L, "W": W}
    if tid == "A2A-020":
        from references.oblique_jump import states

        prm = m["reference"]["generator"]["parameters"]
        dom = json.loads((case / "inputs/params.json").read_text())["domain"]
        st = states(prm["Fr1"], prm["theta_deg"], prm["h1"], prm.get("g", G))
        h1, u1, v1 = st["h1"], st["u1"], st["v1"]
        L, W = dom["xmax"] - dom["xmin"], dom["ymax"] - dom["ymin"]
        bc = ""
        for side, un, ut in (("left", u1, v1), ("top", v1, u1)):
            bc += f"h[{side}] = dirichlet ({h1:.12g}); eta[{side}] = dirichlet ({h1:.12g}); u.n[{side}] = dirichlet ({un:.12g}); u.t[{side}] = dirichlet ({ut:.12g});\n"
        bc += "h[right] = neumann (0.); eta[right] = neumann (0.); u.n[right] = neumann (0.); u.t[right] = neumann (0.);\n"
        src = (head2 + bc
               + "int main (int argc, char * argv[]) {{ dimensions (nx = atoi (argv[2]), ny = atoi (argv[3])); size ({L:.12g}); origin ({x0:.12g}, {y0:.12g}); G = 9.81; init_grid (atoi (argv[1])); run(); }}\n".format(L=L, x0=dom["xmin"], y0=dom["ymin"])
               + f"event init (i = 0) {{ foreach() {{ zb[] = 0.; h[] = {h1:.12g}; u.x[] = {u1:.12g}; u.y[] = {v1:.12g}; }} }}\n"
               + out2)
        return src, {"dim": 2, "x0": dom["xmin"], "y0": dom["ymin"], "L": L, "W": W}
    raise KeyError(tid)


CASES = ["A1F-010", "A1F-011", "A1F-020", "A1F-001", "A1F-040", "A1F-041", "A1F-042", "A1F-043", "A2A-001", "A2A-010", "A2A-020"]


def run_level(exe: Path, lay: dict, dx: float, dx0: float, t_end: float) -> dict:
    n = int(round(lay["L"] / dx))
    args = [str(exe), str(n)]
    if lay["dim"] == 2:
        nx0, ny0 = int(round(lay["L"] / dx0)), int(round(lay["W"] / dx0))
        args += [str(nx0), str(ny0)]
    p = subprocess.run(args, capture_output=True, text=True, timeout=7200)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:])
    d = np.loadtxt([ln for ln in p.stdout.splitlines() if ln and not ln.startswith("#")], ndmin=2)
    nan = np.full(len(d), np.nan)
    if lay["dim"] == 1:
        return {"t": np.full(len(d), t_end), "x": d[:, 0], "y": nan, "h": np.maximum(d[:, 1], 0.0), "u": d[:, 2], "v": nan.copy(),
                "p": nan.copy(), "Q": np.maximum(d[:, 1], 0.0) * d[:, 2]}
    return {"t": np.full(len(d), t_end), "x": d[:, 0], "y": d[:, 1], "h": np.maximum(d[:, 2], 0.0), "u": d[:, 3], "v": d[:, 4],
            "p": nan, "z": d[:, 5]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=CASES)
    ap.add_argument("--basilisk", type=Path, required=True, help="Basilisk's src folder (with qcc built)")
    ap.add_argument("--snapshot", default="", help="SHA-256 of the basilisk.tar.gz that was built (names the version)")
    args = ap.parse_args()

    from benchmark1d2d.signing import private_key as signing_key

    from benchmark1d2d import keep
    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    bas = args.basilisk.resolve()
    env = dict(os.environ, BASILISK=str(bas), PATH=f"{bas}:{os.environ.get('PATH', '')}")
    key = signing_key()  # BENCH_SIGNING_KEY, else the public development key
    ver = f"snapshot {args.snapshot[:8]}" if args.snapshot else "snapshot"
    solver = {"name": f"Basilisk Saint-Venant ({ver})", "version": ver,
              "adapter": "basilisk saint-venant.h (uniform Cartesian grid, defaults; a C program per test, generated by scripts/run_basilisk.py)"}
    OUT.mkdir(parents=True, exist_ok=True)
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        src, lay = program(tid, m)
        levels = sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True)
        t_end = float(m["simulation"]["t_end"])
        with tempfile.TemporaryDirectory() as tdn:
            td = Path(tdn)
            (td / "case.c").write_text(src, encoding="ascii")
            keep.inputs("basilisk", tid, td, None, files=["case.c"])
            c = subprocess.run(["qcc", "-O2", "-Wall", "-disable-dimensions", "case.c", "-o", "case", "-lm"], cwd=td, env=env, capture_output=True, text=True)
            if c.returncode != 0:
                print(f"  {tid}: did not compile:\n{c.stdout[-1500:]}{c.stderr[-1500:]}")
                continue
            paths = []
            try:
                for dx in levels:
                    t0 = time.perf_counter()
                    cols = run_level(td / "case", lay, float(dx), float(levels[0]), t_end)
                    paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx:g}.parquet", cols, wall_seconds=time.perf_counter() - t0))
                    print(f"  {tid} dx={dx}: {time.perf_counter() - t0:.1f}s", flush=True)
            except Exception as exc:  # noqa: BLE001 - a run that fails is a finding
                print(f"  {tid}: did not run: {str(exc)[-800:]}")
                continue
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        cr = card.get("convergence_result") or {}
        print(f"    convergence p={cr.get('observed_order')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
