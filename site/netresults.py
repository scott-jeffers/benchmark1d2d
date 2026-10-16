"""The network viewer: SWMM and EPANET tests drawn from their own .inp files, with each model's results over time.

Three parts:

* ``extract(m, parquet)`` cuts the per-element series a map needs from one
  model's results (node depth, head or pressure; link flow), at most
  ``MAX_STEPS`` times, to four significant figures. ``scripts/export_netresults.py``
  runs it after each solver (in CI and locally) and the result collector files
  the extracts under ``site/fixtures/netres/<test>/<model>.json``.
* ``write_data`` writes ``data/network/<test>.json`` at build time: where the
  model file is, what its variables mean, and every model's results, with the
  pinned reference engine (Track B), the exact answer (the drainage cases) or
  the measured levels (Bellinge) alongside.
* ``page`` is ``network.html``; ``static/netview.js`` parses the .inp in the
  browser and draws it.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from html import escape as esc
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
MAX_STEPS = 288
G = 9.80665

# the tests drawn on the map, and which kept model file stands for the test (the suite writes the .inp per engine)
NETWORK_TESTS = ("B-EXTRAN-001", "B-RTC-001", "B-EPANET-001", "A1D-001", "A1D-002", "A1D-003", "A1D-004", "A1D-005",
                 "A1P-001", "A1P-010", "A1F-100")
PRIMARY_INPUT = {"A1D": "swmm524", "A1P": "epanet22", "A1F-100": "swmm524"}
BELLINGE_EVENT = "2012-06-29"


def sid_of(tid: str) -> str:
    return tid.split("_")[0]


def kind_of(m: dict) -> str:
    sid = sid_of(m["test_id"])
    return "epanet" if sid.startswith(("A1P", "B-EPANET")) else "swmm"


def _sig(v) -> float | None:
    if v is None or not np.isfinite(v):
        return None
    return float(f"{float(v):.4g}")


def _flow_units(inp_text: str) -> str:
    m = re.search(r"(?im)^\s*FLOW_UNITS\s+(\S+)", inp_text)
    return m.group(1).upper() if m else "CMS"


def variables(m: dict, inp_text: str = "") -> dict:
    """What a node's and a link's number means for this test, with units."""
    sid = sid_of(m["test_id"])
    if sid == "A1F-100":
        return {"node": {"label": "Water level", "unit": "m above DVR90", "col": "wse"}, "link": None}
    if sid.startswith("B-EPANET"):
        return {"node": {"label": "Pressure", "unit": "m", "col": "p_m"}, "link": {"label": "Flow", "unit": "L/s", "col": "Q_lps"}}
    if sid.startswith("A1P"):
        return {"node": {"label": "Head", "unit": "m", "col": "h"}, "link": {"label": "Flow", "unit": "L/s", "col": "Q_lps"}}
    us = _flow_units(inp_text) in ("CFS", "GPM", "MGD")
    flow = {"CFS": "ft³/s", "GPM": "gpm", "MGD": "MGD", "CMS": "m³/s", "LPS": "L/s", "MLD": "ML/d"}.get(_flow_units(inp_text), "m³/s")
    return {"node": {"label": "Depth", "unit": "ft" if us else "m", "col": "h"}, "link": {"label": "Flow", "unit": flow, "col": "Q"}}


def _thin(t: np.ndarray) -> np.ndarray:
    idx = np.arange(len(t))
    if len(t) > MAX_STEPS:
        idx = np.unique(np.linspace(0, len(t) - 1, MAX_STEPS).round().astype(int))
    return idx


def _table(df, col: str) -> tuple[list, dict]:
    """{element: [values]} on a shared time axis from long-form rows."""
    import pandas as pd

    if col == "p_m":
        df = df.assign(p_m=df["p"] / (1000.0 * G))
    elif col == "Q_lps":
        df = df.assign(Q_lps=df["Q"] * 1000.0)
    elif col == "wse":
        df = df.assign(wse=df["h"] + df["z"])
    piv = df.pivot_table(index="t", columns="element_id", values=col, aggfunc="first").sort_index()
    t = piv.index.to_numpy(float)
    idx = _thin(t)
    piv = piv.iloc[idx]
    out = {str(e): [_sig(v) for v in piv[e].to_numpy(float)] for e in piv.columns if pd.notna(piv[e]).any()}
    return [float(v) for v in piv.index], out


def extract(m: dict, parquet: Path, series_json: Path | None = None, inp_text: str = "") -> dict | None:
    """One model's per-element results for the map."""
    import pandas as pd

    var = variables(m, inp_text)
    df = pd.read_parquet(parquet)
    if "element_id" not in df.columns:
        return None
    df["element_id"] = df["element_id"].astype(str)
    sid = sid_of(m["test_id"])
    if sid == "A1F-100":  # one storm, the model's own (2012-06-29), in hours from its start
        from datetime import datetime

        ev = next(e for e in m["simulation"]["events"] if e["id"] == BELLINGE_EVENT)
        t0 = (datetime.fromisoformat(ev.get("score_from", ev["start"])) - datetime.fromisoformat(m["simulation"]["epoch"])).total_seconds()
        df = df[(df["t"] > t0) & (df["t"] <= t0 + 2 * 86400)].assign(t=lambda d: d["t"] - t0)
    nodes = df[df["element_type"] == "node"]
    links = df[df["element_type"] == "link"]
    rec: dict = {}
    if series_json is not None and series_json.is_file():  # every reporting step of a small drainage case
        s = json.loads(series_json.read_text(encoding="utf-8"))
        t = np.asarray(s["t"], float)
        idx = _thin(t)
        rec["t"] = [float(t[i]) for i in idx]
        rec["nodes"] = {k: [_sig(v[i]) for i in idx] for k, v in s.get("node_h", {}).items()}
        rec["links"] = {k: [_sig(v[i]) for i in idx] for k, v in s.get("link_q", {}).items()}
        return rec
    t_n, n_vals = _table(nodes, var["node"]["col"]) if len(nodes) else ([], {})
    t_l, l_vals = _table(links, var["link"]["col"]) if (len(links) and var["link"]) else ([], {})
    t = t_n or t_l
    if t_n and t_l and t_n != t_l:  # nodes and links on different steps: put links on the node steps
        l_vals = {k: [_sig(v) for v in np.interp(t_n, t_l, [np.nan if x is None else x for x in vals])] for k, vals in l_vals.items()}
    if not t:
        return None
    return {"t": t, "nodes": n_vals, "links": l_vals}


