#!/usr/bin/env python3
"""Sensitivity envelope for any model the suite can re-run with other settings.

Evidence protocol 4.0 §3 asks how much an engineer's reasonable choices move a
result. For one model, this re-runs it on its tests once per variant, changing
one documented solver option at a time from the published set-up, through the
same mechanism as a proposed set-up (``benchmark1d2d.setups``), and scores every
run with the same scorer. The envelope is the range of each test's percent
difference over the variants, with the variant at each end.

Each variant list below is limited to options the engine's own documentation
leaves to the user for this kind of flow; what the test defines (geometry,
boundaries, friction, grid, end time) never changes.

Writes ``site/fixtures/sensitivity/<model>.json`` (the format of
``scripts/sensitivity_swmm.py``, which remains the SWMM 5.2.4 sweep).

Usage::

    python scripts/sensitivity.py MODEL [cases ...] [runner options, as for scripts/run_setup.py]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO / "site"), str(REPO / "scripts")]
OUT = REPO / "site" / "fixtures" / "sensitivity"

SWMM = {
    "default-iteration": ("SWMM's own iteration defaults (HEAD_TOLERANCE 0.0015 m, MAX_TRIALS 8)", {"HEAD_TOLERANCE": "0"}),
    "converged-iteration": ("Iteration converged: HEAD_TOLERANCE 0.00001 m, MAX_TRIALS 20", {"HEAD_TOLERANCE": "0.00001", "MAX_TRIALS": "20"}),
    "normal-flow-froude": ("NORMAL_FLOW_LIMITED FROUDE", {"NORMAL_FLOW_LIMITED": "FROUDE"}),
    "normal-flow-slope": ("NORMAL_FLOW_LIMITED SLOPE", {"NORMAL_FLOW_LIMITED": "SLOPE"}),
    "damping-none": ("INERTIAL_DAMPING NONE", {"INERTIAL_DAMPING": "NONE"}),
    "damping-full": ("INERTIAL_DAMPING FULL", {"INERTIAL_DAMPING": "FULL"}),
    "variable-step-0.5": ("VARIABLE_STEP 0.5 (smaller time steps)", {"VARIABLE_STEP": "0.5"}),
}
VARIANTS = {
    "swmm515": SWMM,
    "openswmm-dw": SWMM,
    "openswmm-fv": {"variable-step-0.5": ("VARIABLE_STEP 0.5 (smaller time steps)", {"VARIABLE_STEP": "0.5"}),
                    "variable-step-0.9": ("VARIABLE_STEP 0.9 (larger time steps)", {"VARIABLE_STEP": "0.9"})},
    "telemac": {
        "scheme-roe": ("FINITE VOLUME SCHEME = 0 (Roe)", {"FINITE VOLUME SCHEME": "0"}),
        "scheme-hll": ("FINITE VOLUME SCHEME = 5 (HLLC)", {"FINITE VOLUME SCHEME": "5"}),
        "scheme-waf": ("FINITE VOLUME SCHEME = 6 (WAF)", {"FINITE VOLUME SCHEME": "6"}),
        "courant-0.25": ("DESIRED COURANT NUMBER = 0.25", {"DESIRED COURANT NUMBER": "0.25"}),
        "courant-0.9": ("DESIRED COURANT NUMBER = 0.9", {"DESIRED COURANT NUMBER": "0.9"}),
    },
    "lisflood-fv1": {"cfl-0.5": ("cfl 0.5 (smaller time steps)", {"cfl": "0.5"}), "cfl-0.9": ("cfl 0.9", {"cfl": "0.9"})},
    "lisflood-dg2": {"cfl-0.2": ("cfl 0.2 (smaller time steps)", {"cfl": "0.2"}), "cfl-0.33": ("cfl 0.33", {"cfl": "0.33"})},
    "lisflood-acc": {"alpha-0.5": ("cfl (alpha) 0.5 (smaller time steps)", {"cfl": "0.5"}), "alpha-0.9": ("cfl (alpha) 0.9", {"cfl": "0.9"}),
                     "theta-0.7": ("theta 0.7 (more upwinding)", {"theta": "0.7"})},
}


def main() -> int:
    import difference  # site/difference.py: the same percent difference the site shows
    import run_setup

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("model", choices=sorted(VARIANTS))
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--openswmm-python")
    ap.add_argument("--swmm51-python")
    ap.add_argument("--telemac-prefix")
    ap.add_argument("--lisflood-exe")
    a = ap.parse_args()
    variants = {"published": ("As published", {})} | VARIANTS[a.model]
    results: dict[str, dict[str, dict]] = {}
    out = OUT / f"{a.model}.json"

    def write(partial: bool) -> dict:
        env = {}
        for c, by in results.items():
            done = {k: v for k, v in by.items() if v.get("completed") and v.get("percent_difference") is not None}
            if not done:
                continue
            lo = min(done, key=lambda k: done[k]["percent_difference"])
            hi = max(done, key=lambda k: done[k]["percent_difference"])
            env[c] = {"low": done[lo]["percent_difference"], "low_variant": lo, "high": done[hi]["percent_difference"], "high_variant": hi,
                      "published": (by.get("published") or {}).get("percent_difference"), "variants": by}
        target = out.with_suffix(".partial.json") if partial else out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"model": a.model, "date": date.today().isoformat(), "script": "scripts/sensitivity.py",
                                      "variants": {k: v[0] for k, v in variants.items()}, "tests": env}, indent=1) + "\n", encoding="utf-8")
        return env

    with tempfile.TemporaryDirectory() as tdn:
        for name, (title, opts) in variants.items():
            # every variant, the published one included, runs through the same path, so they differ only in the options
            f = Path(tdn) / f"sens-{name}" / "setup.json"
            f.parent.mkdir(parents=True)
            f.write_text(json.dumps({"schema_version": "1.0.0", "base": a.model, "title": title[:60], "proposed_by": "sensitivity sweep",
                                     "tests": a.cases or "all", "settings": opts, "reason": "One option at a time from the published set-up."}),
                         encoding="utf-8")
            dest = run_setup.OUT / f"sens-{name}"
            shutil.rmtree(dest, ignore_errors=True)
            sys.argv = ["run_setup.py", str(f)] + sum(([f"--{o.replace('_', '-')}", getattr(a, o)] for o in
                                                      ("openswmm_python", "swmm51_python", "telemac_prefix", "lisflood_exe") if getattr(a, o)), [])
            run_setup.main()
            for path in dest.glob("*.scorecard.json"):
                card = json.loads(path.read_text(encoding="utf-8"))
                rep = ((card.get("run") or {}).get("engine") or {})
                conv = card.get("convergence_result") or {}
                results.setdefault(card["test_id"].split("_")[0], {})[name] = {
                    "completed": True, "percent_difference": difference.result(card),
                    "observed_order": conv.get("observed_order"), "engine_flagged": bool(rep.get("flagged"))}
            shutil.rmtree(dest, ignore_errors=True)
            write(partial=True)
    env = write(partial=False)
    out.with_suffix(".partial.json").unlink(missing_ok=True)
    for c, e in env.items():
        print(f"{c}: {e['low']:.3g} % ({e['low_variant']}) to {e['high']:.3g} % ({e['high_variant']}); published {e['published']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
