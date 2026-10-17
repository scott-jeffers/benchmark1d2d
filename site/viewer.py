"""The results viewer: pick a test, see every model's result side by side.

``write_data`` writes ``data/viewer/<test>.json`` for each Track A test:
the depth maps (exact and each model, ``site/fields.py``), with frames over
time where they exist, and each model's grid-convergence errors and fitted
rate. ``viewer_page`` is the page; ``static/viewer.js`` draws it.
"""

from __future__ import annotations

import json
from html import escape as esc
from pathlib import Path

import numpy as np

EXACT_FRAMES = 24


def _union_grid(fs: list[dict]) -> dict | None:
    import fields

    if not fs:
        return None
    xs, ys = [], []
    for f in fs:
        xs += [f["x0"] + f["dx"] / 2, f["x0"] + f["dx"] * (f["nx"] - 0.5)]
        ys += [f["y0"] + f["dx"] / 2, f["y0"] + f["dx"] * (f["ny"] - 0.5)]
    return fields.grid_for(np.array(xs), np.array(ys))


def test_data(m: dict, by: dict, model_fields: dict, solver: dict, order, verdict, story) -> dict | None:
    import fields

    sid = m["test_id"].split("_")[0]
    st = story(m)
    models = []
    for k in order(set(by)):
        c = by[k]
        a = c.get("_judged") or {}
        conv = c.get("convergence_result") or {}
        cv = a.get("converges") or {}
        rec = dict(key=k, label=f'{solver[k]["name"]} · {solver[k]["sub"]}' if solver[k].get("sub") else solver[k]["name"],
                   color=solver[k]["color"], score=verdict(c), verified=bool(a.get("verified")))
        if conv.get("errors"):
            rec["conv"] = dict(errors=[abs(e) for e in conv["errors"]], spacings=conv["spacings"], order=cv.get("order"),
                               ci=cv.get("ci"), verdict=cv.get("verdict"), min=conv.get("min_observed_order"),
                               norm=conv.get("norm"), variable=conv.get("variable"))
        if k in model_fields:
            rec["field"] = model_fields[k]
        models.append(rec)
    exact = None
    if fields.is_2d(m):
        g = _union_grid([r["field"] for r in models if r.get("field")])
        if g is not None:
            t_end = float(m["simulation"]["t_end"])
            # an unsteady analytic test (the sloshing bowl) is animated over the run; a steady one is one frame
            times = list(np.linspace(0.0, t_end, EXACT_FRAMES)) if "thacker" in m["test_id"] else None
            try:
                exact = fields.exact_field(m, g, times)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN exact field {sid}: {exc}")
    if exact is not None:  # the exact depth on each model's own map grid, for the difference maps
        for r in models:
            f = r.get("field")
            if f:
                try:
                    f["exact_h"] = fields.exact_field(m, {k: f[k] for k in ("x0", "y0", "dx", "nx", "ny")})["h"]
                except Exception:  # noqa: BLE001
                    pass
    if not any(r.get("field") or r.get("conv") for r in models):
        return None
    return dict(sid=sid, name=st["name"], question=st["question"], exact=exact, models=models,
                two_d=fields.is_2d(m), t_end=float(m["simulation"]["t_end"]))


def write_data(dist: Path, manifests: list[dict], runs: dict, fields_by: dict, solver: dict, order, verdict, story) -> list[dict]:
    out = dist / "data" / "viewer"
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for m in manifests:
        if m["status"] == "draft" or m["track"] != "A" or m["test_id"] not in runs:
            continue
        d = test_data(m, runs[m["test_id"]], fields_by.get(m["test_id"].split("_")[0], {}), solver, order, verdict, story)
        if not d:
            continue
        (out / f"{d['sid']}.json").write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
        index.append(dict(sid=d["sid"], name=d["name"], maps=any(r.get("field") for r in d["models"]),
                          frames=bool((d.get("exact") or {}).get("frames")) or any((r.get("field") or {}).get("frames") for r in d["models"]),
                          conv=any(r.get("conv") for r in d["models"])))
    return index


