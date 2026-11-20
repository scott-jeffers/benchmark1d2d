"""Engine defaults, from each engine's own source, and the audit of a written model against them.

Protocol 4.0 asks every configuration to list each setting that differs from
the engine's default (``configurations/<key>.json``). For the engines whose
models are plain text with an options section (EPA SWMM and EPANET .inp
files), that list is produced here automatically: the model files the runners
wrote are read and every numerical option is compared with the engine's
default.

The default tables are copied from the engines' source code at the pinned
release tags, and each table names its source:

* EPA SWMM 5.2.4: ``src/solver/project.c`` ``setDefaults()`` and
  ``src/solver/dynwave.c`` (``DEFAULT_HEADTOL``, ``DEFAULT_MAXTRIALS``,
  ``DEFAULT_SURFAREA``), tag ``v5.2.4``.
* EPA SWMM 5.1.15: the same functions, tag ``v5.1.15``.
* EPANET 2.2: ``src/input1.c`` ``setdefaults()`` and its ``#define``\\ s, tag ``v2.2``.

Options fall into two groups. *Case* options express what the test defines
(units, dates, reporting, how offsets are written, the friction law, which
processes are modelled). They are never counted as set-up changes. *Numerical*
options are the set-up choices a modeller makes, and those are the ones
compared with the defaults.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

FT = 0.3048

SWMM_SOURCES = {
    "5.2.4": "USEPA/Stormwater-Management-Model v5.2.4: src/solver/project.c setDefaults(), src/solver/dynwave.c",
    "5.1.15": "USEPA/Stormwater-Management-Model v5.1.15: src/solver/project.c setDefaults(), src/solver/dynwave.c",
}
EPANET_SOURCE = "OpenWaterAnalytics/EPANET v2.2: src/input1.c setdefaults() and its #defines"

# Numerical options and their defaults, as an .inp file would write them. Length-valued
# defaults are in feet in the source and are converted when the file uses SI flow units.
_SWMM_524 = {
    "FLOW_ROUTING": "DYNWAVE",
    "ROUTING_STEP": 20.0,
    "VARIABLE_STEP": 0.75,
    "MINIMUM_STEP": 0.5,
    "LENGTHENING_STEP": 0.0,
    "INERTIAL_DAMPING": "PARTIAL",
    "NORMAL_FLOW_LIMITED": "BOTH",
    "FORCE_MAIN_EQUATION": "H-W",
    "SURCHARGE_METHOD": "EXTRAN",
    "MAX_TRIALS": 8,
    "HEAD_TOLERANCE": ("ft", 0.005),
    "SYS_FLOW_TOL": 5.0,
    "LAT_FLOW_TOL": 5.0,
    "MIN_SURFAREA": ("ft2", 12.566),
    "MIN_SLOPE": 0.0,
    "ALLOW_PONDING": "NO",
    "SKIP_STEADY_STATE": "NO",
    "WET_STEP": 300.0,
    "DRY_STEP": 3600.0,
    "RULE_STEP": 0.0,
}
_SWMM_5115 = {**_SWMM_524, "FLOW_ROUTING": "KINWAVE", "VARIABLE_STEP": 0.0, "ROUTING_STEP": 300.0}
SWMM_DEFAULTS = {"5.2.4": _SWMM_524, "5.1.15": _SWMM_5115}
# Values the engine treats as "use the default" (0 for MAX_TRIALS, HEAD_TOLERANCE, MIN_SURFAREA).
_SWMM_ZERO_MEANS_DEFAULT = {"MAX_TRIALS", "HEAD_TOLERANCE", "MIN_SURFAREA"}
_SWMM_WORDS = {"INERTIAL_DAMPING": {"SOME": "PARTIAL"}, "FLOW_ROUTING": {"DW": "DYNWAVE", "KW": "KINWAVE"}}
_SWMM_TIMES = {"ROUTING_STEP", "WET_STEP", "DRY_STEP", "RULE_STEP", "LENGTHENING_STEP"}

EPANET_DEFAULTS = {
    "TRIALS": 200,
    "ACCURACY": 0.001,
    "UNBALANCED": "STOP",
    "CHECKFREQ": 2,
    "MAXCHECK": 10,
    "DAMPLIMIT": 0.0,
    "HEADERROR": 0.0,
    "FLOWCHANGE": 0.0,
    "HYDRAULIC TIMESTEP": 3600.0,
    "QUALITY TIMESTEP": 0.0,
    "RULE TIMESTEP": 0.0,
}
# EPANET matches option keywords on their leading characters (src/text.h): each key's words and the
# prefix EPANET compares for each word ("Headloss" is HEADL and is not HEADERROR).
_EPANET_KEYS = {"TRIALS": ["TRIAL"], "ACCURACY": ["ACCU"], "UNBALANCED": ["UNBA"], "CHECKFREQ": ["CHECKFREQ"],
                "MAXCHECK": ["MAXCHECK"], "DAMPLIMIT": ["DAMPLIMIT"], "HEADERROR": ["HEADERROR"], "FLOWCHANGE": ["FLOWCHANGE"],
                "HYDRAULIC TIMESTEP": ["HYDR", "TIME"], "QUALITY TIMESTEP": ["QUAL", "TIME"], "RULE TIMESTEP": ["RULE", "TIME"]}
_EPANET_TIMES = {"HYDRAULIC TIMESTEP", "QUALITY TIMESTEP", "RULE TIMESTEP"}


def _seconds(v: str) -> float:
    """SWMM/EPANET time: seconds, or [h]h:mm[:ss], optionally with a unit word."""
    v = v.strip().upper()
    parts = v.split()
    if len(parts) == 2 and parts[1] in ("SEC", "SECONDS", "MIN", "MINUTES", "HR", "HOURS", "HOUR"):
        return float(parts[0]) * {"S": 1, "M": 60, "H": 3600}[parts[1][0]]
    if ":" in v:
        bits = [float(b) for b in v.split(":")]
        while len(bits) < 3:
            bits.append(0.0)
        return bits[0] * 3600 + bits[1] * 60 + bits[2]
    return float(v)


def _section(text: str, name: str) -> list[list[str]]:
    rows, on = [], False
    for line in text.splitlines():
        s = line.split(";", 1)[0].strip()
        if not s:
            continue
        if s.startswith("["):
            on = s.upper().startswith(f"[{name}]")
            continue
        if on:
            rows.append(s.split())
    return rows


def _same(a, b, rel: float = 1e-9) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= rel * max(abs(float(a)), abs(float(b)), 1e-300)
    return str(a).upper() == str(b).upper()


def audit_swmm(text: str, version: str = "5.2.4") -> list[dict]:
    """Numerical options of one SWMM .inp that differ from the engine's defaults."""
    table = SWMM_DEFAULTS[version]
    opts = {r[0].upper(): " ".join(r[1:]) for r in _section(text, "OPTIONS") if len(r) >= 2}
    si = opts.get("FLOW_UNITS", "CFS").upper() in ("CMS", "LPS", "MLD")
    out = []
    for key, default in table.items():
        if isinstance(default, tuple):
            unit, val = default
            default = val * (FT if unit == "ft" else FT * FT) if si else val
            shown_default = round(default, 6)
        else:
            shown_default = default
        raw = opts.get(key)
        if raw is None:
            continue
        if isinstance(default, str):
            value = _SWMM_WORDS.get(key, {}).get(raw.upper(), raw.upper())
        else:
            try:
                value = _seconds(raw) if key in _SWMM_TIMES else float(raw)
            except ValueError:
                value = raw
            if key in _SWMM_ZERO_MEANS_DEFAULT and value == 0:
                continue
        if not _same(value, default, 2e-2 if isinstance(table[key], tuple) else 1e-9):
            out.append({"setting": key, "value": value if not isinstance(value, float) or not value.is_integer() else int(value),
                        "default": shown_default})
    return out


