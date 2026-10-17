"""The 1D/2D viewer: watch a coupled sewer/surface model run.

The coupled runners write a replay of each run (``<test>.replay.json``: the
surface depth over time, every manhole's surface level, head and exchange,
the network's heads and flows, and the volume accounts; see
``scripts/run_coupled_cases.py``). The result collector files them under
``site/fixtures/replay/<test>/<model>.json``; ``write_data`` copies the ones
for the catalog's current case version to ``data/coupled/`` and ``page`` is
the viewer, drawn by ``static/coupled.js``.
"""

from __future__ import annotations

import json
import shutil
from html import escape as esc
from pathlib import Path

SITE = Path(__file__).resolve().parent
FIXTURES = SITE / "fixtures" / "replay"
LOCAL = SITE.parent / "out" / "coupled"  # a local run's replays, used when the fixtures have none for that test and model


def _replays() -> dict[tuple[str, str], Path]:
    found: dict[tuple[str, str], Path] = {}
    for p in sorted(FIXTURES.glob("*/*.json")):
        found[(p.parent.name, p.stem)] = p
    for p in sorted(LOCAL.glob("*/*.replay.json")):
        key = (p.name.split(".")[0], p.parent.name)
        found.setdefault(key, p)
    return found


def write_data(dist: Path, manifests: list[dict], runs: dict, solver: dict, verdict, story) -> list[dict]:
    by_sid = {m["test_id"].split("_")[0]: m for m in manifests}
    out = dist / "data" / "coupled"
    index: dict[str, dict] = {}
    for (sid, key), path in _replays().items():
        m = by_sid.get(sid)
        if m is None or m["status"] == "draft":
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if doc.get("case_version") != m["case_version"]:
            continue
        card = (runs.get(m["test_id"]) or {}).get(key)
        dest = out / sid / f"{key}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        st = story(m)
        t = index.setdefault(sid, dict(sid=sid, name=st["name"], question=st["question"], models=[]))
        sv = solver.get(key, {})
        t["models"].append(dict(key=key, label=f'{sv.get("name", key)} · {sv.get("sub", "")}'.rstrip(" ·"), color=sv.get("color", "var(--ink)"),
                                score=verdict(card) if card else None, url=f"data/coupled/{sid}/{key}.json"))
    return [index[k] for k in sorted(index)]


def page(layout, index: list[dict]) -> str:
    opts = "".join(f'<option value="{esc(t["sid"])}">{esc(t["sid"])} · {esc(t["name"])}</option>' for t in index)
    first = "A12-012" if any(t["sid"] == "A12-012" for t in index) else (index[0]["sid"] if index else "")
    body = f"""<div class="wrap">
<section class="page-head nv-head">
  <h1>1D/2D viewer</h1>
  <p class="lede">Watch a coupled model run: the pipe network underneath, the street surface on top, and the water moving between them at each manhole.</p>
</section>
<div class="vw-pick card cv-pick">
  <label>Test <select id="cv-test">{opts}</select></label>
  <div class="cv-models" id="cv-models" role="group" aria-label="Model"></div>
  <a id="cv-link" href="#" class="small">Open the test page →</a>
</div>
<p class="cv-story" id="cv-story" aria-live="polite"></p>
<div class="vw-player" id="cv-player">
  <div class="vw-time">
    <button type="button" class="vw-step" id="cv-back" aria-label="Previous frame"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M3 2h2.5v14H3zM16 2 7 9l9 7z"/></svg></button>
    <button type="button" class="play" id="cv-play" aria-label="Play"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg></button>
    <button type="button" class="vw-step" id="cv-fwd" aria-label="Next frame"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M12.5 2H15v14h-2.5zM2 2l9 7-9 7z"/></svg></button>
    <input type="range" id="cv-scrub" min="0" max="0" value="0" aria-label="Time">
    <span id="cv-tlabel" class="vw-tlabel"></span>
    <div class="vw-speed" role="group" aria-label="Speed"><button type="button" data-cvspeed="0.5" aria-pressed="false">½×</button><button type="button" data-cvspeed="1" aria-pressed="true">1×</button><button type="button" data-cvspeed="3" aria-pressed="false">3×</button></div>
  </div>
</div>
<div class="cv-grid">
  <figure class="cv-panel cv-surface">
    <figcaption><b>Surface</b> <span class="muted small">(2D, from above)</span><span class="cv-read" id="cv-read"></span></figcaption>
    <canvas id="cv-map" role="img" aria-label="Surface water depth with the manholes"></canvas>
    <div class="cv-leg small" id="cv-leg"></div>
  </figure>
  <figure class="cv-panel cv-profile">
    <figcaption><b>Pipe network</b> <span class="muted small">(1D, long section)</span></figcaption>
    <svg id="cv-prof" viewBox="0 0 640 340" role="img" aria-label="Long section of the pipes with the water level"></svg>
    <div class="cv-key small"><span><i class="k-pipe"></i>pipe</span><span><i class="k-water"></i>water in the pipe</span><span><i class="k-hgl"></i>head (pressure level)</span><span><i class="k-ground"></i>ground</span><span><i class="k-surf"></i>water on the street</span></div>
  </figure>
</div>
<div class="cv-charts">
  <figure class="cv-panel"><figcaption><b>Exchange at the manholes</b> <span class="muted small">up: pipe → street · down: street → pipe (m³/s)</span></figcaption><svg id="cv-q" viewBox="0 0 640 190" role="img" aria-label="Exchange flow over time"></svg></figure>
  <figure class="cv-panel"><figcaption><b>Levels at the manhole</b> <span class="muted small">head in the pipe, water on the street, rim (m)</span></figcaption><svg id="cv-lv" viewBox="0 0 640 190" role="img" aria-label="Levels over time"></svg></figure>
  <figure class="cv-panel"><figcaption><b>Where the water is</b> <span class="muted small">volume on the street, in the pipes, and gone out (m³)</span></figcaption><svg id="cv-vol" viewBox="0 0 640 190" role="img" aria-label="Volumes over time"></svg><p class="small muted cv-bal" id="cv-bal"></p></figure>
</div>
<p class="small muted">Click a chart to jump to that time. Point at the surface to read the depth there.</p>
</div>
<script type="application/json" id="cv-index">{json.dumps(dict(tests=index, first=first))}</script>"""
    return layout("1D/2D viewer", body, "coupled.html", scripts='<script src="static/coupled.js" defer></script>',
                  description="Watch a coupled sewer and surface model run: the street, the pipes and the exchange at each manhole.")
