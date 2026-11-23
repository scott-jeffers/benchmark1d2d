"""Proposed set-ups: someone who knows a solver well changes its settings, and the suite re-runs it.

A proposed set-up lives in ``setups/<slug>/setup.json`` (schema
``schemas/v1/setup.schema.json``): the model it starts from (``base``, one of
the suite's model keys), the settings to change, the tests to run, and who
proposed it. The workflow ``setups.yml`` runs the base model's own runner with
``BENCH_SETUP`` naming that file. Each runner calls :func:`apply` on the model
files it has just written, before the solver runs; :func:`apply` changes the
named settings in place and records what it changed. The scorer then calls
:func:`decorate`, which marks the score card with the set-up, so the result is
filed as a separate model ("<base> · set-up <title>") and shown beside the
suite's own result, never in place of it.

Only settings the solver reads from a plain-text input file can be changed:

* SWMM 5 family (EPA SWMM 5.2.4 and 5.1.15, OpenSWMM Engine v6): keywords in the ``[OPTIONS]`` section of the ``.inp``.
* openTELEMAC-2D: keywords of the steering file (``KEYWORD = value``).
* LISFLOOD-FP: keywords of the ``.par`` file (``keyword value``); a keyword alone is a switch.

Settings the test itself defines (geometry, boundaries, friction, the grid, the
end time) cannot be changed: :data:`PROTECTED` lists them per format, so a
set-up competes on solver settings, not on a different problem.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

# model key -> file format whose settings a proposed set-up may change
BASES = {
    "swmm524": "swmm", "swmm515": "swmm", "openswmm-dw": "swmm", "openswmm-fv": "swmm",
    "telemac": "telemac",
    "lisflood-fv1": "lisflood", "lisflood-dg2": "lisflood", "lisflood-acc": "lisflood",
    "hecras": "hecras", "hecras-em": "hecras",  # HEC-RAS 7.0.1 2D (SWE-ELM, SWE-EM): keys of the plan file
    "landlab": "kwargs",  # Landlab OverlandFlow: keyword arguments of the component (models built in Python)
    "openswmm-2d": "kwargs", "openswmm-2d-x": "kwargs",
    "hydronet-fvm": "kwargs",  # HydroNet's Roe finite-volume solver: arguments of run_fvm_rk2  # OpenSWMM v6 1D/2D: choices in how the model is written
}
# for models built in Python: which keyword arguments of the solver's own API a set-up may pass, with their type
KWARGS = {"landlab": {"alpha": float, "theta": float, "h_init": float, "steep_slopes": bool},
          # crest_at_vertex: the mesh vertex a manhole is coupled at is raised to the grate's crest
          "openswmm-2d": {"crest_at_vertex": bool}, "openswmm-2d-x": {"crest_at_vertex": bool},
          "hydronet-fvm": {"cfl": float, "h_dry": float}}
FILES = {"swmm": ("*.inp",), "telemac": ("*.cas",), "lisflood": ("*.par",), "hecras": ("*.p0[0-9]",)}
# settings that define the test rather than the solver
PROTECTED = {
    "swmm": {"FLOW_UNITS", "START_DATE", "START_TIME", "END_DATE", "END_TIME", "REPORT_START_DATE", "REPORT_START_TIME",
             "REPORT_STEP", "INFILTRATION", "FLOW_ROUTING"},
    "telemac": {"GEOMETRY FILE", "BOUNDARY CONDITIONS FILE", "RESULTS FILE", "DURATION", "NUMBER OF TIME STEPS",
                "FRICTION COEFFICIENT", "LAW OF BOTTOM FRICTION", "INITIAL CONDITIONS", "INITIAL DEPTH", "INITIAL ELEVATION",
                "PRESCRIBED FLOWRATES", "PRESCRIBED ELEVATIONS", "TITLE"},
    "lisflood": {"dirroot", "resroot", "demfile", "startfile", "bcifile", "bdyfile", "sim_time", "fpfric", "manningfile",
                 "dx", "nrows", "ncols", "saveint", "massint", "startelev", "solver_type", "stagefile", "voutput",
                 "output_precision", "fv1", "dg2", "acceleration"},  # the solver itself is the model, not a setting
    "hecras": {"Plan Title", "Program Version", "Short Identifier", "Simulation Date", "Geom File", "Flow File", "DSS File",
               "UNET D2 Name", "Write IC File", "Write IC File at Sim End", "Write IC File at Fixed DateTime", "IC Time",
               "Output Interval", "Mapping Interval", "Instantaneous Interval", "HDF Write Warmup", "HDF Write Time Slices",
               "HDF Additional Output Variable", "UNET D2 Equation", "Run HTab", "Run UNet", "Run Sediment", "Run PostProcess",
               "Run WQNet", "Run RASMapper", "UNET Gravity", "UNET D2 Coriolis"},  # the equation set is the model itself
    "telemac_also": {"EQUATIONS", "GEOMETRY FILE", "PREVIOUS COMPUTATION FILE", "VARIABLES FOR GRAPHIC PRINTOUTS",
                     "GRAPHIC PRINTOUT PERIOD", "LISTING PRINTOUT PERIOD", "INITIAL TIME SET TO ZERO"},
}
VALUE = re.compile(r"^[A-Za-z0-9_.+\-:/ ]{0,60}$")  # one simple value; no line breaks or section headers

APPLIED: dict[str, list[dict]] = {}  # test id -> the changes applied in this process
_SETUP: dict | None = None


def load(path: str | Path | None = None) -> dict | None:
    """The proposed set-up named by ``path`` or ``BENCH_SETUP``, validated; None when there is none."""
    global _SETUP
    path = path or os.environ.get("BENCH_SETUP")
    if not path:
        return None
    if _SETUP is not None and _SETUP.get("_path") == str(path):
        return _SETUP
    s = json.loads(Path(path).read_text(encoding="utf-8"))
    sweep = s.get("proposed_by") == "sensitivity sweep" and Path(path).parent.name.startswith("sens-")  # scripts/sensitivity.py
    problems = [] if sweep else check(s)
    if problems:
        raise ValueError(f"{path}: " + "; ".join(problems))
    s["_path"] = str(path)
    s["slug"] = s.get("slug") or Path(path).parent.name
    _SETUP = s
    return s


def check(s: dict) -> list[str]:
    """Problems with a proposed set-up, beyond the schema: a base the suite can re-run, settings it may change."""
    out = []
    try:
        import jsonschema

        schema = json.loads((Path(__file__).resolve().parents[3] / "schemas" / "v1" / "setup.schema.json").read_text(encoding="utf-8"))
        out += [f"{'/'.join(map(str, e.path)) or '(top)'}: {e.message}" for e in jsonschema.Draft202012Validator(schema).iter_errors(s)]
    except FileNotFoundError:
        pass
    fmt = BASES.get(s.get("base", ""))
    if fmt == "kwargs":
        allowed = KWARGS.get(s["base"], {})
        for k, v in (s.get("settings") or {}).items():
            if k not in allowed:
                out.append(f"{k}: {s['base']} set-ups may set {', '.join(sorted(allowed))}")
            else:
                try:
                    _cast(allowed[k], v)
                except ValueError:
                    out.append(f"{k}: give a {allowed[k].__name__}")
        return out
    if fmt is None:
        out.append(f"base {s.get('base')!r}: the suite can re-run a proposed set-up for {', '.join(sorted(BASES))}")
        return out
    protected = {x.lower() for x in PROTECTED[fmt]} | ({x.lower() for x in PROTECTED["telemac_also"]} if fmt == "telemac" else set())
    for k, v in (s.get("settings") or {}).items():
        if k.strip().lower() in protected:
            out.append(f"{k}: defined by the test, not a solver setting")
        if not VALUE.match(str(v)) or not re.match(r"^[A-Za-z][A-Za-z0-9_ ]{0,40}$", k):
            out.append(f"{k}: give the setting's name and one simple value")
    if s.get("tier") == "T1" and not s.get("guidance_source"):
        out.append("tier T1 needs guidance_source: where the developer publishes this guidance")
    return out


def _cast(kind, v):
    if kind is bool:
        if str(v).lower() in ("true", "yes", "on", "1"):
            return True
        if str(v).lower() in ("false", "no", "off", "0"):
            return False
        raise ValueError(v)
    return kind(v)


def kwargs(model_key: str, test_id: str) -> dict:
    """For a model built in Python: the keyword arguments a proposed set-up passes to the solver, recorded like file edits."""
    if not applies(model_key, test_id):
        return {}
    s = load()
    allowed = KWARGS[model_key]
    out = {k: _cast(allowed[k], v) for k, v in s["settings"].items()}
    sid = test_id.split("_")[0]
    seen = {c["setting"] for c in APPLIED.get(sid, [])}
    APPLIED.setdefault(sid, []).extend({"setting": k, "value": str(v), "was": None, "file": "(keyword argument)"} for k, v in out.items() if k not in seen)
    return out


def applies(model_key: str, test_id: str) -> bool:
    s = load()
    if not s or s["base"] != model_key:
        return False
    tests = s.get("tests") or "all"
    return tests == "all" or test_id.split("_")[0] in tests


def _swmm(text: str, settings: dict) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    changes = []
    start = next((i for i, ln in enumerate(lines) if ln.strip().upper() == "[OPTIONS]"), None)
    if start is None:
        lines = ["[OPTIONS]"] + [""] + lines
        start = 0
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    for k, v in settings.items():
        key = k.upper()
        hit = next((i for i in range(start + 1, end) if lines[i].split() and lines[i].split()[0].upper() == key), None)
        was = lines[hit].split(None, 1)[1].strip() if hit is not None and len(lines[hit].split(None, 1)) > 1 else None
        new = f"{key:<20} {v}"
        if hit is None:
            lines.insert(end, new)
            end += 1
        else:
            lines[hit] = new
        changes.append({"setting": key, "value": str(v), "was": was})
    return "\n".join(lines) + "\n", changes


def _telemac(text: str, settings: dict) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    changes = []
    for k, v in settings.items():
        key = k.upper().strip()
        pat = re.compile(rf"^\s*{re.escape(key)}\s*[=:]\s*(.*)$", re.I)
        hit = next((i for i, ln in enumerate(lines) if pat.match(ln)), None)
        was = pat.match(lines[hit]).group(1).strip() if hit is not None else None
        if hit is None:
            lines.append(f"{key} = {v}")
        else:
            lines[hit] = f"{key} = {v}"
        changes.append({"setting": key, "value": str(v), "was": was})
    return "\n".join(lines) + "\n", changes


def _lisflood(text: str, settings: dict) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    changes = []
    for k, v in settings.items():
        hit = next((i for i, ln in enumerate(lines) if ln.split() and ln.split()[0].lower() == k.lower()), None)
        was = (" ".join(lines[hit].split()[1:]) or "on") if hit is not None else None
        sv = str(v)
        off = sv.lower() in ("off", "false", "no")
        if off:
            if hit is not None:
                del lines[hit]
        elif hit is None:
            lines.append(k if sv.lower() in ("on", "true", "yes", "") else f"{k} {sv}")
        else:
            lines[hit] = k if sv.lower() in ("on", "true", "yes", "") else f"{k} {sv}"
        changes.append({"setting": k, "value": sv, "was": was})
    return "\n".join(lines) + "\n", changes


def _hecras(text: str, settings: dict) -> tuple[str, list[dict]]:
    """HEC-RAS plan files: ``Key=value`` lines; a key may appear more than once (the plan's and each 2D area's block)."""
    lines = text.splitlines()
    changes = []
    for k, v in settings.items():
        key = k.strip()
        hits = [i for i, ln in enumerate(lines) if ln.split("=", 1)[0].strip() == key]
        was = lines[hits[0]].split("=", 1)[1].strip() if hits else None
        if hits:
            for i in hits:
                lines[i] = f"{key}= {v} " if lines[i].split("=", 1)[1].startswith(" ") else f"{key}={v}"
        else:
            lines.append(f"{key}={v}")
        changes.append({"setting": key, "value": str(v), "was": was})
    return "\r\n".join(lines) + "\r\n", changes


EDIT = {"swmm": _swmm, "telemac": _telemac, "lisflood": _lisflood, "hecras": _hecras}


def apply(model_key: str, test_id: str, folder: str | Path) -> list[dict]:
    """Change the proposed settings in the model files just written in ``folder``. Does nothing without ``BENCH_SETUP``."""
    if not applies(model_key, test_id):
        return []
    s = load()
    fmt = BASES[model_key]
    folder = Path(folder)
    done: list[dict] = []
    for pattern in FILES[fmt]:
        for f in sorted(folder.glob(pattern)):
            text = f.read_text(encoding="latin-1")
            new, changes = EDIT[fmt](text, s["settings"])
            f.write_text(new, encoding="latin-1")
            done += [{**c, "file": f.name} for c in changes]
    if not done and s["settings"]:
        raise RuntimeError(f"set-up {s['slug']}: no {', '.join(FILES[fmt])} file in {folder} to change")
    APPLIED.setdefault(test_id.split("_")[0], [])
    seen = {(c["setting"], c["file"]) for c in APPLIED[test_id.split("_")[0]]}
    APPLIED[test_id.split("_")[0]] += [c for c in done if (c["setting"], c["file"]) not in seen]
    return done


def decorate(solver: dict | None, test_id: str) -> dict | None:
    """The solver block for a score card: marked with the proposed set-up when one was applied to this test."""
    sid = test_id.split("_")[0]
    s = _SETUP if _SETUP is not None else None
    if solver is None or s is None or sid not in APPLIED:
        return solver
    changes = []
    for c in APPLIED[sid]:
        if not any(x["setting"] == c["setting"] for x in changes):
            changes.append({"setting": c["setting"], "value": c["value"], "was": c.get("was"), "file": c["file"]})
    out = dict(solver)
    out["name"] = f"{solver['name']} · set-up “{s['title']}”"
    out["adapter"] = f"{solver.get('adapter', '')}; proposed set-up \u201c{s['title']}\u201d: " + ", ".join(f"{c['setting']} {c['value']}" for c in changes)
    out["setup"] = {k: v for k, v in {"slug": s["slug"], "title": s["title"], "proposed_by": s["proposed_by"],
                                     "github_user": s.get("github_user"), "tier": s.get("tier", "T2"),
                                     "guidance_source": s.get("guidance_source"), "changes": changes}.items() if v is not None}
    return out