# ── build time ──────────────────────────────────────────────────────────────


def _inp_for(m: dict, dist: Path) -> dict | None:
    """The model file to draw and offer for download, copied under data/network/."""
    sid = sid_of(m["test_id"])
    dest = dist / "data" / "network" / sid
    case = Path(m["_case_dir"])
    for e in m.get("inputs", []):
        if str(e.get("path", "")).endswith(".inp") and (case / e["path"]).is_file():
            src = case / e["path"]
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / src.name)
            return {"url": f"data/network/{sid}/{src.name}", "name": src.name, "bytes": src.stat().st_size,
                    "source": "the test's own model file", "text": src.read_text(encoding="latin-1")}
    key = PRIMARY_INPUT.get(sid) or PRIMARY_INPUT.get(sid[:3])
    zp = SITE / "fixtures" / "inputs" / sid / f"{key}.zip"
    if not key or not zp.is_file():
        return None
    with zipfile.ZipFile(zp) as z:
        names = sorted(n for n in z.namelist() if n.lower().endswith(".inp"))
        if not names:
            return None
        pick = next((n for n in names if BELLINGE_EVENT in n), names[0])
        data = z.read(pick)
    name = Path(pick).name if sid != "A1F-100" else "BellingeSWMM_v021_nopervious_2012-06-29.inp"
    if name in ("m.inp", "model.inp"):
        name = f"{sid}.inp"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / name).write_bytes(data)
    return {"url": f"data/network/{sid}/{name}", "name": name, "bytes": len(data), "source": f"as the suite wrote it for {key}",
            "text": data.decode("latin-1")}


