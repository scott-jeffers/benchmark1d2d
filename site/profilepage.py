"""Evidence profiles (protocol 4.0): one per model, capability by kind of evidence.

For each model, a grid: one row per capability group (benchmark1d2d.evidence
.CAPABILITIES), one column per kind of evidence (verification, validation,
comparison). Each cell lists the model's results on the tests in that group
and kind, each with its percent difference. Capabilities with no evidence are
named, because "not tested" is information too. Nothing is ranked, and no
number is combined across tests.

Also writes data/profiles.json and data/profiles.csv: one row per result.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date

from benchmark1d2d import evidence as ev

KIND_GROUPS = [("production", "Production software"), ("submitted", "Submitted results"), ("research", "Research codes"),
               ("suite", "Worked examples"), ("compat", "Previous releases and compatibility")]


def rows(manifests: list[dict], runs: dict, pages) -> list[dict]:
    """One row per (model, test) result, with its evidence kind and capabilities."""
    out = []
    for m in manifests:
        if m["status"] == "draft":
            continue
        kind = ev.evidence_of(m)
        for k, c in (runs.get(m["test_id"]) or {}).items():
            if k not in pages.SOLVER:
                continue
            sc = pages.measures.score(c)
            out.append({
                "model": k,
                "model_name": f'{pages.SOLVER[k]["name"]} · {pages.SOLVER[k]["sub"]}',
                "tier": pages.tier_of(k) or "",
                "test": pages.sid_of(m["test_id"]),
                "test_name": pages.story(m)["name"],
                "case_version": m["case_version"],
                "evidence": kind,
                "capabilities": ev.capabilities_of(m),
                "percent_difference": None if sc is None or sc != sc or sc == float("inf") else round(sc, 6),
                "engine_flag": pages.measures.flagged(c) or "",
                "label": pages.HOLD(k) or "",
            })
    return out


def _cell(results: list[dict], pages, depth: int, label: str = "") -> str:
    if not results:
        return f'<td class="pf-none" data-label="{pages.esc(label)}">—</td>'
    up = "../" * depth
    items = "".join(
        f'<li><a href="{up}tests/{r["test"]}.html#m-{r["model"]}">{pages.esc(r["test_name"])}</a> '
        f'<span class="score {pages.measures.klass(r["percent_difference"])}">{pages.esc(pages.measures.short(r["percent_difference"]))}</span>'
        + (f' <span class="muted small">{pages.esc(r["engine_flag"] or r["label"])}</span>' if (r["engine_flag"] or r["label"]) else "")
        + "</li>" for r in results)
    return f'<td data-label="{pages.esc(label)}"><ul class="pf-list">{items}</ul></td>'


CENSUS: dict[str, str] = {}  # model key -> one line on the real-world corpus census (set by page())


def census_line(census) -> dict[str, str]:
    """EPA SWMM 5.2.4's census over the HydroCouple corpus, as a robustness line for its profile (comparison evidence)."""
    if census is None or not len(census):
        return {}
    st = census["status"].value_counts().to_dict()
    n = len(census)
    ran = int(st.get("ran", 0))
    bad_c = int(((census["status"] == "ran") & (census["continuity_routing_pct"].abs() > 5)).sum()) if "continuity_routing_pct" in census else 0
    line = (f"Real-world models: of {n:,} SWMM models in the HydroCouple corpus, {ran:,} run cleanly, "
            f"{int(st.get('input_error', 0)):,} stop on input errors in the model files (older-version syntax, missing rainfall files: the corpus's issue, not the engine's), "
            f"{int(st.get('timeout', 0)):,} exceed the census time limit, and {int(st.get('engine_error', 0)) + int(st.get('harness_error', 0))} fail in the engine or harness. "
            f"{bad_c} of those that run report a flow-routing continuity error beyond ±5 %. Comparison evidence: robustness, not accuracy.")
    return {"swmm524": line}


