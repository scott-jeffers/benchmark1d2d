#!/usr/bin/env python3
"""Write each audited model's settings-changed-from-default list from the model files it ran.

For every model whose engine reads SWMM or EPANET .inp files
(``benchmark1d2d.defaults.AUDITED``), this reads the model packages the
runners kept (``site/fixtures/inputs/<case>/<key>.zip``) and compares every
numerical option with the engine's own default, taken from its source at the
pinned tag. The result replaces the record's ``changed_from_default`` list in
``configurations/<key>.json`` and sets ``defaults_audit`` to ``automatic``.

A reason for each change comes from ``REASONS`` below: the suite's own
runners record why they set what they set. A change with no recorded reason
is still listed, marked "reason not recorded", so nothing is hidden.

Usage::

    python scripts/audit_configurations.py           # rewrite the records
    python scripts/audit_configurations.py --check   # exit 1 if a record is out of date (CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runner" / "python"))

from benchmark1d2d import defaults  # noqa: E402

INPUTS = REPO / "site" / "fixtures" / "inputs"
CONFIGS = REPO / "configurations"
NO_REASON = "Reason not recorded by the runner."

# Why the suite's runners set what they set (scripts/run_swmm_track_a.py, run_drainage_cases.py,
# run_openswmm_coupled.py, run_network_cases.py). Keyed by setting; applies to every model the suite runs.
REASONS = {
    "ROUTING_STEP": "The conduits are as short as the case's grid cells (down to 5 cm): the step is 1 s on the dam breaks and drainage cases and dx/20 on the bump channels, where SWMM's velocity-based variable step would otherwise stay far above the gravity-wave limit and a lake at rest sloshes (run_swmm_track_a.py).",
    "MINIMUM_STEP": "SWMM's default 0.5 s minimum step would exceed the Courant limit on the finer grids (run_swmm_track_a.py, run_drainage_cases.py).",
    "MIN_SURFAREA": "On 5 cm conduits SWMM's default minimum nodal area (1.17 m²) exceeds a node's own plan area and would add storage (bump channels only; run_swmm_track_a.py).",
    "HEAD_TOLERANCE": "The harness writes 0.0005 m on every case, tighter than SWMM's default (0.005 ft, 0.0015 m); the converged variants tighten it to 0.00001 m (review finding F1).",
    "MAX_TRIALS": "The converged variants allow 20 trials so the dynamic-wave iteration converges on short conduits (review finding F1).",
    "VARIABLE_STEP": "SWMM 5.1.15 defaults to a fixed step; the harness writes 5.2.4's default variable step (0.75) so both releases run the same model file.",
    "FLOW_ROUTING": "The routing method this configuration exists to test.",
    "ACCURACY": "Converged to 1e-6 so the solve is far tighter than the checks (run_network_cases.py).",
    "QUALITY TIMESTEP": "1 s quality step for the tracer test, so the transport is resolved on the case's time scale (run_network_cases.py).",
}


# Changes the case itself makes unavoidable: a T0 configuration may carry these and nothing else.
REQUIRED_BY_CASE = {"ROUTING_STEP", "MINIMUM_STEP", "MIN_SURFAREA", "QUALITY TIMESTEP"}
# Changes that pick which of the engine's methods the configuration evaluates (also allowed in T0).
SELECTS_METHOD = {"FLOW_ROUTING"}


def fmt(v) -> str:
    return f"{v:g}" if isinstance(v, float) else str(v)


def changes_for(key: str) -> list[dict]:
    found = defaults.audit_key(key, INPUTS)
    out = []
    for setting, e in sorted(found.items()):
        values = {defaults.parse_value(v): cases for v, cases in e["values"].items()}
        if len(values) == 1:
            (value, cases), = values.items()
        else:
            value = "; ".join(f"{fmt(v)} ({', '.join(sorted(c))})" for v, c in sorted(values.items(), key=lambda kv: str(kv[0])))
            cases = sorted({c for cs in values.values() for c in cs})
        out.append({"setting": setting, "value": value, "default": e["default"], "reason": REASONS.get(setting, NO_REASON),
                    "source": f"Default from {defaults.source_of(key)}", "cases": sorted(cases),
                    "required_by_case": setting in REQUIRED_BY_CASE, "selects_method": setting in SELECTS_METHOD})
    return out


def updated(rec: dict) -> dict:
    key = rec["key"]
    new = dict(rec)
    new["changed_from_default"] = changes_for(key)
    new["defaults_audit"] = "automatic"
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if a record differs from the audit")
    args = ap.parse_args()
    stale = []
    for key in defaults.AUDITED:
        path = CONFIGS / f"{key}.json"
        if not path.is_file() or not any(INPUTS.glob(f"*/{key}.zip")):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        new = updated(rec)
        text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
        if text != path.read_text(encoding="utf-8"):
            stale.append(key)
            if not args.check:
                path.write_text(text, encoding="utf-8")
        n = len(new["changed_from_default"])
        print(f"{key:24} {n} setting{'s' if n != 1 else ''} changed from default")
    if args.check and stale:
        print(f"out of date: {', '.join(stale)} (run scripts/audit_configurations.py)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