def available(m: dict) -> bool:
    sid = sid_of(m["test_id"])
    if sid not in NETWORK_TESTS or m.get("status") == "draft":
        return False
    case = Path(m["_case_dir"])
    if any(str(e.get("path", "")).endswith(".inp") and (case / e["path"]).is_file() for e in m.get("inputs", [])):
        return True
    key = PRIMARY_INPUT.get(sid) or PRIMARY_INPUT.get(sid[:3])
    return bool(key) and (SITE / "fixtures" / "inputs" / sid / f"{key}.zip").is_file()


def _reference(m: dict, inp_text: str) -> dict | None:
    """The pinned engine (Track B), the exact answer (drainage cases) or the measurements (Bellinge), as a series."""
    sid = sid_of(m["test_id"])
    ref = m.get("reference") or {}
    case = Path(m["_case_dir"])
    if ref.get("kind") == "pinned_engine" and (case / ref.get("results_path", "")).is_file():
        r = extract(m, case / ref["results_path"], inp_text=inp_text)
        if r:
            r.update(key="reference", role="reference", label=f"{ref.get('engine', 'Reference')} {ref.get('version', '')} (reference)".strip())
        return r
    if sid.startswith("A1D"):
        from references import drainage

        fn = getattr(drainage, ref["generator"]["function"])
        t_end = float(m["simulation"]["t_end"])
        ex = fn(network_path=str(case / "inputs" / "network.json"), t=t_end)
        nodes = {str(e): [_sig(h)] for k, e, h in zip(ex["element_type"], ex["element_id"], ex["h"]) if k == "node" and np.isfinite(h)}
        links = {str(e): [_sig(q)] for k, e, q in zip(ex["element_type"], ex["element_id"], ex["Q"]) if k == "link" and np.isfinite(q)}
        return {"key": "exact", "role": "exact", "label": "Exact answer", "t": [t_end], "nodes": nodes, "links": links}
    if sid == "A1F-100":
        import pandas as pd
        from datetime import datetime

        meas = pd.read_parquet(case / ref["data_path"])
        meas = meas[meas["event"] == BELLINGE_EVENT]
        ev = next(e for e in m["simulation"]["events"] if e["id"] == BELLINGE_EVENT)
        t0 = (datetime.fromisoformat(ev["score_from"]) - datetime.fromisoformat(m["simulation"]["epoch"])).total_seconds()
        node_of = {p["id"]: p["element"] for p in m["simulation"]["probes"]}
        piv = meas.pivot_table(index="t", columns="gauge", values="wse").sort_index()
        idx = _thin(piv.index.to_numpy(float))
        piv = piv.iloc[idx]
        return {"key": "measured", "role": "measured", "label": "Measured", "t": [float(v - t0) for v in piv.index],
                "nodes": {node_of[g]: [_sig(v) for v in piv[g].to_numpy(float)] for g in piv.columns if g in node_of}, "links": {}}
    return None


