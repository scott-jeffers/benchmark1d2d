"""The scoring-method review page: every result under the current and the proposed method.

The proposed method (``benchmark1d2d.scoring.method_v2``) is computed from the
same signed score cards; nothing on the rest of the site changes until
reviewers adopt it (``docs/methodology/scoring_v2.md``).
"""

from __future__ import annotations

from collections import Counter
from html import escape as esc

from benchmark1d2d.scoring.method_v2 import CONFIDENCE, FLOOR_FACTOR, assess

VERDICT_WORD = {"pass": "Passes", "fail": "Fails", "inconclusive": "Inconclusive", "at_floor": "At its precision",
                "n/a": "Not studied"}
NOTE_URL = "https://github.com/scott-jeffers/benchmark1d2d/blob/master/docs/methodology/scoring_v2.md"
X0, X1 = -1.0, 2.5  # order axis


def margin_text(m: float | None) -> str:
    if m is None:
        return ""
    if m < 0.01:
        return "uses under 1 % of it"
    if m < 1:
        return f"uses {round(m * 100):d} % of it"
    return f"{m:.1f}× the limit" if m < 10 else f"{m:,.0f}× the limit"


def rows(manifests: list[dict], runs: dict, solver: dict, order) -> list[dict]:
    out = []
    for m in manifests:
        if m["status"] == "draft" or m["test_id"] not in runs:
            continue
        sid = m["test_id"].split("_")[0]
        for k in order(set(runs[m["test_id"]])):
            c = runs[m["test_id"]][k]
            s = solver[k]
            name = s["name"] + (f" · {s['sub']}" if s.get("sub") else "")
            out.append(dict(sid=sid, title=m["title"], key=k, name=name, color=s["color"], a=assess(c)))
    return out


def _badge(v: str) -> str:
    cls = {"pass": "pass", "fail": "fail"}.get(v, "unsure")
    return f'<span class="badge sm {cls}">{esc(VERDICT_WORD.get(v, v))}</span>'


def _x(p: float, w: float = 400.0) -> float:
    return (min(max(p, X0), X1) - X0) / (X1 - X0) * w


def _axis(pmin: float) -> str:
    ticks = "".join(f'<line x1="{_x(t):.1f}" x2="{_x(t):.1f}" y1="12" y2="18" class="tk"/>'
                    f'<text x="{_x(t):.1f}" y="10" text-anchor="middle">{t:g}</text>' for t in (-1, 0, 0.5, 1, 1.5, 2, 2.5))
    return (f'<svg viewBox="0 0 400 20" class="ord-svg axis" aria-hidden="true">{ticks}'
            f'<line x1="{_x(pmin):.1f}" x2="{_x(pmin):.1f}" y1="12" y2="20" class="need"/></svg>')


def _whisker(cv: dict) -> str:
    v, p, ci, pmin = cv["verdict"], cv.get("order"), cv.get("ci"), cv.get("min", 0.8)
    cls = {"pass": "pass", "fail": "fail"}.get(v, "unsure")
    parts = [f'<rect x="{_x(pmin):.1f}" y="0" width="{400 - _x(pmin):.1f}" height="16" class="ok-zone"/>',
             f'<line x1="{_x(pmin):.1f}" x2="{_x(pmin):.1f}" y1="0" y2="16" class="need"/>']
    if ci:
        lo, hi = ci
        parts.append(f'<line x1="{_x(lo):.1f}" x2="{_x(hi):.1f}" y1="8" y2="8" class="ci {cls}"/>')
        for e, clipped in ((lo, lo < X0), (hi, hi > X1)):
            if not clipped:
                parts.append(f'<line x1="{_x(e):.1f}" x2="{_x(e):.1f}" y1="4" y2="12" class="ci {cls}"/>')
    if p is not None:
        parts.append(f'<circle cx="{_x(p):.1f}" cy="8" r="4" class="pt {cls}"/>')
    return f'<svg viewBox="0 0 400 16" class="ord-svg" aria-hidden="true">{"".join(parts)}</svg>'


