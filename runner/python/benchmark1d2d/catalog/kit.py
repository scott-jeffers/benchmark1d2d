"""Submission kit for one case: a results template and instructions.

``kit_files(manifest)`` returns ``{filename: text}`` for

* ``RESULTS_TEMPLATE.csv`` — the columns the case is scored on and example
  rows in the shape the scorer expects (grid cells, probes, network elements,
  coupling accounts), with the values left blank;
* ``HOW_TO_SUBMIT.md`` — what to run (end time, grids, boundary data), what
  to write, how to check the score locally and how to submit.

The site puts both into every case's download, next to the inputs.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

REPO_URL = "https://github.com/scott-jeffers/benchmark1d2d"
BASE = ["t", "x", "y", "h", "u", "v", "p"]


def _short(test_id: str) -> str:
    return test_id.split("_")[0]


def _levels(m: dict) -> list[float]:
    return sorted((m["simulation"].get("mesh_refinement") or {}).get("levels") or [], reverse=True)


def _network_elements(m: dict) -> list[tuple[str, str]]:
    """Element ids the reference is keyed by (analytic network cases)."""
    try:
        from benchmark1d2d.scoring.scorer import _load_generator

        fn, params = _load_generator(m)
        if fn is None:
            return []
        ref = fn(None, float(m["simulation"]["t_end"]), **params)
        if isinstance(ref, dict) and "element_id" in ref:
            types = ref.get("element_type") or [""] * len(ref["element_id"])
            return [(str(e), str(t)) for e, t in zip(ref["element_id"], types)]
    except Exception:  # noqa: BLE001 - the template is a convenience; never fail a build over it
        return []
    return []


def results_template(m: dict) -> tuple[list[str], list[list[Any]], str]:
    """(columns, example rows, one-line description of the rows)."""
    kind = (m.get("reference") or {}).get("kind")
    sim = m["simulation"]
    t_end = float(sim["t_end"])
    req = sim.get("required_outputs") or []
    probes = sim.get("probes") or []
    dim = m["physics"]["dimensionality"]
    opt = [c for c in ("Q", "c") if c in req]
    if kind == "exact_states":
        cols = BASE + ["Q", "z", "V", "element_id", "element_type"]
        rows = [[t_end, p["x"], p["y"], "", "", "", "", "", "", "", p["id"], "cell"] for p in probes]
        rows += [[t_end, "", "", "", "", "", "", "", "", "", "M1", "exchange"]]
        rows += [[t_end, "", "", "", "", "", "", "", "", "", a, "account"] for a in ("surface", "network", "inflow", "outflow")]
        return cols, rows, ("At every output time: one row per probe (depth h), one per manhole (exchange flow Q, "
                            "> 0 from the network onto the surface) and four volume accounts in V (m³): water stored "
                            "on the surface and in the network, and cumulative inflow to and outflow from the whole system.")
    if kind == "pinned_engine":
        cols = BASE + ["Q", "element_id", "element_type"]
        rows = [[0.0, "", "", "", "", "", "", "", "J1", "node"], [0.0, "", "", "", "", "", "", "", "C1", "link"]]
        return cols, rows, ("A time series for every node (depth h) and link (flow Q) of the input model, at its "
                            "reporting step, named as in the input file.")
    elems = _network_elements(m) if kind == "analytic" else []
    if elems:
        cols = BASE + ["Q", "element_id", "element_type"]
        rows = [[t_end, "", "", "", "", "", "", "", e, t] for e, t in elems]
        return cols, rows, ("One row per node (depth h above its invert, or head for pressurized networks) and per "
                            "link (flow Q, and depth h for open-channel conduits) at the end of the run.")
    if probes and kind == "measured" and all(p.get("element") for p in probes):
        cols = BASE + ["z", "element_id", "element_type"]
        rows = [[0.0, "", "", "", "", "", "", "", p["element"], "node"] for p in probes]
        ev = sim.get("events") or []
        return cols, rows, (f"A time series of depth h above the invert, with the invert elevation z, at each gauge node "
                            f"({', '.join(p['element'] for p in probes)}) every {sim.get('output_interval', '?')} s, named "
                            f"as in the input model; one run per storm ({len(ev)}), with t in seconds from "
                            f"{sim.get('epoch', 'the epoch')}, all in one file.")
    if probes and kind in ("intercomparison", "measured"):
        cols = BASE + ["z"]
        rows = [[0.0, p["x"], p.get("y", ""), "", "", "", "", ""] for p in probes]
        return cols, rows, (f"A time series at each probe ({', '.join(p['id'] for p in probes)}) every "
                            f"{sim.get('output_interval', '?')} s, with the bed elevation z of the cell holding it; "
                            "the whole wet field at the end if you can (for volume checks).")
    if dim == "2D":
        cols = BASE + ["z"]
        return cols, [[t_end, "", "", "", "", "", "", ""]], ("One row per cell centre at the end of the run (t = "
                                                             f"{t_end:g} s), with the cell's bed elevation z.")
    cols = BASE + opt
    return cols, [[t_end, "", "", "", "", "", "", *[""] * len(opt)]], (f"One row per cell centre along the channel at "
                                                                     f"the end of the run (t = {t_end:g} s); y, v and p empty.")


def _csv(cols: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def how_to_submit(m: dict, row_text: str) -> str:
    sid = _short(m["test_id"])
    sim = m["simulation"]
    levels = _levels(m)
    files = [f"{sid}_dx{lv:g}.csv" for lv in levels] if len(levels) > 1 else [f"{sid}.csv"]
    crit = "\n".join(f"| {c['id']} | {c['metric']} of {c.get('variable', '')} | {c['threshold']['op']} {c['threshold']['value']:g} "
                     f"{c['threshold'].get('units', '')} | {'yes' if c.get('gating') else 'no'} |" for c in m["scoring"]["criteria"])
    grids = (f"Run it on each of the {len(levels)} grids ({', '.join(f'{lv:g}' for lv in levels)} m), one results file "
             "per grid: the finest is scored and all of them are used to measure the order of convergence."
             if len(levels) > 1 else "Run it once.")
    sub = {
        "schema_version": "1.0.0",
        "solver": {"name": "Your solver", "version": "exact build", "options": "scheme, wet/dry depth, time-step control"},
        "submitted_by": "Your organisation",
        "date": "YYYY-MM-DD",
        "results_licence": "CC-BY-4.0",
        "cases": [{"test_id": sid, "case_version": m["case_version"], "results": files}],
    }
    return f"""# {sid} — {m['title']}: how to submit results