def write_data(dist: Path, manifests: list[dict], runs: dict, solver: dict, order, verdict, story) -> list[dict]:
    out = dist / "data" / "network"
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for m in manifests:
        if not available(m):
            continue
        sid = sid_of(m["test_id"])
        inp = _inp_for(m, dist)
        if inp is None:
            continue
        text = inp.pop("text")
        results = []
        try:
            r = _reference(m, text)
        except Exception as exc:  # noqa: BLE001 - a missing reference must not break the build
            print(f"WARN network reference {sid}: {exc}")
            r = None
        if r:
            r["color"] = "var(--ink)"
            results.append(r)
        by = runs.get(m["test_id"], {})
        for k in order(set(by)):
            fx = SITE / "fixtures" / "netres" / sid / f"{k}.json"
            if not fx.is_file():
                continue
            rec = json.loads(fx.read_text(encoding="utf-8"))
            if rec.get("case_version") != m["case_version"]:
                continue
            s = solver[k]
            results.append(dict(key=k, role="model", label=f'{s["name"]} · {s["sub"]}' if s.get("sub") else s["name"], color=s["color"],
                                verdict=verdict(by[k]), t=rec["t"], nodes=rec["nodes"], links=rec["links"]))
        zips = [dict(key=k, label=(f'{solver[k]["name"]} · {solver[k]["sub"]}' if solver[k].get("sub") else solver[k]["name"]), url=f"data/inputs/{sid}/{k}.zip")
                for k in order(set(by)) if (SITE / "fixtures" / "inputs" / sid / f"{k}.zip").is_file()]
        st = story(m)
        doc = dict(sid=sid, name=st["name"], question=st["question"], kind=kind_of(m), inp=inp, zips=zips,
                   case_zip=f"data/cases/{sid}.zip", vars=variables(m, text), results=results,
                   t_unit="s", t0=(BELLINGE_EVENT + "T00:00:00") if sid == "A1F-100" else None, track=m["track"])
        (out / f"{sid}.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        index.append(dict(sid=sid, name=st["name"], kind=doc["kind"], n=len([r for r in results if r["role"] == "model"]),
                          inp=inp["url"], inp_name=inp["name"], bytes=inp["bytes"], source=inp["source"], thumb=thumbnail(text, doc["kind"])))
    return index


def thumbnail(text: str, kind: str, w: int = 320, h: int = 200) -> str:
    """A small SVG of the network from the file's own coordinates ('' when it has none)."""
    sec, rows = None, {}
    for line in text.splitlines():
        s = line.split(";", 1)[0].strip()
        if not s:
            continue
        if s.startswith("["):
            sec = s.strip("[]").upper()
            continue
        rows.setdefault(sec, []).append(s.split())
    xy = {r[0]: (float(r[1]), float(r[2])) for r in rows.get("COORDINATES", []) if len(r) >= 3}
    if len(xy) < 2:
        return ""
    verts: dict[str, list] = {}
    for r in rows.get("VERTICES", []):
        if len(r) >= 3:
            verts.setdefault(r[0], []).append((float(r[1]), float(r[2])))
    lsecs = ("CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS") if kind == "swmm" else ("PIPES", "PUMPS", "VALVES")
    links = [(r[1], r[2], verts.get(r[0], [])) for s_ in lsecs for r in rows.get(s_, []) if len(r) >= 3 and r[1] in xy and r[2] in xy]
    pts = list(xy.values()) + [p for _, _, v in links for p in v]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    pad = 10
    sc = min((w - 2 * pad) / max(x1 - x0, 1e-9), (h - 2 * pad) / max(y1 - y0, 1e-9))
    ox, oy = (w - sc * (x1 - x0)) / 2, (h - sc * (y1 - y0)) / 2
    f = lambda p: f"{ox + (p[0] - x0) * sc:.1f},{h - (oy + (p[1] - y0) * sc):.1f}"  # noqa: E731
    d = "".join("M" + " L".join(f(p) for p in [xy[a], *v, xy[b]]) for a, b, v in links)
    r = 1.6 if len(xy) > 200 else 2.6
    dots = "".join(f'<circle cx="{f(p).split(",")[0]}" cy="{f(p).split(",")[1]}" r="{r}"/>' for p in xy.values())
    return (f'<svg class="nv-thumb" viewBox="0 0 {w} {h}" role="img" aria-label="Map of the network">'
            f'<path d="{d}" class="nv-thumb-l"/><g class="nv-thumb-n">{dots}</g></svg>')


