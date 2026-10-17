"""The Rankings page: a leaderboard, a models × tests portrait and accuracy against run time.

Everything is computed in the browser (``static/rankings.js``) from one data
block written here, so the filters (test group, model kind) re-rank on the
spot with the same rules as ``site/ranking.py``.
"""

from __future__ import annotations

import json
from html import escape as esc

import ranking


def data(manifests: list[dict], runs: dict, solver: dict, story, sid_of, machine_summary) -> dict:
    tests, results, keys = [], [], set()
    for m in manifests:
        by = runs.get(m["test_id"]) or {}
        if not by:
            continue
        sid = sid_of(m["test_id"])
        tests.append({"sid": sid, "name": story(m)["name"], "group": ranking.group_of(m["test_id"])})
        for k, c in by.items():
            sc = ranking.score(c)
            run = c.get("run") or {}
            results.append([sid, k, None if sc is None else (sc if sc < 1e12 else 1e12), run.get("wall_seconds"),
                            machine_summary(run.get("machine")) if run.get("machine") else None])
            keys.add(k)
    order = {g: i for i, (g, _) in enumerate(ranking.GROUPS)}
    tests.sort(key=lambda t: (order.get(t["group"], 99), t["sid"]))
    models = {k: {"name": solver[k]["name"], "sub": solver[k]["sub"], "kind": solver[k]["kind"], "color": solver[k]["color"]} for k in keys if k in solver}
    return {"models": models, "tests": tests, "results": results, "groups": ranking.GROUPS,
            "rules": {"tie_rel": ranking.TIE_REL, "tie_floor": ranking.TIE_FLOOR, "min_tests": ranking.MIN_TESTS}}


def page(layout, d: dict) -> str:
    groups = "".join(f'<button type="button" class="pill" data-g="{esc(g)}" aria-pressed="false">{esc(n)}</button>'
                     for g, n in d["groups"] if any(t["group"] == g for t in d["tests"]))
    kinds = [("production", "Production software"), ("research", "Research codes"), ("submitted", "Submitted"), ("suite", "Worked examples"), ("compat", "Previous releases")]
    present = {m["kind"] for m in d["models"].values()}
    kchk = "".join(f'<label class="rk-kind"><input type="checkbox" value="{k}"{" checked" if k in ("production", "research", "submitted") else ""}> {esc(n)}</label>'
                   for k, n in kinds if k in present)
    body = f"""<div class="wrap">
<section class="page-head nv-head">
  <h1>Rankings</h1>
  <p class="lede">How close each model gets to the right answer, test by test and overall. No pass or fail: every result is the share of the test's error allowance it uses, and lower is better.</p>
</section>
<div class="rk-controls card">
  <div class="filters" role="group" aria-label="Test group"><button type="button" class="pill" data-g="" aria-pressed="true">All tests</button>{groups}</div>
  <div class="rk-kinds" role="group" aria-label="Models shown">{kchk}</div>
</div>
<section class="section tight" id="rk-board-sec">
  <h2>Leaderboard</h2>
  <p class="muted small" id="rk-board-note"></p>
  <div class="table-scroll"><table class="data rk-board" id="rk-board"><thead><tr>
    <th scope="col" class="num">Rank</th><th scope="col">Model</th>
    <th scope="col">Head-to-head wins <span class="muted">(share of comparisons)</span></th>
    <th scope="col" class="num">Error vs the field <span class="muted">(× typical)</span></th>
    <th scope="col" class="num">Tests</th><th scope="col" class="num">Median allowance used</th><th scope="col" class="num">Median run time</th>
  </tr></thead><tbody></tbody></table></div>
</section>
<section class="section tight">
  <h2>Every result</h2>
  <p class="muted small">Rows in rank order; each cell is the share of that test's allowance the model uses. Click a cell to open the result.</p>
  <div class="rk-legend small" id="rk-legend"></div>
  <div class="table-scroll rk-portrait-wrap"><table class="rk-portrait" id="rk-portrait"></table></div>
</section>
<section class="section tight">
  <h2>Accuracy and run time</h2>
  <p class="muted small">One test at a time: allowance used against wall time on the finest grid. The best models sit bottom left. Times compare models run on the same kind of machine only; the machine is in each point's label.</p>
  <label class="nv-field rk-test-pick">Test <select id="rk-test"></select></label>
  <div id="rk-speed"></div>
</section>
<section class="section tight">
  <h2>How the ranking works</h2>
  <div class="grid">
    <div class="card"><h3>Allowance used</h3><p>Each check has a limit with a stated reason. A result's score is its largest error as a share of its limit, over the test's accuracy checks. Convergence on finer grids is reported on each test page beside it.</p></div>
    <div class="card"><h3>Head-to-head wins</h3><p>For every pair of models and every test both ran, the lower score wins; within 10 % of each other (or both under 1 % of the allowance) is a tie, worth half. A model's win rate is its share of those comparisons, so nobody is judged on tests they did not run. Models need {d["rules"]["min_tests"]} tests to be ranked.</p></div>
    <div class="card"><h3>Error vs the field</h3><p>On each test, a model's score divided by the median model's, then the geometric mean over its tests: 0.5 means half the typical error. Scores under 1 % count as 1 %, the solvers' own precision.</p></div>
  </div>
  <p class="small muted">Why no pass/fail: a result using 99 % of an allowance and one using 101 % are almost the same, but a verdict makes them opposites. Leading benchmarks (SPEC, MLPerf, HELM, the climate models' PCMDI metrics) report measured scores and rank them instead.</p>
</section>
</div>
<script type="application/json" id="rk-data">{json.dumps(d, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    return layout("Rankings", body, "rankings.html", scripts='<script src="static/rankings.js" defer></script>',
                  description="Water models ranked by how close they get to the right answer on every benchmark test, with run times.")