Case version **{m['case_version']}**. Everything the case needs is in this
folder: `manifest.json` (the case, its checks and limits), `README.md` (the
physics and the exact answer) and `inputs/`.

## 1. Run the case

{m['description']}

Run to t = {float(sim['t_end']):g} s. {grids}
Use the options you would recommend to a user for this kind of problem and
record them; do not tune them to the answer.

## 2. Write the results

{row_text}

Columns (SI units: m, s, m/s, m³/s, Pa): see `RESULTS_TEMPLATE.csv` for the
exact header and the rows expected. Parquet with the same columns is also
accepted. Name the files:

{chr(10).join(f'- `{f}`' for f in files)}

## 3. Check the score yourself

```bash
git clone {REPO_URL} && cd benchmark1d2d && pip install -e .
benchmark1d2d score {sid} --results {files[-1]}{' --refinement ' + ' '.join(files) if len(files) > 1 else ''} --solver-name "Your solver" --solver-version X
```

The checks and their limits:

| Check | Metric | Pass when | Decides pass/fail |
|---|---|---|---|
{crit}

## 4. Submit

The easiest way: drop the files on https://scott-jeffers.github.io/benchmark1d2d/score.html#{sid}
and press **Publish**; it makes the submission for you. Or add a folder `submissions/<your-solver>/` holding the results files and a
`submission.json` such as

```json
{json.dumps(sub, indent=2)}
```

and open a pull request on {REPO_URL}. The suite scores the files itself and
posts the scores on the pull request; once merged, the site lists them as
*submitted by* your organisation. Full instructions:
{REPO_URL}/blob/master/docs/submitting.md
"""


def kit_files(m: dict) -> dict[str, str]:
    cols, rows, text = results_template(m)
    return {"RESULTS_TEMPLATE.csv": _csv(cols, rows), "HOW_TO_SUBMIT.md": how_to_submit(m, text)}