def page(layout, index: list[dict]) -> str:
    groups = [("Parity with the reference engines (Track B)", [t for t in index if t["sid"].startswith("B-")]),
              ("Drainage networks with exact answers", [t for t in index if t["sid"].startswith("A1D")]),
              ("Water-supply networks with exact answers", [t for t in index if t["sid"].startswith("A1P")]),
              ("A real sewer system", [t for t in index if t["sid"] == "A1F-100"])]
    opts = "".join(f'<optgroup label="{esc(g)}">' + "".join(
        f'<option value="{esc(t["sid"])}">{esc(t["sid"])} · {esc(t["name"])}</option>' for t in ts) + "</optgroup>" for g, ts in groups if ts)
    first = "B-RTC-001" if any(t["sid"] == "B-RTC-001" for t in index) else (index[0]["sid"] if index else "")
    body = f"""<div class="wrap nv-wrap">
<section class="page-head nv-head">
  <h1>Network viewer</h1>
  <p class="lede">Every SWMM and EPANET test, drawn from its own .inp file, with each engine's results on the map.</p>
</section>
<div class="nv-bar card">
  <label class="nv-field">Test <select id="nv-test">{opts}</select></label>
  <div class="nv-dl" id="nv-dl"></div>
</div>
<div class="nv-tabs" role="tablist">
  <button type="button" role="tab" id="nv-tab-map" aria-selected="true" aria-controls="nv-map-pane">Map</button>
  <button type="button" role="tab" id="nv-tab-file" aria-selected="false" aria-controls="nv-file-pane">Input file</button>
  <span class="nv-summary small muted" id="nv-summary"></span>
</div>
<section id="nv-map-pane" class="nv-pane" role="tabpanel" aria-labelledby="nv-tab-map">
  <div class="nv-controls">
    <label class="nv-field">Show <select id="nv-model"></select></label>
    <label class="nv-field">Colour <select id="nv-mode"><option value="value">by value</option><option value="diff">by difference from the reference</option></select></label>
    <div class="nv-time" id="nv-time" hidden>
      <button type="button" class="play" id="nv-play" aria-label="Play"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg></button>
      <input type="range" id="nv-scrub" min="0" max="0" value="0" aria-label="Time">
      <span id="nv-tlabel" class="small"></span>
    </div>
  </div>
  <div class="nv-main">
    <div class="nv-canvas-box">
      <canvas id="nv-canvas" aria-label="Map of the network" role="img"></canvas>
      <div class="nv-zoom">
        <button type="button" id="nv-zin" aria-label="Zoom in">+</button><button type="button" id="nv-zout" aria-label="Zoom out">−</button><button type="button" id="nv-fit" aria-label="Fit the network">⤢</button>
      </div>
      <div class="nv-tip small" id="nv-tip" hidden></div>
      <div class="nv-legend small" id="nv-legend"></div>
      <div class="nv-foot small muted" id="nv-foot"></div>
    </div>
    <aside class="nv-side card" id="nv-side" aria-live="polite">
      <p class="muted small">Click a manhole, junction or pipe on the map.</p>
    </aside>
  </div>
</section>
<section id="nv-file-pane" class="nv-pane" role="tabpanel" aria-labelledby="nv-tab-file" hidden>
  <div class="nv-file">
    <nav class="nv-sections small" id="nv-sections" aria-label="Sections of the input file"></nav>
    <div class="nv-src-box">
      <div class="nv-src-head"><input type="search" id="nv-find" placeholder="Find an element or text" aria-label="Find in the input file"><span class="small muted" id="nv-find-n"></span></div>
      <div class="nv-src" id="nv-src" tabindex="0" aria-label="The input file"></div>
    </div>
  </div>
</section>
</div>
<script type="application/json" id="nv-index">{json.dumps(dict(tests=index, first=first))}</script>"""
    return layout("Network viewer", body, "network.html", scripts='<script src="static/netview.js" defer></script>',
                  description="SWMM and EPANET benchmark networks drawn from their .inp files, with every engine's results on the map.")
