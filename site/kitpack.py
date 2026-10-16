"""The download for one test, made to be used without reading anything else.

``files(m, check_dir)`` returns ``{path in the zip: bytes}``:

* ``START_HERE.md``: what to build, in plain words (the test's ``SETUP.md``),
  then which sheets to fill in and how to send them;
* ``results/``: the sheets to fill in, one per grid size, with the positions,
  elements or times already in them, so only the values are left to type;
* ``model/``: ready-made model files where a test has a standard format: the
  EPA SWMM or EPANET input file, the bed and the starting depth as ASCII grids
  (``.asc``) or tables (``.csv``), and the surface of the coupled tests.

The test's own files (``manifest.json``, ``README.md``, ``inputs/``) are added
by the build next to these.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SITE_URL = "https://scott-jeffers.github.io/benchmark1d2d"


def sid_of(tid: str) -> str:
    return tid.split("_")[0]


def _levels(m: dict) -> list[float]:
    return sorted((m["simulation"].get("mesh_refinement") or {}).get("levels") or [], reverse=True)


def _g(v: float) -> str:
    return f"{v:g}"


def _csv(header: list[str], rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode()


def _asc(x0: float, y0: float, d: float, z: np.ndarray, nodata: float = -9999.0) -> bytes:
    """ESRI ASCII grid; ``z[j, i]`` with j = 0 the southern row (written north row first)."""
    ny, nx = z.shape
    head = f"ncols {nx}\nnrows {ny}\nxllcorner {x0:.6f}\nyllcorner {y0:.6f}\ncellsize {d:g}\nNODATA_value {nodata:g}\n"
    rows = "\n".join(" ".join(f"{v:.6f}" if np.isfinite(v) else f"{nodata:g}" for v in z[j]) for j in range(ny - 1, -1, -1))
    return (head + rows + "\n").encode()


def _centres(a: float, b: float, d: float) -> np.ndarray:
    n = int(round((b - a) / d))
    return a + d * (np.arange(n) + 0.5)


# ── model files ─────────────────────────────────────────────────────────────


def _bed_1d(fn, L: float, levels: list[float], fine_step: float) -> dict[str, bytes]:
    xs = np.round(np.arange(0.0, L + fine_step / 2, fine_step), 6)
    out = {"model/bed.csv": _csv(["x_m", "bed_level_m"], [[_g(x), f"{z:.6f}"] for x, z in zip(xs, fn(xs))])}
    for lv in levels:
        xc = _centres(0.0, L, lv)
        out[f"model/bed_dx{_g(lv)}.csv"] = _csv(["x_m (cell centre)", "bed_level_m"], [[_g(round(x, 6)), f"{z:.6f}"] for x, z in zip(xc, fn(xc))])
    return out


def _inp_from_zip(sid: str, key: str, name: str, pick: str | None = None) -> dict[str, bytes]:
    zp = SITE / "fixtures" / "inputs" / sid / f"{key}.zip"
    if not zp.is_file():
        return {}
    with zipfile.ZipFile(zp) as z:
        names = sorted(n for n in z.namelist() if n.lower().endswith(".inp"))
        if not names:
            return {}
        n = next((x for x in names if pick and pick in x), names[0])
        return {f"model/{name}": z.read(n)}


def model_files(m: dict) -> dict[str, bytes]:
    sid = sid_of(m["test_id"])
    case = Path(m["_case_dir"])
    levels = _levels(m)
    sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "runner" / "python")]
    try:
        if sid == "A1F-001":
            from references.macdonald import M1_PARAMS, bed_elevation

            fine = np.linspace(0.0, float(M1_PARAMS["L"]), 200001)
            zf = bed_elevation(fine)
            return _bed_1d(lambda x: np.interp(x, fine, zf), float(M1_PARAMS["L"]), levels, 1.0)
        if sid in ("A1F-040", "A1F-041", "A1F-042", "A1F-043"):
            from references.swashes import bed

            return _bed_1d(lambda x: bed(np.asarray(x, float)), 25.0, levels, 0.01)
        if sid == "A2A-001":
            from references.thacker import bed_elevation

            prm = json.loads((case / "inputs" / "params.json").read_text(encoding="utf-8"))
            h0, L, eta, dom = prm["h0"], prm["L"], prm["eta"], prm["domain"]
            out = {}
            for lv in levels:
                xc, yc = _centres(dom["xmin"], dom["xmax"], lv), _centres(dom["ymin"], dom["ymax"], lv)
                X, Y = np.meshgrid(xc, yc)
                z = bed_elevation(X, Y, h0, L)
                zs = eta * h0 / L**2 * (2 * X - eta)
                out[f"model/bed_dx{_g(lv)}.asc"] = _asc(dom["xmin"], dom["ymin"], lv, z)
                out[f"model/initial_depth_dx{_g(lv)}.asc"] = _asc(dom["xmin"], dom["ymin"], lv, np.maximum(zs - z, 0.0))
            return out
        if sid == "A2A-010":
            from references.macdonald_2d import bed_elevation

            prm = json.loads((case / "inputs" / "params.json").read_text(encoding="utf-8"))
            L, W, q, n = prm["L"], prm["W"], prm["q_m2s"], prm["n_manning"]
            fn = lambda x: bed_elevation(np.asarray(x, float), L=L, q=q, n_manning=n)  # noqa: E731
            out = _bed_1d(fn, L, [], 1.0)
            for lv in levels:
                xc, yc = _centres(0.0, L, lv), _centres(0.0, W, lv)
                out[f"model/bed_dx{_g(lv)}.asc"] = _asc(0.0, 0.0, lv, np.tile(fn(xc), (len(yc), 1)))
            return out
        if sid.startswith("A12"):
            from run_coupled_cases import bed_function
            from run_drainage_cases import write_inp
            import tempfile

            spec = json.loads((case / "inputs" / "coupling.json").read_text(encoding="utf-8"))
            s = spec["surface"]
            d = s["cell_size"]
            xc, yc = _centres(s["x0"], s["x1"], d), _centres(s["y0"], s["y1"], d)
            X, Y = np.meshgrid(xc, yc)
            out = {"model/surface.asc": _asc(s["x0"], s["y0"], d, bed_function(s["bed"])(X, Y))}
            net = json.loads(json.dumps(spec["network"]))
            net["duration_s"] = spec["duration_s"]
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "network.inp"
                write_inp(net, p, "DYNWAVE")
                out["model/network.inp"] = p.read_bytes()
            return out
        if sid.startswith("A1D"):
            from run_drainage_cases import write_inp
            import tempfile

            net = json.loads((case / "inputs" / "network.json").read_text(encoding="utf-8"))
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / f"{sid}.inp"
                write_inp(net, p, "DYNWAVE")
                return {f"model/{sid}.inp": p.read_bytes()}
        if sid.startswith("A1P-0") and sid in ("A1P-001", "A1P-010"):
            return _inp_from_zip(sid, "epanet22", f"{sid}.inp")
        if sid == "A1F-100":
            return _inp_from_zip(sid, "swmm524", "BellingeSWMM_v021_nopervious_2012-06-29.inp", "2012-06-29")
    except Exception as exc:  # noqa: BLE001 - a missing convenience file must not break the build
        print(f"WARN model files for {sid}: {exc}", file=sys.stderr)
    return {}


# ── results sheets ──────────────────────────────────────────────────────────

# the columns that matter for each kind of test (the rest of the contract is optional)
COLUMNS_1D = ["t", "x", "h", "u"]


def _trim(header: list[str], rows: list[list], keep: list[str]) -> tuple[list[str], list[list]]:
    idx = [header.index(c) for c in keep if c in header]
    return [header[i] for i in idx], [[r[i] for i in idx] for r in rows]


def _read_csv(text: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


def _inp_elements(text: str, kind: str) -> list[tuple[str, str]]:
    nodes = ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS") if kind == "swmm" else ("JUNCTIONS", "RESERVOIRS", "TANKS")
    links = ("CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS") if kind == "swmm" else ("PIPES", "PUMPS", "VALVES")
    sec, out = None, []
    for line in text.splitlines():
        s = line.split(";", 1)[0].strip()
        if not s:
            continue
        if s.startswith("["):
            sec = s.strip("[]").upper()
            continue
        if sec in nodes:
            out.append((s.split()[0], "node"))
        elif sec in links:
            out.append((s.split()[0], "link"))
    return out


def result_sheets(m: dict, check_dir: Path) -> tuple[dict[str, bytes], str]:
    """{results/<file>: csv}, and one sentence on what to fill in."""
    sid = sid_of(m["test_id"])
    levels = _levels(m)
    req = m["simulation"].get("required_outputs") or []
    t_end = float(m["simulation"]["t_end"])
    out: dict[str, bytes] = {}
    grid_tpl = {lv: check_dir / f"{sid}_dx{_g(lv)}_template.csv" for lv in levels}
    if levels and all(p.is_file() for p in grid_tpl.values()):
        two_d = m["physics"]["dimensionality"] == "2D"
        used = {c.get("variable", "h") for c in m["scoring"]["criteria"]} | {(m["scoring"].get("convergence") or {}).get("variable", "h")}
        used = {"h" if v in ("volume", "h+z") else v for v in used}
        keep = ["t", "x"] + (["y"] if two_d else []) + [c for c in ("h", "u", "v", "Q", "c", "p") if c in used]
        for lv, p in grid_tpl.items():
            header, rows = _read_csv(p.read_text(encoding="utf-8"))
            header, rows = _trim(header, rows, keep)
            out[f"results/{sid}_dx{_g(lv)}.csv"] = _csv(header, rows)
        what = (f"one sheet per grid size; each row is already a cell centre ({'x, y' if two_d else 'x'}) at the end of the run "
                f"(t = {t_end:g} s). Fill in " + ", ".join({"h": "the depth h (m)", "u": "the velocity u (m/s)", "v": "v (m/s)",
                                                             "Q": "the flow Q (m³/s)", "c": "the concentration c", "p": "the pressure p (Pa)"}[c]
                                                             for c in keep if c in ("h", "u", "v", "Q", "c", "p")) + ".")
        return out, what
    flat = check_dir / f"{sid}_template.csv"
    if flat.is_file():  # networks and coupled tests with an in-browser check
        out[f"results/{sid}.csv"] = flat.read_bytes()
        return out, "one sheet; each row is already an element (node or pipe) or a time. Fill in the empty values."
    if sid == "A1P-020":
        for lv in levels:
            xs = np.round(np.arange(0.0, 1000.0 + lv / 2, lv), 6)
            out[f"results/{sid}_dx{_g(lv)}.csv"] = _csv(["t", "x", "p", "u"], [[_g(t_end), _g(x), "", ""] for x in xs])
        return out, ("one sheet per reach length; each row is a computational point along the pipe at t = 0.5 s. Fill in the pressure "
                     "rise p (Pa, relative to the starting pressure) and the velocity u (m/s).")
    if sid == "A1P-001":
        xs = np.arange(0.0, 1000.0 + 1, 100.0)
        out[f"results/{sid}.csv"] = _csv(["t", "x", "h"], [["1", _g(x), ""] for x in xs])
        return out, "one sheet; each row is a point along the pipe (x = 0 is the reservoir). Fill in the head h (m)."
    if sid.startswith("B-"):
        inp = next(Path(m["_case_dir"]).glob("inputs/*.inp"))
        kind = "epanet" if sid.startswith("B-EPANET") else "swmm"
        els = _inp_elements(inp.read_text(encoding="latin-1"), kind)
        node_v, link_v = ("p", "Q") if kind == "epanet" else ("h", "Q")
        out[f"results/{sid}.csv"] = _csv(["t", "element_id", "element_type", node_v, link_v],
                                         [["", e, k, "", ""] for e, k in els])
        what = (f"one sheet listing every node and link of the model. Repeat the list for every reporting time, with t in seconds from the start, "
                + ("the pressure p (Pa) at nodes and the flow Q (m³/s) in links." if kind == "epanet" else
                   "the depth h at nodes and the flow Q in links, in the model's own units."))
        return out, what
    from benchmark1d2d.catalog.kit import results_template

    header, rows, text = results_template(m)
    out[f"results/{sid}.csv"] = _csv(header, rows)
    return out, text[0].lower() + text[1:] if text else "the sheet in results/."


# ── the page to start from ──────────────────────────────────────────────────


def start_here(m: dict, sheets: dict[str, bytes], what: str, model: dict[str, bytes]) -> str:
    sid = sid_of(m["test_id"])
    setup = Path(m["_case_dir"]) / "SETUP.md"
    head = setup.read_text(encoding="utf-8").strip() if setup.is_file() else f"# {m['title']}\n\n{m['description']}"
    sheet_list = "\n".join(f"- `{p}`" for p in sheets)
    model_list = "\n".join(f"- `{p}`" for p in model) if model else ""
    return f"""{head}