def audit_epanet(text: str) -> list[dict]:
    """Numerical options of one EPANET .inp that differ from EPANET 2.2's defaults."""
    found: dict[str, str] = {}
    for sec in ("OPTIONS", "TIMES"):
        for r in _section(text, sec):
            words = [w.upper() for w in r]
            for key, prefixes in _EPANET_KEYS.items():
                if len(words) > len(prefixes) and all(w.startswith(pre) for w, pre in zip(words, prefixes)):
                    found[key] = " ".join(r[len(prefixes):])
                    break
    out = []
    for key, raw in found.items():
        default = EPANET_DEFAULTS[key]
        if isinstance(default, str):
            value = raw.split()[0].upper()
        else:
            try:
                value = _seconds(raw) if key in _EPANET_TIMES else float(raw.split()[0])
            except ValueError:
                value = raw
        if not _same(value, default):
            out.append({"setting": key, "value": value if not isinstance(value, float) or not value.is_integer() else int(value),
                        "default": default})
    return out


# Which engines are audited, with which table. Engines that read the SWMM or
# EPANET data model but are not EPA's (OpenSWMM, Hydra) are compared with the
# EPA defaults of the version they claim to follow, and say so.
AUDITED = {
    "swmm524": ("swmm", "5.2.4"), "swmm524-defaults": ("swmm", "5.2.4"), "swmm524-converged": ("swmm", "5.2.4"), "swmm515": ("swmm", "5.1.15"),
    "openswmm-dw": ("swmm", "5.2.4"), "openswmm-dw-converged": ("swmm", "5.2.4"), "openswmm-fv": ("swmm", "5.2.4"),
    "openswmm-2d": ("swmm", "5.2.4"), "openswmm-2d-x": ("swmm", "5.2.4"), "hydra-uds": ("swmm", "5.2.4"),
    "epanet22": ("epanet", "2.2"), "wntr": ("epanet", "2.2"), "hydra-wds": ("epanet", "2.2"),
}