def model_profile(key: str, all_rows: list[dict], pages, depth: int = 0) -> str:
    mine = [r for r in all_rows if r["model"] == key]
    s = pages.SOLVER[key]
    esc = pages.esc
    caps_with = [c for c in ev.CAPABILITIES if any(c in r["capabilities"] for r in mine)]
    caps_without = [c for c in ev.CAPABILITIES if c not in caps_with]
    body_rows = []
    for c in caps_with:
        cells = "".join(_cell([r for r in mine if c in r["capabilities"] and r["evidence"] == k], pages, depth, ev.EVIDENCE[k]["name"]) for k in ev.EVIDENCE)
        body_rows.append(f'<tr><th scope="row" title="{esc(ev.CAPABILITIES[c]["engineer"])}"><b>{esc(ev.CAPABILITIES[c]["name"])}</b></th>{cells}</tr>')
    head = "".join(f'<th>{esc(v["name"])}<div class="muted small">against {esc(v["short"])}</div></th>' for v in ev.EVIDENCE.values())
    up = "../" * depth
    none_line = (f'<p class="small">No evidence yet on: {esc(", ".join(ev.CAPABILITIES[c]["name"] for c in caps_without))}.</p>'
                 if caps_without else "")
    counts = {k: sum(1 for r in mine if r["evidence"] == k) for k in ev.EVIDENCE}
    summary = (f'{len(caps_with)} of {len(ev.CAPABILITIES)} capabilities · '
               + " · ".join(f'{n} {ev.EVIDENCE[k]["name"].lower()}' for k, n in counts.items()))
    return (f'<details class="profile" id="p-{esc(key)}">'
            f'<summary><span class="pf-title"><span class="sw" style="background:{s["color"]}"></span><b>{esc(s["name"])}</b> <span class="muted">{esc(s["sub"])}</span> {pages.tier_badge(key)}</span>'
            f'<span class="pf-sum muted small">{esc(summary)}</span></summary>'
            f'<div class="pf-body"><p class="muted small">{esc(s["what"])}. <a href="{up}solvers/{esc(key)}.html">How it was set up, and every result →</a></p>'
            + (f'<div class="table-scroll"><table class="data pf"><thead><tr><th>Capability</th>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
               if body_rows else '<p>No results yet.</p>')
            + none_line
            + (f'<p class="small"><a href="{up}corpus.html">{esc(CENSUS[key])}</a></p>' if key in CENSUS else "")
            + '</div></details>')


