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


def _sha256(path: Path) -> str | None:
    import hashlib

    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _attr(v):
    if isinstance(v, bytes):
        return v.decode(errors="replace").strip("\x00 ").strip()
    try:
        import numpy as np

        if isinstance(v, np.ndarray):
            v = v.tolist()
            return [_attr(x) for x in v] if isinstance(v, list) else v
        if isinstance(v, np.generic):
            return v.item()
    except ImportError:
        pass
    return v


def hecras_report(plan_hdf: str | Path | None, ras_exe: str | Path | None = None) -> dict | None:
    """HEC-RAS's own record of a run (review F11): the program that wrote the plan HDF and its version
    string, when it ran and how long it took, how it finished, the volume-accounting error, and the
    executable's path and SHA-256 — enough to show two versions ran separately."""
    out: dict = {"engine_report": "hecras-hdf"}
    if ras_exe:
        out["executable"] = str(ras_exe)
        sha = _sha256(Path(ras_exe))
        if sha:
            out["executable_sha256"] = sha
    p = Path(plan_hdf) if plan_hdf else None
    if p is not None and p.is_file():
        try:
            import h5py

            with h5py.File(p, "r") as f:
                for k in ("File Type", "File Version"):
                    if k in f.attrs:
                        out[k.lower().replace(" ", "_")] = _attr(f.attrs[k])
                for grp in ("Results/Summary", "Results/Unsteady/Summary"):
                    if grp in f:
                        for k, v in f[grp].attrs.items():
                            if any(w in k for w in ("Computation Time", "Run Time Window", "Solution", "Time Stamp", "Version")):
                                out[k.lower().replace(" ", "_")] = _attr(v)
                for grp in ("Results/Unsteady/Summary/Volume Accounting", "Results/Unsteady/Summary/Volume Accounting/Volume Accounting 2D"):
                    if grp in f:
                        for k, v in f[grp].attrs.items():
                            if "Error" in k and "Percent" in k:
                                try:
                                    out.setdefault("volume_error_pct", float(_attr(v)))
                                except (TypeError, ValueError):
                                    pass
        except Exception as exc:  # noqa: BLE001 - a report is extra; never fail a run over it
            out["read_error"] = f"{type(exc).__name__}: {exc}"[:200]
    if len(out) <= 1:
        return None
    ve = out.get("volume_error_pct")
    if ve is not None and abs(ve) > MAX_CONTINUITY:
        out["flagged"], out["flag_reason"] = True, f"volume accounting error {ve:+g} %"
    else:
        out["flagged"] = False
    return out