## Fill in your results

The sheets are in `results/`: {what}

{sheet_list}

Use metres, seconds and cubic metres per second unless the test says otherwise. Any column names are fine as long as
they say what they are ("Depth (m)" works as well as "h"); leave out what your software does not give.
{f'''
## Ready-made model files

{model_list}
''' if model_list else ''}
## Check your score and send it

1. Open {SITE_URL}/score.html#{sid}
2. Drop the filled sheets on the page. Your score appears at once (nothing is uploaded).
3. Press **Publish**, answer five short questions, and send the file it makes. We score it in the open and add it to the site.

Use the settings you would recommend to a user for this kind of problem; do not tune them to the answer.

## For the curious

`manifest.json` holds the checks and their limits, and `README.md` explains where the exact answer comes from.
Test {m['test_id']}, version {m['case_version']}.
"""


def fetched_inputs(m: dict) -> dict[str, bytes]:
    """Model files the catalog fetches rather than commits (the Track B .inp files), when the build has them."""
    case = Path(m["_case_dir"])
    out = {}
    for e in m.get("inputs", []):
        p = case / e["path"]
        if e.get("committed", True) is False and p.suffix.lower() == ".inp" and p.is_file() and p.stat().st_size < 20e6:
            out[e["path"]] = p.read_bytes()
    return out


def files(m: dict, check_dir: Path) -> dict[str, bytes]:
    model = {**model_files(m), **fetched_inputs(m)}
    sheets, what = result_sheets(m, check_dir)
    return {"START_HERE.md": start_here(m, sheets, what, model).encode(), **sheets, **model}
