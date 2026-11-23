#!/usr/bin/env python3
"""Sensitivity envelope: EPA SWMM 5.2.4's results over the set-up choices a competent user could make.

Evidence protocol 4.0 §3 asks how much an engineer's reasonable choices move
a result. This reruns EPA SWMM 5.2.4 on each of its Track A channel tests
(``scripts/run_swmm_track_a.py``), changing one numerical option at a time
from the published configuration, and scores every run with the same scorer.
The written envelope is the range of each test's percent difference over the
variants, with the variant at each end.

The variants are the options SWMM's manual leaves to the user for dynamic-wave
routing: the iteration (head tolerance and trials, including SWMM's own
defaults), the normal-flow limitation, inertial damping and the variable-step
safety factor. The geometry, boundaries, friction, grid and routing step are
the test's own and stay fixed.

Writes ``site/fixtures/sensitivity/swmm524.json``. Usage::

    python scripts/sensitivity_swmm.py [cases ...]
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runner" / "python"))
sys.path.insert(0, str(REPO / "site"))
OUT = REPO / "site" / "fixtures" / "sensitivity" / "swmm524.json"

# One option at a time from the published configuration (the harness), plus SWMM's own iteration defaults.
VARIANTS = {
    "published": ("As published (the harness's settings)", {}),
    "default-iteration": ("SWMM's own iteration defaults: HEAD_TOLERANCE 0.0015 m, MAX_TRIALS 8", {"HEAD_TOLERANCE": "0"}),
    "converged-iteration": ("Iteration converged: HEAD_TOLERANCE 0.00001 m, MAX_TRIALS 20", {"HEAD_TOLERANCE": "0.00001", "MAX_TRIALS": "20"}),
    "normal-flow-froude": ("NORMAL_FLOW_LIMITED FROUDE", {"NORMAL_FLOW_LIMITED": "FROUDE"}),
    "normal-flow-slope": ("NORMAL_FLOW_LIMITED SLOPE", {"NORMAL_FLOW_LIMITED": "SLOPE"}),
    "damping-none": ("INERTIAL_DAMPING NONE", {"INERTIAL_DAMPING": "NONE"}),
    "damping-full": ("INERTIAL_DAMPING FULL", {"INERTIAL_DAMPING": "FULL"}),
    "variable-step-0.5": ("VARIABLE_STEP 0.5 (smaller time steps)", {"VARIABLE_STEP": "0.5"}),
}


def _runner():
    spec = importlib.util.spec_from_file_location("run_swmm_track_a", REPO / "scripts" / "run_swmm_track_a.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    import difference  # site/difference.py: the same percent difference the site shows
    from benchmark1d2d import keep

    keep.inputs = lambda *a, **k: None  # the published model packages stay as they are
    run = _runner()
    cases = sys.argv[1:] or list(run.CASES)
    results: dict[str, dict[str, dict]] = {c: {} for c in cases}
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
        target = OUT.with_suffix(".partial.json") if partial else OUT
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"model": "swmm524", "engine": "EPA SWMM 5.2.4 (swmm-toolkit 0.17.0)", "date": date.today().isoformat(),
                                      "script": "scripts/sensitivity_swmm.py", "variants": {k: v[0] for k, v in VARIANTS.items()},
                                      "tests": env}, indent=1) + "\n", encoding="utf-8")
        return env

    with tempfile.TemporaryDirectory() as tdn:
        run.OUT = Path(tdn)
        for name, (_, opts) in VARIANTS.items():
            key = f"swmm524~{name}"
            run.ENGINES[key] = dict(label=f"EPA SWMM 5.2.4 ({name})", routing="DYNWAVE", base="swmm524", options=opts)
            sys.argv = ["run_swmm_track_a.py", *cases, "--engines", key]
            run.main()
            for c in cases:
                cards = list((Path(tdn) / key).glob(f"{c}_*.scorecard.json"))
                if not cards:
                    results[c][name] = {"completed": False}
                    continue
                card = json.loads(cards[0].read_text(encoding="utf-8"))
                rep = ((card.get("run") or {}).get("engine") or {})
                conv = card.get("convergence_result") or {}
                results[c][name] = {"completed": True, "percent_difference": difference.result(card),
                                    "observed_order": conv.get("observed_order"),
                                    "engine_flagged": bool(rep.get("flagged")),
                                    "steps_not_converging_pct": rep.get("steps_not_converging_pct")}
            write(partial=True)  # an interrupted sweep keeps every finished variant
    env = write(partial=False)
    OUT.with_suffix(".partial.json").unlink(missing_ok=True)
    for c, e in env.items():
        print(f"{c}: {e['low']:.3g} % ({e['low_variant']}) to {e['high']:.3g} % ({e['high_variant']}); published {e['published']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
