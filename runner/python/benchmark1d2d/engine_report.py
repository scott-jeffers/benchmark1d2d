"""What an engine says about its own run, read from its report file.

A SWMM-family engine (EPA SWMM 5.x, OpenSWMM, anything writing SWMM's .rpt)
reports how many routing steps did not converge and how far its flow-routing
and runoff mass balances failed to close. A score computed from a run whose
engine says it did not converge measures the run's settings, not the engine's
physics (review F1, Bob Dickinson, 17 Oct 2026), so every card carries these
numbers and the site does not rank a run its engine flags.

A run is **flagged** when its engine reports

* more than ``MAX_UNCONVERGED`` % of routing steps not converging, or
* a flow-routing continuity error larger than ``MAX_CONTINUITY`` % in size
  (the SWMM user's manual: errors above 10 % call the results into question).
"""

from __future__ import annotations

import re
from pathlib import Path

MAX_UNCONVERGED = 10.0   # % of routing steps
MAX_CONTINUITY = 10.0    # % flow-routing continuity error

_PATTERNS = {
    "steps_not_converging_pct": r"%\s*of\s*Steps\s*Not\s*Converging\s*[.:]*\s*(-?[0-9.]+)",
    "routing_continuity_pct": r"Flow\s*Routing\s*Continuity.*?Continuity\s*Error\s*\(%\)\s*[.:]*\s*(-?[0-9.]+)",
    "runoff_continuity_pct": r"Runoff\s*Quantity\s*Continuity.*?Continuity\s*Error\s*\(%\)\s*[.:]*\s*(-?[0-9.]+)",
    "average_iterations": r"Average\s*Iterations\s*per\s*Step\s*[.:]*\s*(-?[0-9.]+)",
}


def swmm_report(rpt: str | Path) -> dict | None:
    """The convergence and continuity lines of a SWMM .rpt, or None when there are none."""
    p = Path(rpt)
    if not p.is_file():
        return None
    text = p.read_text(errors="replace")
    out: dict = {"engine_report": "swmm-rpt"}
    for k, pat in _PATTERNS.items():
        m = re.search(pat, text, re.S | re.I)
        if m:
            try:
                out[k] = float(m.group(1))
            except ValueError:
                pass
    out["warnings"] = len(re.findall(r"^\s*WARNING", text, re.M))
    if len(out) <= 2 and not out["warnings"]:
        return None
    return judge(out)


def judge(rep: dict) -> dict:
    """Add ``flagged`` and the reason to an engine report."""
    why = []
    nc = rep.get("steps_not_converging_pct")
    ce = rep.get("routing_continuity_pct")
    if nc is not None and nc > MAX_UNCONVERGED:
        why.append(f"{nc:g} % of routing steps did not converge")
    if ce is not None and abs(ce) > MAX_CONTINUITY:
        why.append(f"flow-routing continuity error {ce:+g} %")
    rep["flagged"] = bool(why)
    if why:
        rep["flag_reason"] = "; ".join(why)
    return rep
