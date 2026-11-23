#!/usr/bin/env python3
"""Re-run proposed set-ups (``setups/<slug>/setup.json``) with the base model's own runner.

For each set-up, this picks the runner that writes the base model, runs it on
the set-up's tests with ``BENCH_SETUP`` naming the file (the runner applies the
settings to the model files it writes; see ``benchmark1d2d.setups``), and
copies the score cards that carry the set-up to ``out/setups/<slug>/``. Cards
without it (tests the set-up does not cover) are left out, so a set-up run
never replaces the suite's own results.

Engines are found through the same options the solver workflows use.

Usage::

    python scripts/run_setup.py setups/<slug>/setup.json ... [--family swmm|telemac|lisflood]
        [--openswmm-python PY] [--swmm51-python PY] [--telemac-prefix DIR] [--lisflood-exe EXE]
    python scripts/run_setup.py --list-families SETUP ...   # print the engine families the set-ups need
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO / "scripts")]
OUT = REPO / "out" / "setups"
FAMILY = {"swmm": {"swmm524", "swmm515", "openswmm-dw", "openswmm-fv"}, "telemac": {"telemac"},
          "lisflood": {"lisflood-fv1", "lisflood-dg2", "lisflood-acc"}, "hecras": {"hecras", "hecras-em"}, "landlab": {"landlab"}, "openswmm-2d": {"openswmm-2d", "openswmm-2d-x"},
          "hydronet": {"hydronet-fvm"}}


def family_of(base: str) -> str | None:
    return next((f for f, ks in FAMILY.items() if base in ks), None)


def runs_for(s: dict, a: argparse.Namespace) -> list[tuple[list[str], Path]]:
    """[(command, folder its score cards land in)] for one set-up."""
    base, tests = s["base"], s.get("tests") or "all"
    py = sys.executable

    def pick(cases: list[str]) -> list[str]:
        return cases if tests == "all" else [c for c in cases if c in tests]

    out = []
    if base in FAMILY["swmm"]:
        import run_swmm_track_a as ta

        extra = (["--openswmm-python", a.openswmm_python] if a.openswmm_python else []) + (["--swmm51-python", a.swmm51_python] if a.swmm51_python else [])
        c1 = pick(list(ta.CASES))
        if c1:
            out.append(([py, "scripts/run_swmm_track_a.py", *c1, "--engines", base, *extra], REPO / "out" / "swmm_track_a" / base))
        import run_drainage_cases as dc

        c2 = pick(list(dc.CASES))
        if c2:
            out.append(([py, "scripts/run_drainage_cases.py", *c2, "--engines", base, *extra], REPO / "out" / "swmm_track_a" / base))
    elif base == "telemac":
        import run_telemac as rt

        c = pick(list(rt.CASES) + sorted(rt.CASES_2D))
        if c:
            out.append(([py, "scripts/run_telemac.py", "--telemac-prefix", a.telemac_prefix or os.environ.get("TELEMAC_PREFIX", ""), *c], REPO / "out" / "telemac"))
    elif base in FAMILY["hecras"]:
        import run_hecras_2d as rh

        c = pick(list(rh.CASES))
        eq = "em" if base == "hecras-em" else "elm"
        if c:
            out.append(([py, "scripts/run_hecras_2d.py", "--accept-hec-terms", *c, "--equations", eq], REPO / "out" / "hecras2d" / eq))
    elif base == "hydronet-fvm":
        import run_hydronet as hn

        c = pick(list(hn.CASES))
        if c:
            out.append(([py, "scripts/run_hydronet.py", "--hydronet", a.hydronet or os.environ.get("HYDRONET", ""), *c, "--mode", "fvm"],
                        REPO / "out" / "hydronet" / "fvm"))
    elif base == "landlab":
        import run_landlab as rl2

        c = pick(list(rl2.CASES))
        if c:
            out.append(([py, "scripts/run_landlab.py", *c], REPO / "out" / "landlab"))
    elif base in FAMILY["openswmm-2d"]:
        import run_openswmm_coupled as oc

        c = pick(list(oc.CASES))
        mesh = next(k for k, (mk, _) in oc.MESHES.items() if mk == base)
        if c:
            out.append(([py, "scripts/run_openswmm_coupled.py", "--openswmm-python", a.openswmm_python or sys.executable, *c, "--mesh", mesh],
                        REPO / "out" / "coupled" / base))
    elif base.startswith("lisflood-"):
        import run_lisflood as rl

        c = pick(list(rl.CASES) + list(rl.EA_CASES))
        if c:
            out.append(([py, "scripts/run_lisflood.py", "--exe", a.lisflood_exe or "lisflood", *c, "--solver", base.split("-", 1)[1]], REPO / "out" / "lisflood"))
    return out


def main() -> int:
    from benchmark1d2d import setups

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("setups", nargs="+", type=Path)
    ap.add_argument("--family", choices=list(FAMILY), help="only the set-ups of this engine family")
    ap.add_argument("--list-families", action="store_true")
    ap.add_argument("--openswmm-python")
    ap.add_argument("--hydronet", help="a HydroNet checkout (for hydronet-fvm set-ups)")
    ap.add_argument("--swmm51-python")
    ap.add_argument("--telemac-prefix")
    ap.add_argument("--lisflood-exe")
    a = ap.parse_args()
    files = [p if p.suffix == ".json" else p / "setup.json" for p in a.setups]
    if a.list_families:
        fams = sorted({family_of(json.loads(f.read_text(encoding="utf-8"))["base"]) or "" for f in files if f.is_file()} - {""})
        print(" ".join(fams))
        return 0
    failed = 0
    for f in files:
        s = json.loads(f.read_text(encoding="utf-8"))
        problems = [] if s.get("proposed_by") == "sensitivity sweep" and f.parent.name.startswith("sens-") else setups.check(s)
        if problems:
            print(f"{f}: not run: " + "; ".join(problems))
            failed += 1
            continue
        if a.family and family_of(s["base"]) != a.family:
            continue
        slug = s.get("slug") or f.parent.name
        dest = OUT / slug
        dest.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, BENCH_SETUP=str(f.resolve()))
        print(f"== set-up {slug}: {s['title']} ({s['base']}, by {s['proposed_by']})", flush=True)
        for cmd, folder in runs_for(s, a):
            print("   " + " ".join(cmd[1:]), flush=True)
            subprocess.run(cmd, cwd=REPO, env=env, check=False)
            for card in sorted(folder.rglob("*.scorecard.json")):
                c = json.loads(card.read_text(encoding="utf-8"))
                if ((c.get("solver") or {}).get("setup") or {}).get("slug") == slug:
                    shutil.copy2(card, dest / card.name)
                    card.unlink()  # not the suite's own result: keep it out of the base model's folder
        n = len(list(dest.glob("*.scorecard.json")))
        print(f"   {n} score card(s) in {dest.relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