def source_of(key: str) -> str:
    kind, ver = AUDITED[key]
    return SWMM_SOURCES[ver] if kind == "swmm" else EPANET_SOURCE


def audit_package(zip_path: Path, key: str) -> list[dict]:
    """Deviations over every .inp in one model package (``site/fixtures/inputs/<case>/<key>.zip``)."""
    kind, ver = AUDITED[key]
    seen: dict[tuple, dict] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".inp"):
                continue
            text = io.TextIOWrapper(zf.open(name), encoding="utf-8", errors="replace").read()
            for d in (audit_swmm(text, ver) if kind == "swmm" else audit_epanet(text)):
                seen.setdefault((d["setting"], str(d["value"])), d)
    return sorted(seen.values(), key=lambda d: (d["setting"], str(d["value"])))


# Cases whose model file is itself the test's input (a published model run unchanged): its options are
# the case's, not a set-up choice.
MODEL_IS_INPUT = ("A1F-100", "B-")


def audit_key(key: str, inputs_dir: Path) -> dict:
    """{setting: {"default": d, "values": {value: [cases]}}} over every case's package for one model."""
    out: dict[str, dict] = {}
    for z in sorted(inputs_dir.glob(f"*/{key}.zip")):
        case = z.parent.name
        if case.startswith(MODEL_IS_INPUT):
            continue
        for d in audit_package(z, key):
            e = out.setdefault(d["setting"], {"default": d["default"], "values": {}})
            e["values"].setdefault(str(d["value"]), []).append(case)
    return out


_NUM = re.compile(r"^-?\d+(\.\d+)?([eE]-?\d+)?$")


def parse_value(v: str):
    return (int(v) if v.lstrip("-").isdigit() else float(v)) if _NUM.match(v) else v
