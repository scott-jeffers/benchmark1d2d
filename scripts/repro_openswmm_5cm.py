#!/usr/bin/env python3
"""Review F13: A1F-040 (SWASHES subcritical bump) on EPA SWMM 5.2.4 and OpenSWMM 6 dynamic wave,
with the published options and with HEAD_TOLERANCE 0.00001 m / MAX_TRIALS 20, on the 20, 10 and 5 cm
conduit grids. Uses the committed inputs (site/fixtures/inputs/A1F-040/swmm524.zip, unzipped into
WORK/epa) and prints each engine's convergence report and the final-depth difference.

    python scripts/repro_openswmm_5cm.py WORK /path/to/python-with-openswmm
"""
import sys, subprocess, re
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runner/python"))
from benchmark1d2d.adapters.swmm5 import read_out
from benchmark1d2d.adapters import openswmm
from benchmark1d2d.engine_report import swmm_report
S = Path(sys.argv[1]); OSW = sys.argv[2]
EPA = ("import os,sys\nfrom swmm.toolkit import solver\nos.chdir(os.path.dirname(sys.argv[1]))\nsolver.swmm_run(*sys.argv[1:4])\n")
res = {}
for dx in ("0.2", "0.1", "0.05"):
    src = (S / "epa" / f"dx{dx}" / "m.inp").read_text()
    for opt in ("published", "tight"):
        txt = src if opt == "published" else src.replace("MAX_TRIALS 8", "MAX_TRIALS 20").replace("HEAD_TOLERANCE 0.0005", "HEAD_TOLERANCE 0.00001")
        for eng in ("epa", "osw"):
            d = S / "runs" / f"{eng}_{opt}_{dx}"; d.mkdir(parents=True, exist_ok=True)
            inp = d / "m.inp"; inp.write_text(txt)
            if eng == "epa":
                subprocess.run([sys.executable, "-c", EPA, str(inp), str(d/"m.rpt"), str(d/"m.out")], check=True, capture_output=True)
            else:
                openswmm.run(OSW, inp, d/"m.rpt", d/"m.out")
            o = read_out(d / "m.out")
            names = sorted(o["nodes"])
            h = np.array([o["nodes"][n][-1] for n in names])
            rep = swmm_report(d / "m.rpt") or {}
            res[(eng, opt, dx)] = h
            print(eng, opt, dx, "nodes", len(h), "final depth mean %.4f" % h.mean(), "unconv %", rep.get("steps_not_converging_pct"), "cont %", rep.get("routing_continuity_pct"), flush=True)
for opt in ("published", "tight"):
    for dx in ("0.2", "0.1", "0.05"):
        a, b = res[("epa", opt, dx)], res[("osw", opt, dx)]
        print(f"{opt} dx={dx}: max |EPA - OpenSWMM| final depth {np.abs(a-b).max():.4f} m, mean {np.abs(a-b).mean():.5f} m")