def viewer_page(layout, index: list[dict]) -> str:
    opts = "".join(f'<option value="{esc(t["sid"])}">{esc(t["sid"])} · {esc(t["name"])}{" · maps" if t["maps"] else ""}{" · animated" if t["frames"] else ""}</option>'
                   for t in index)
    first = next((t["sid"] for t in index if t["frames"]), index[0]["sid"] if index else "")
    body = f"""<div class="wrap">
<section class="page-head nv-head">
  <h1>Results viewer</h1>
  <p class="lede">Every model's result on one test, side by side: depth maps over time, the difference from the exact answer, and how the error shrinks on finer grids.</p>
</section>
<div class="vw-pick card">
  <label>Test <select id="vw-test">{opts}</select></label>
  <a id="vw-link" href="#" class="small">Open the test page →</a>
</div>
<section class="section" id="vw-maps-sec" hidden>
  <div class="head-row"><h2 style="margin:0">Depth maps</h2>
    <div class="view-toggle" role="group" aria-label="Map mode"><button type="button" data-mode="depth" aria-pressed="true">Depth</button><button type="button" data-mode="diff" aria-pressed="false">Difference from exact</button></div>
  </div>
  <p class="muted small" id="vw-maps-note"></p>
  <div class="vw-player" id="vw-player">
    <div class="vw-time" id="vw-time" hidden>
      <button type="button" class="vw-step" id="vw-back" aria-label="Previous frame"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M3 2h2.5v14H3zM16 2 7 9l9 7z"/></svg></button>
      <button type="button" class="play" id="vw-play" aria-label="Play"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg></button>
      <button type="button" class="vw-step" id="vw-fwd" aria-label="Next frame"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M12.5 2H15v14h-2.5zM2 2l9 7-9 7z"/></svg></button>
      <input type="range" id="vw-scrub" min="0" max="0" value="0" aria-label="Time">
      <span id="vw-tlabel" class="vw-tlabel"></span>
      <div class="vw-speed" role="group" aria-label="Speed"><button type="button" data-speed="0.5" aria-pressed="false">½×</button><button type="button" data-speed="1" aria-pressed="true">1×</button><button type="button" data-speed="2" aria-pressed="false">2×</button><button type="button" data-speed="4" aria-pressed="false">4×</button></div>
    </div>
    <div class="vw-legend" id="vw-legend"></div>
  </div>
  <p class="vw-hint small muted" id="vw-hint">Point at any map to read every model's depth at that spot. Click a map to enlarge it.</p>
  <div class="vw-chips" id="vw-chips" role="group" aria-label="Models shown"></div>
  <p class="small muted vw-stale-note" id="vw-stale-note" hidden></p>
  <div class="vw-maps" id="vw-maps"></div>
</section>
<section class="section" id="vw-conv-sec" hidden>
  <h2>Error on finer grids</h2>
  <p class="muted small">Each model's error against the exact answer on every grid it ran (both axes logarithmic). A correct method's line falls at the test's expected rate; the dashed line shows the minimum rate, drawn through the best model's coarsest point. Point at a line or a row to pick it out; the chips show and hide models.</p>
  <div class="vw-chips" id="vw-chips2" role="group" aria-label="Models shown"></div>
  <svg id="vw-conv" class="chart" viewBox="0 0 1000 420" role="img" aria-label="Error against grid spacing for each model"></svg>
  <div class="table-scroll" style="margin-top:12px"><table class="data" id="vw-table"><thead><tr><th>Model</th><th class="num">Difference</th><th class="num">Rate</th><th>90 % range</th><th>Against the design order</th></tr></thead><tbody></tbody></table></div>
</section>
</div>
<script type="application/json" id="vw-index">{json.dumps(dict(tests=index, first=first))}</script>"""
    return layout("Results viewer", body, "viewer.html", scripts='<script src="static/viewer.js" defer></script>',
                  description="Compare every model's result on a benchmark test: depth maps, differences from the exact answer and grid convergence.")
