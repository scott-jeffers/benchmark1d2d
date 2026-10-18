"""The leaderboard page, laid out the way current AI benchmark sites present results.

LMArena, Artificial Analysis, SWE-bench and LiveBench share a pattern: the
leaderboard is the page; one headline score per model with its uncertainty;
the rank follows that uncertainty, not the third decimal; category columns
beside the headline; a chart of the headline score; accuracy against cost or
speed; separate boards per category; filters; the date of the last update and
the data to download. This page does the same for water models (method:
docs/methodology/ranking.md):

* the headline is the **OpenHydro rating**: a Bradley–Terry fit of every
  head-to-head result on the tests two models share (LMArena's method), on the
  Elo scale, with a 95 % bootstrap interval over the tests;
* the category columns are the median percent difference from the right
  answer in each test group;
* everything is recomputed in the browser (``static/rankings.js``, the same
  arithmetic as ``site/ranking.py``) when the board or the model kinds change.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from html import escape as esc

import ranking

# Submitted results are never on the ranked board until a second party reproduces them (review F4).
KINDS = [("production", "Production software"), ("research", "Research codes"),
         ("suite", "Worked examples"), ("compat", "Previous releases")]
DEFAULT_KINDS = ("production", "research")


def data(manifests: list[dict], runs: dict, solver: dict, story, sid_of, machine_summary, meta=None) -> dict:
    tests, results, keys = [], [], set()
    for m in sorted(manifests, key=lambda m: m["test_id"]):
        by = runs.get(m["test_id"]) or {}
        if not by:
            continue
        sid = sid_of(m["test_id"])
        tests.append({"sid": sid, "name": story(m)["name"], "group": ranking.group_of(m["test_id"])})
        for k, c in sorted(by.items()):
            sc = ranking.score(c)
            run = c.get("run") or {}
            results.append([sid, k, None if sc is None else (sc if sc < 1e12 else 1e12), run.get("wall_seconds"),
                            machine_summary(run.get("machine")) if run.get("machine") else None, ranking.flagged(c)])
            keys.add(k)
    models = {k: {"name": solver[k]["name"], "sub": solver[k]["sub"], "kind": solver[k]["kind"], "color": solver[k]["color"],
                  **((meta or (lambda _k: {}))(k))} for k in keys if k in solver}
    return {"models": models, "tests": tests, "results": results, "groups": ranking.GROUPS, "updated": date.today().isoformat(),
            "rules": {"tie_rel": ranking.TIE_REL, "tie_floor": ranking.TIE_FLOOR, "min_tests": ranking.MIN_TESTS,
                      "boot": ranking.BOOT, "seed": ranking.BOOT_SEED, "prior": ranking.PRIOR,
                      "rated_groups": list(ranking.RATED_GROUPS), "noise": dict(ranking.NOISE_FLOOR),
                      "bands": [[hi if hi != float("inf") else 1e300, k, t] for hi, k, t in ranking.BANDS]}}


def board(runs: dict, solver: dict, kinds=DEFAULT_KINDS, group: str | None = None) -> list[dict]:
    """The default board, computed at build time (for the home page, the page's first paint and the downloads)."""
    return ranking.rating_board(runs, keep=lambda k: k in solver and solver[k]["kind"] in kinds, group=group)


def exports(updated: str, rows: list[dict], solver: dict, meta) -> tuple[str, str]:
    """leaderboard.json and leaderboard.csv: the default overall board."""
    out = []
    for r in rows:
        m = solver[r["key"]]
        out.append({"rank": r["rank"] if r["ranked"] else None, "model": m["name"], "variant": m["sub"], "key": r["key"],
                    "organisation": meta(r["key"])["org"], "licence": meta(r["key"])["licence"],
                    "rating": round(r["rating"], 1) if r["ranked"] else None, "ci95_low": round(r["lo"], 1) if r["ranked"] else None,
                    "ci95_high": round(r["hi"], 1) if r["ranked"] else None,
                    "not_ranked_because": None if r["ranked"] else ("no test shared with the rated models" if not r["connected"] else f"fewer than {ranking.MIN_TESTS} tests"),
                    "tests": r["tests"], "median_percent_difference": r["median_score"],
                    **{f"median_percent_difference_{g}": r["groups"].get(g) for g, _ in ranking.GROUPS},
                    "median_run_time_s": r["median_time"]})
    js = json.dumps({"updated": updated, "method": "docs/methodology/ranking.md", "board": out}, indent=1)
    buf = io.StringIO()
    if out:
        w = csv.DictWriter(buf, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    return js, buf.getvalue()


def board_table_html(rows: list[dict], solver: dict, meta, groups_present: list[tuple[str, str]], up: str = "") -> str:
    """The leaderboard table, server-rendered (the script redraws it on every filter change)."""
    head = ('<th scope="col" class="num"><button type="button" data-sort="rank">Rank</button></th>'
            '<th scope="col"><button type="button" data-sort="name">Model</button></th>'
            '<th scope="col" class="num"><button type="button" data-sort="rating">Rating</button></th>'
            '<th scope="col" class="num">95 % interval</th>'
            '<th scope="col" class="num"><button type="button" data-sort="tests">Tests</button></th>'
            + "".join(f'<th scope="col" class="num lb-g"><button type="button" data-sort="g:{g}">{esc(n)}</button></th>' for g, n in groups_present)
            + '<th scope="col" class="num"><button type="button" data-sort="time">Median run time</button></th><th scope="col">Licence</th>')
    body = []
    for r in rows:
        m, mm = solver[r["key"]], meta(r["key"])
        cells = "".join(
            f'<td class="num"><span class="lb-cell {ranking.klass(r["groups"][g])}">{esc(ranking.short(r["groups"][g]))}</span></td>'
            if g in r["groups"] else '<td class="num lb-none">–</td>' for g, _ in groups_present)
        cls = "" if r["ranked"] else ' class="lb-unranked"'
        rating = f'{r["rating"]:.0f}' if r["ranked"] else "–"
        why = "no test shared with the rated models" if not r["connected"] else f"fewer than {ranking.MIN_TESTS} tests"
        interval = f'{r["lo"]:.0f}–{r["hi"]:.0f}' if r["ranked"] else f'<span class="lb-why">{esc(why)}</span>'
        body.append(
            f'<tr{cls}><td class="num lb-rank">{(str(r["rank"]) + ("=" if r.get("tie") else "")) if r["ranked"] else "–"}</td>'
            f'<td class="lb-model"><a href="{up}solvers/{esc(r["key"])}.html"><span class="sw" style="background:{esc(m["color"])}"></span>'
            f'<b>{esc(m["name"])}</b> <span class="lb-sub">{esc(m["sub"])}</span></a><div class="lb-org">{esc(mm["org"])}</div></td>'
            f'<td class="num lb-rating">{rating}</td><td class="num lb-ci">{interval}</td>'
            f'<td class="num">{r["tests"]}</td>{cells}'
            f'<td class="num">{esc(ranking.fmt_time(r["median_time"]))}</td><td class="lb-lic">{esc(mm["licence"])}</td></tr>')
    return f'<table class="lb" id="lb-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def rating_chart_html(rows: list[dict], solver: dict, top: int | None = None, up: str = "", id_: str = "") -> str:
    """The rating as a dot on its 95 % interval, one row per model (LMArena's interval plot) (server-rendered; redrawn by the script)."""
    rows = [r for r in rows if r["ranked"]]
    if top:
        rows = rows[:top]
    if not rows:
        return f'<ol class="rc"{f" id={chr(34)}{id_}{chr(34)}" if id_ else ""}></ol>'
    base = (int(min(r["lo"] for r in rows) // 50) - 1) * 50
    span = max(max(r["hi"] for r in rows) - base, 1)
    out = []
    for r in rows:
        m = solver[r["key"]]
        w = 100 * (r["rating"] - base) / span
        a, b = 100 * (r["lo"] - base) / span, 100 * (r["hi"] - base) / span
        out.append(
            f'<li><a class="rc-name" href="{up}solvers/{esc(r["key"])}.html"><span class="rc-rank">{r["rank"]}{"=" if r.get("tie") else ""}</span>'
            f'<span class="sw" style="background:{esc(m["color"])}"></span><b>{esc(m["name"])}</b> <span class="lb-sub">{esc(m["sub"])}</span></a>'
            f'<span class="rc-track" title="{r["rating"]:.0f} (95 % interval {r["lo"]:.0f} to {r["hi"]:.0f})">'
            f'<i class="rc-ci" style="left:{a:.2f}%;width:{max(b - a, 0.6):.2f}%"></i><i class="rc-dot" style="left:{w:.2f}%"></i></span>'
            f'<span class="rc-val">{r["rating"]:.0f}</span></li>')
    return f'<ol class="rc"{f" id={chr(34)}{id_}{chr(34)}" if id_ else ""}>{"".join(out)}</ol>'


def group_strip(group_rows: dict, solver: dict) -> str:
    """The group boards first (review F2): the leaders of each test group, before the overall rating."""
    cards = []
    for g, n in ranking.GROUPS:
        rows = [r for r in (group_rows or {}).get(g, []) if r["ranked"]]
        if not rows:
            continue
        lis = "".join(
            f'<li><span class="tc-rk">{r["rank"]}{"=" if r.get("tie") else ""}</span><span class="sw" style="background:{esc(solver[r["key"]]["color"])}"></span>'
            f'<span class="tc-nm">{esc(solver[r["key"]]["name"])} <span class="tc-sub">{esc(solver[r["key"]]["sub"])}</span></span>'
            f'<span class="lb-ci">{r["rating"]:.0f}</span></li>' for r in rows[:4])
        note = {"parity": "Different from the reference engine, not wrong: not in the physics rating.",
                "field": "Validation of a published model: not in the physics rating."}.get(g, "")
        cards.append(f'<button type="button" class="lb-gcard" data-g="{esc(g)}"><b>{esc(n)}</b>'
                     f'<ol class="tc-board">{lis}</ol>{f"<span class=lb-gnote>{esc(note)}</span>" if note else ""}</button>')
    return f'<div class="lb-groups">{"".join(cards)}</div>' if cards else ""


def page(layout, d: dict, rows: list[dict], solver: dict, meta, group_rows: dict | None = None) -> str:
    groups_present = [(g, n) for g, n in d["groups"] if any(t["group"] == g for t in d["tests"])]
    tabs = "".join(f'<button type="button" class="lb-tab" data-g="{esc(g)}" aria-pressed="false">{esc(n)}</button>' for g, n in groups_present)
    present = {m["kind"] for m in d["models"].values()}
    kchk = "".join(f'<label class="rk-kind"><input type="checkbox" value="{k}"{" checked" if k in DEFAULT_KINDS else ""}> {esc(n)}</label>'
                   for k, n in KINDS if k in present)
    upd = date.fromisoformat(d["updated"])
    body = f"""<div class="wrap">
<section class="lb-head">
  <div>
    <h1>Leaderboard</h1>
    <p class="lede">Water models ranked by how close they get to the right answer, on tests where the answer is known. Every model runs the same inputs, and the suite scores them all the same way.</p>
  </div>
  <dl class="lb-facts">
    <div><dt>Updated</dt><dd>{upd.day} {upd.strftime("%b %Y")}</dd></div>
    <div><dt>Models</dt><dd>{len(d["models"])}</dd></div>
    <div><dt>Tests</dt><dd>{len(d["tests"])}</dd></div>
    <div><dt>Results</dt><dd>{len(d["results"])}</dd></div>
  </dl>
</section>
<div class="lb-bar">
  <div class="lb-tabs" role="group" aria-label="Board"><button type="button" class="lb-tab" data-g="" aria-pressed="true">All physics groups</button>{tabs}</div>
  <div class="lb-tools">
    <div class="rk-kinds" role="group" aria-label="Kinds of model shown">{kchk}</div>
    <label class="lb-search"><span class="sr-only">Find a model</span><input type="search" id="lb-q" placeholder="Find a model" autocomplete="off"></label>
  </div>
</div>
<section class="lb-sec" aria-labelledby="gb-h">
  <div class="lb-sec-head"><h2 id="gb-h">By group</h2><p class="muted small">Each group is rated on its own tests. Select a group to open its board.</p></div>
  {group_strip(group_rows, solver)}
</section>
<section class="lb-sec" aria-labelledby="rc-h">
  <div class="lb-sec-head"><h2 id="rc-h">OpenHydro rating</h2><p class="muted small" id="rc-note">Higher is better. Each dot is a model's rating and the band its 95 % interval; models whose bands overlap share a rank.</p></div>
  {rating_chart_html(rows, solver, id_="rc")}
</section>
<section class="lb-sec" aria-labelledby="lb-h">
  <div class="lb-sec-head"><h2 id="lb-h">Full table</h2><p class="muted small" id="lb-note">Select a column heading to sort. Group columns are the median percent difference from the right answer on that group's tests.</p></div>
  <div class="table-scroll lb-scroll">{board_table_html(rows, solver, meta, groups_present)}</div>
  <p class="small lb-dl">Download this board as <a href="data/leaderboard.csv" download>CSV</a> or <a href="data/leaderboard.json" download>JSON</a>, or every signed result as <a href="data/scorecards/">score cards</a>.</p>
</section>
<section class="lb-sec lb-two">
  <div>
    <div class="lb-sec-head"><h2>Accuracy and run time</h2><p class="muted small">Rating against median run time on the finest grids (log scale). Top left is more accurate and faster. Times compare models on the same kind of machine only.</p></div>
    <div id="rk-speed"></div>
  </div>
  <div>
    <div class="lb-sec-head"><h2>How the rating works</h2></div>
    <ul class="lb-how">
      <li><b>Every test is a match.</b> On each test two models both ran, the one closer to the right answer wins; within 10 % of each other (or both under 0.01 %, or both inside the test's measured noise floor) is a draw. Nobody is compared on a test they did not run.</li>
      <li><b>Each test counts the same.</b> A test's matches share one unit of weight, whether 3 models ran it or 16; otherwise the most-run tests (the dam breaks) would decide the order.</li>
      <li><b>One rating from all the matches.</b> A Bradley–Terry fit, the method LMArena uses for chat models, on the Elo scale: 1000 is the average model, and 400 points more is ten times the odds of being closer on a test. Only models linked to each other through shared tests are rated together.</li>
      <li><b>Physics only.</b> The overall rating counts the Track A groups. Parity with a reference engine (Track B) can show a model is different, not wrong, and the Bellinge field test compares engines inside their own build-to-build noise, so both keep their own boards.</li>
      <li><b>Runs the engine flags are not ranked.</b> When an engine reports that its own run did not converge or lost mass (SWMM's report: over 10 % of steps unconverged or a 10 % continuity error), the result is shown with that report, not ranked.</li>
      <li><b>An interval, not a decimal.</b> The tests are redrawn with replacement {d["rules"]["boot"]} times and the rating refitted each time; the band covers 95 % of those fits. A model's rank is 1 + the number of models whose band lies wholly above its own.</li>
      <li><b>Percent difference underneath.</b> Each result is its percent difference from the right answer, the largest over the test's checks. The group columns and the grid below show it. <a href="how-it-works.html">Read the full method</a>.</li>
      <li><b>{d["rules"]["min_tests"]} tests to be ranked.</b> Models with fewer in the current board are listed without a rank.</li>
    </ul>
  </div>
</section>
<section class="lb-sec" aria-labelledby="pt-h">
  <div class="lb-sec-head"><h2 id="pt-h">Every result</h2><p class="muted small">Rows in rating order; each cell is the model's percent difference on that test. Select a cell to open the result.</p></div>
  <div class="rk-legend small" id="rk-legend"></div>
  <div class="table-scroll rk-portrait-wrap"><table class="rk-portrait" id="rk-portrait"></table></div>
</section>
</div>
<script type="application/json" id="rk-data">{json.dumps(d, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    return layout("Leaderboard", body, "rankings.html", scripts='<script src="static/rankings.js" defer></script>',
                  description="Water models ranked by how close they get to the right answer on every benchmark test: ratings with 95 % intervals, per-group results and run times.")