def page(manifests: list[dict], runs: dict, pages, census=None) -> tuple[str, str, str]:
    """(profiles.html, profiles.json, profiles.csv)."""
    esc = pages.esc
    CENSUS.clear()
    CENSUS.update(census_line(census))
    all_rows = rows(manifests, runs, pages)
    keys = pages.SOLVERS_ORDER({r["model"] for r in all_rows})
    toc, sections, mrows = [], [], []
    caps = list(ev.CAPABILITIES)
    kinds_k = list(ev.EVIDENCE)

    def mcell(k: str, c: str) -> str:
        n = {kk: sum(1 for r in all_rows if r["model"] == k and c in r["capabilities"] and r["evidence"] == kk) for kk in kinds_k}
        if not any(n.values()):
            return '<td class="mx-none"><span class="sr-only">none</span></td>'
        tip = f'{pages.SOLVER[k]["name"]} {pages.SOLVER[k]["sub"]}, {ev.CAPABILITIES[c]["name"]}: ' + ", ".join(f"{v} {ev.EVIDENCE[kk]['name'].lower()}" for kk, v in n.items() if v)
        marks = "".join(f'<i class="mk mk-{kk}">{v}</i>' for kk, v in n.items() if v)
        return f'<td><a href="#p-{esc(k)}" title="{esc(tip)}" aria-label="{esc(tip)}">{marks}</a></td>'

    for kind, title in KIND_GROUPS:
        ks = [k for k in keys if pages.SOLVER[k]["kind"] == kind]
        if not ks:
            continue
        toc.append(f'<li><b>{esc(title)}:</b> ' + ", ".join(
            f'<a href="#p-{esc(k)}">{esc(pages.SOLVER[k]["name"])} {esc(pages.SOLVER[k]["sub"])}</a>' for k in ks) + "</li>")
        sections.append(f'<h2 class="pf-group">{esc(title)}</h2>' + "".join(model_profile(k, all_rows, pages) for k in ks))
        mrows.append(f'<tr class="mx-group"><th colspan="{len(caps) + 1}" scope="rowgroup">{esc(title)}</th></tr>' + "".join(
            f'<tr><th scope="row"><a href="#p-{esc(k)}"><span class="sw" style="background:{pages.SOLVER[k]["color"]}"></span>{esc(pages.SOLVER[k]["name"])}'
            f' <span class="muted">{esc(pages.SOLVER[k]["sub"])}</span></a></th>' + "".join(mcell(k, c) for c in caps) + "</tr>" for k in ks))
    tiers = "".join(f'<li><b>{esc(t)} · {esc(n)}</b>: {esc(w)}</li>' for t, (n, w) in pages.config_records.TIERS.items())
    kinds = "".join(f'<li><b>{esc(v["name"])}</b>: the truth is {esc(v["truth"])}; a difference means {esc(v["a_miss_means"])}.</li>'
                    for v in ev.EVIDENCE.values())
    body = f"""<div class="wrap">
<section class="page-head">
  <h1>Evidence profiles</h1>
  <p class="lede">For each model, what the evidence says about each kind of flow it may be used for, and where there is none yet. Every result is its percent difference from the right answer. Nothing is ranked and no number is combined across tests.</p>
</section>
<section class="section" id="overview"><h2>Where the evidence is</h2>
<p class="muted">One row per model, one column per capability. Each cell counts the model's results there: <i class="mk mk-verification">n</i> against an exact solution, <i class="mk mk-validation">n</i> against measurements, <i class="mk mk-comparison">n</i> against another code. An empty cell means no evidence yet. Select a row to see every result.</p>
<div class="table-scroll mx-wrap"><table class="mx">
<thead><tr><th scope="col" class="mx-model">Model</th>{"".join(f'<th scope="col" class="mx-cap" title="{esc(ev.CAPABILITIES[c]["engineer"])}"><span>{esc(ev.CAPABILITIES[c]["name"])}</span></th>' for c in caps)}</tr></thead>
<tbody>{"".join(mrows)}</tbody></table></div>
<p class="small">Download every result: <a href="data/profiles.csv">profiles.csv</a> · <a href="data/profiles.json">profiles.json</a>.</p></section>
<section class="section grid">
  <div class="card"><h3>Three kinds of evidence</h3><ul>{kinds}</ul></div>
  <div class="card"><h3>How each model was set up</h3><ul>{tiers}</ul><p class="small">Results of different tiers were set up under different rules and are never compared as if alike.</p></div>
</section>
<section class="section" id="models"><div class="head-row"><h2>Each model's evidence</h2>
<div class="pf-tools"><button type="button" class="btn ghost sm" data-open-all="details.profile">Open all</button><button type="button" class="btn ghost sm" data-close-all="details.profile">Close all</button></div></div>
<p class="muted small">Each percent is that result's difference from the right answer; the shading only helps reading and is not a verdict. Hover a capability for what it covers.</p>
{"".join(sections)}</section>
</div>
"""
    html = pages.layout("Evidence profiles", body, "profiles.html",
                        description="What verification, validation and comparison evidence says about each water model, capability by capability.")
    data = {"protocol": "4.0", "updated": date.today().isoformat(),
            "evidence": ev.EVIDENCE, "capabilities": ev.CAPABILITIES,
            "tiers": {t: {"name": n, "rule": w} for t, (n, w) in pages.config_records.TIERS.items()},
            "results": all_rows}
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["model", "model_name", "tier", "test", "test_name", "case_version", "evidence", "capabilities",
            "percent_difference", "engine_flag", "label"]
    w.writerow(cols)
    for r in all_rows:
        w.writerow([";".join(r[c]) if c == "capabilities" else ("" if r[c] is None else r[c]) for c in cols])
    return html, json.dumps(data, indent=1, ensure_ascii=False), buf.getvalue()