def order_chart(rs: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for r in rs:
        if r["a"]["converges"]["verdict"] in ("n/a",):
            continue
        groups.setdefault(r["sid"], []).append(r)
    blocks = []
    for sid, g in groups.items():
        pmin = g[0]["a"]["converges"].get("min", 0.8)
        lines = []
        for r in g:
            cv = r["a"]["converges"]
            ci = cv.get("ci")
            val = (f'{cv["order"]:.2f}' if cv.get("order") is not None else "–") + (f' <span class="muted">[{ci[0]:.2f}, {ci[1]:.2f}]</span>' if ci else "")
            now = r["a"]["converges"].get("current_order")
            title = f'{r["name"]}: {VERDICT_WORD[cv["verdict"]]}. {cv.get("why", "")}. Current method: rate {now:.2f}.' if now is not None else r["name"]
            lines.append(f'<div class="ord-row" title="{esc(title)}"><div class="lab"><span class="sw" style="background:{r["color"]}"></span>{esc(r["name"])}</div>'
                         f'{_whisker(cv)}<div class="val">{val} {_badge(cv["verdict"])}</div></div>')
        blocks.append(f'<div class="ord-group"><div class="ord-head"><a href="tests/{esc(sid)}.html"><b>{esc(sid)}</b></a> '
                      f'<span class="muted">{esc(g[0]["title"])} · needed {pmin:g}</span></div>'
                      f'<div class="ord-row axis-row"><div class="lab"></div>{_axis(pmin)}<div class="val"></div></div>{"".join(lines)}</div>')
    return "".join(blocks)


def review_page(layout, manifests: list[dict], runs: dict, solver: dict, order) -> str:
    rs = rows(manifests, runs, solver, order)
    now = Counter(r["a"]["current"] for r in rs)
    new = Counter(r["a"]["overall"] for r in rs)
    trans = Counter((r["a"]["current"], r["a"]["overall"]) for r in rs)
    conv_only = [r for r in rs if r["a"]["current"] == "fail" and r["a"]["accurate"] == "pass"]
    near = sorted([r for r in rs if r["a"]["worst_margin"] is not None and 0.5 <= r["a"]["worst_margin"] <= 2.0],
                  key=lambda r: r["a"]["worst_margin"])
    changed = [r for r in rs if r["a"]["current"] != r["a"]["overall"]]
    n_ord = sum(1 for r in rs if r["a"]["converges"]["verdict"] not in ("n/a",))
    n_inc = sum(1 for r in rs if r["a"]["converges"]["verdict"] == "inconclusive")
    three = sum(1 for r in rs if r["a"]["converges"]["verdict"] == "inconclusive" and r["a"]["converges"].get("levels") == 3)

    def cell(a, b):
        n = trans.get((a, b), 0)
        return f'<td class="{"hl" if n and a != b else ""}">{n}</td>'

    matrix = (f'<div class="table-scroll tmx-wrap"><table class="data tmx"><thead><tr><th scope="col">Current method</th><th scope="col">→ Passes</th><th scope="col">→ Inconclusive</th><th scope="col">→ Fails</th></tr></thead><tbody>'
              f'<tr><th scope="row">Passes ({now["pass"]})</th>{cell("pass", "pass")}{cell("pass", "inconclusive")}{cell("pass", "fail")}</tr>'
              f'<tr><th scope="row">Fails ({now["fail"]})</th>{cell("fail", "pass")}{cell("fail", "inconclusive")}{cell("fail", "fail")}</tr></tbody></table></div>')

    def why(r):
        a = r["a"]
        if a["accurate"] == "fail":
            return "a check is over its limit"
        return a["converges"].get("why", "")

    ch_rows = "".join(f'<tr><th scope="row"><a href="tests/{esc(r["sid"])}.html#m-{esc(r["key"])}">{esc(r["sid"])}</a></th><td>{esc(r["name"])}</td>'
                      f'<td>{_badge(r["a"]["current"])}</td><td>{_badge(r["a"]["overall"])}</td><td class="small">{esc(why(r))}</td></tr>' for r in changed)
    near_rows = "".join(f'<tr><th scope="row"><a href="tests/{esc(r["sid"])}.html#m-{esc(r["key"])}">{esc(r["sid"])}</a></th><td>{esc(r["name"])}</td>'
                        f'<td>{r["a"]["worst_margin"]:.2f}×</td><td>{_badge(r["a"]["current"])}</td></tr>' for r in near)
    body = f"""<div class="wrap">
<section class="page-head">
  <div class="kicker">Proposal under review</div>
  <h1>How results are judged: a proposed change</h1>
  <p class="lede">Every result on this site gets one verdict: passes or fails. This page shows the same {len(rs)} results under a proposed method that gives each one two verdicts, says how close each check came to its limit, and allows a third answer, <em>inconclusive</em>, when the grids run cannot settle the question. <b>Nothing else on the site changes until reviewers adopt it.</b> <a href="{NOTE_URL}">Read the proposal</a>.</p>
</section>

<section class="section">
  <h2>What changes</h2>
  <div class="grid review-rules">
    <div class="card"><h3>Two verdicts, not one</h3><p><b>Accurate:</b> every check within its limit. <b>Converges:</b> the error falls as the grid gets finer, at the rate a correct method should. Today both are folded into one word, so a model 1 mm from the exact answer that converges slowly looks the same as one a metre out.</p></div>
    <div class="card"><h3>How close, not only which side</h3><p>Each check says how much of its limit it used: 4 % of it, or 1.4× over it. A near miss and a gross failure stop looking alike.</p></div>
    <div class="card"><h3>The rate with its uncertainty</h3><p>The convergence rate is fitted through every grid, with a {round(CONFIDENCE * 100)} % range. It passes only if the whole range clears the minimum and fails only if the whole range is below it; otherwise the result is inconclusive. Today the rate is the average of the two finest pairs of grids, and a single number decides.</p></div>
    <div class="card"><h3>A solver's own precision</h3><p>A program that stores levels to 0.3 mm cannot show its error falling below that. When the finest grid is within {FLOOR_FACTOR:g}× a solver's declared precision, the rate is reported but does not decide the verdict. Errors at rounding level on every grid still fail.</p></div>
  </div>
</section>

<section class="section">
  <h2>What would move</h2>
  <div class="cmp-summary">
    <div><b>{now['pass']}</b><span>pass today</span></div>
    <div><b>{new['pass']}</b><span>would pass</span></div>
    <div class="hl"><b>{new['inconclusive']}</b><span>would be inconclusive</span></div>
    <div><b>{new['fail']}</b><span>would fail ({now['fail']} today)</span></div>
    <div><b>{len(conv_only)}</b><span>fail today only on the convergence rate</span></div>
  </div>
  {matrix}
  <p class="muted">Of the {n_ord} results with a grid study, {n_inc} have a rate the grids cannot settle ({new["inconclusive"]} of them pass every accuracy check, so they come out inconclusive overall; the rest fail an accuracy check anyway). {three} of the {n_inc} are on tests run on three grids, where the fitted rate has one degree of freedom and its range is wide. The proposal therefore also asks for five grids per test.</p>
</section>

<section class="section">
  <h2>Convergence rate, with its range</h2>
  <p class="muted">Dot: the rate fitted through every grid. Bar: its {round(CONFIDENCE * 100)} % range. Shaded: at or above the minimum the test needs (line). Green: the whole range clears it; orange: the whole range is below it; grey: the range straddles it. Rates are clipped to the −1 to 2.5 window.</p>
  <div class="ord-chart">{order_chart(rs)}</div>
</section>

<section class="section">
  <h2>Results whose verdict would change ({len(changed)})</h2>
  <div class="table-scroll"><table class="data"><thead><tr><th scope="col">Test</th><th scope="col">Model</th><th scope="col">Today</th><th scope="col">Proposed</th><th scope="col">Why</th></tr></thead><tbody>{ch_rows}</tbody></table></div>
</section>

<section class="section">
  <h2>Close to the line ({len(near)})</h2>
  <p class="muted">Results whose worst gating check used between half and twice its limit: today these are a confident ✓ or ✗ either way.</p>
  <div class="table-scroll"><table class="data"><thead><tr><th scope="col">Test</th><th scope="col">Model</th><th scope="col">Worst check, share of its limit</th><th scope="col">Today</th></tr></thead><tbody>{near_rows}</tbody></table></div>
</section>
</div>"""
    return layout("Scoring review", body, "method.html", description="A proposed change to how benchmark results are judged, shown on every result.")
