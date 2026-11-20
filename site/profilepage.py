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


def _cell(results: list[dict], pages, depth: int) -> str:
    if not results:
        return '<td class="pf-none">—</td>'
    up = "../" * depth
    items = "".join(
        f'<li><a href="{up}tests/{r["test"]}.html#m-{r["model"]}">{pages.esc(r["test_name"])}</a> '
        f'<span class="score {pages.measures.klass(r["percent_difference"])}">{pages.esc(pages.measures.short(r["percent_difference"]))}</span>'
        + (f' <span class="muted small">{pages.esc(r["engine_flag"] or r["label"])}</span>' if (r["engine_flag"] or r["label"]) else "")
        + "</li>" for r in results)
    return f'<td><ul class="pf-list">{items}</ul></td>'


def model_profile(key: str, all_rows: list[dict], pages, depth: int = 0) -> str:
    mine = [r for r in all_rows if r["model"] == key]
    s = pages.SOLVER[key]
    esc = pages.esc
    caps_with = [c for c in ev.CAPABILITIES if any(c in r["capabilities"] for r in mine)]
    caps_without = [c for c in ev.CAPABILITIES if c not in caps_with]
    body_rows = []
    for c in caps_with:
        cells = "".join(_cell([r for r in mine if c in r["capabilities"] and r["evidence"] == k], pages, depth) for k in ev.EVIDENCE)
        body_rows.append(f'<tr><th scope="row"><b>{esc(ev.CAPABILITIES[c]["name"])}</b>'
                         f'<div class="muted small">{esc(ev.CAPABILITIES[c]["engineer"])}</div></th>{cells}</tr>')
    head = "".join(f'<th>{esc(v["name"])}<div class="muted small">against {esc(v["short"])}</div></th>' for v in ev.EVIDENCE.values())
    up = "../" * depth
    none_line = (f'<p class="small">No evidence yet on: {esc(", ".join(ev.CAPABILITIES[c]["name"] for c in caps_without))}.</p>'
                 if caps_without else "")
    return (f'<section class="section profile" id="p-{esc(key)}">'
            f'<h2><span class="sw" style="background:{s["color"]}"></span>{esc(s["name"])} <small class="muted">{esc(s["sub"])}</small> {pages.tier_badge(key)}</h2>'
            f'<p class="muted small">{esc(s["what"])}. <a href="{up}solvers/{esc(key)}.html">How it was set up, and every result →</a></p>'
            + (f'<div class="table-scroll"><table class="data pf"><thead><tr><th>Capability</th>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
               if body_rows else '<p>No results yet.</p>')
            + none_line + '</section>')


def page(manifests: list[dict], runs: dict, pages) -> tuple[str, str, str]:
    """(profiles.html, profiles.json, profiles.csv)."""
    esc = pages.esc
    all_rows = rows(manifests, runs, pages)
    keys = pages.SOLVERS_ORDER({r["model"] for r in all_rows})
    toc, sections = [], []
    for kind, title in KIND_GROUPS:
        ks = [k for k in keys if pages.SOLVER[k]["kind"] == kind]
        if not ks:
            continue
        toc.append(f'<li><b>{esc(title)}:</b> ' + ", ".join(
            f'<a href="#p-{esc(k)}">{esc(pages.SOLVER[k]["name"])} {esc(pages.SOLVER[k]["sub"])}</a>' for k in ks) + "</li>")
        sections.append(f'<h2 class="pf-group">{esc(title)}</h2>' + "".join(model_profile(k, all_rows, pages) for k in ks))
    tiers = "".join(f'<li><b>{esc(t)} · {esc(n)}</b>: {esc(w)}</li>' for t, (n, w) in pages.config_records.TIERS.items())
    kinds = "".join(f'<li><b>{esc(v["name"])}</b>: the truth is {esc(v["truth"])}; a difference means {esc(v["a_miss_means"])}.</li>'
                    for v in ev.EVIDENCE.values())
    body = f"""<div class="wrap">
<section class="page-head">
  <h1>Evidence profiles</h1>
  <p class="lede">For each model, what the evidence says about each kind of flow it may be used for: one row per capability, one column per kind of evidence, every result with its percent difference from the right answer. Nothing is ranked, no number is combined across tests, and an empty cell means no evidence yet.</p>
</section>
<section class="section grid">
  <div class="card"><h3>Three kinds of evidence</h3><ul>{kinds}</ul></div>
  <div class="card"><h3>How each model was set up</h3><ul>{tiers}</ul><p class="small">Results of different tiers were set up under different rules and are never compared as if alike.</p></div>
</section>
<section class="section"><h2>Models</h2><ul class="waitlist">{"".join(toc)}</ul>
<p class="small">Download every row: <a href="data/profiles.csv">profiles.csv</a> · <a href="data/profiles.json">profiles.json</a>. The shading of a percent difference is for reading only; it is not a verdict.</p></section>
{"".join(sections)}
</div>"""
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
