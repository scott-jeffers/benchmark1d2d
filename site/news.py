"""What's new: releases (from CHANGELOG.md) and result changes (from the collector's log).

``news_page`` renders ``news.html``; ``atom_feed`` writes ``feed.xml`` with the
same entries, newest first, so people can follow the benchmark in a feed reader.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import escape as esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://scott-jeffers.github.io/benchmark1d2d/"


def releases(changelog: Path) -> list[dict]:
    """Each '## [x] — date' section: version, date, summary paragraph, the bold leads of its items, full markdown."""
    text = changelog.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    out = []
    for part in parts:
        head, _, body = part.partition("\n")
        m = re.match(r"\[(.+?)\](?:\s*[—-]\s*(\d{4}-\d{2}-\d{2}))?", head.strip())
        if not m:
            continue
        version, date = m.group(1), m.group(2)
        paras = [p.strip() for p in body.strip().split("\n\n") if p.strip()]
        summary = next((p for p in paras if not p.startswith(("#", "-", "*"))), "")
        leads = [re.sub(r"\s+", " ", x).strip().rstrip(".:") for x in re.findall(r"^- \*\*(.+?)\*\*", body, flags=re.M | re.S)]
        out.append(dict(version=version, date=date, summary=re.sub(r"\s+", " ", summary), leads=leads, body=body.strip()))
    return out


def result_changes(log: Path) -> list[dict]:
    if not log.is_file():
        return []
    out = []
    for ln in log.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return sorted(out, key=lambda e: e["date"], reverse=True)


WF_NAMES = {"open-solvers.yml": "Open-source solvers", "slow-runs.yml": "Long runs", "hecras.yml": "HEC-RAS",
            "track-a.yml": "Physics tests", "nightly.yml": "Nightly SWMM comparison"}


def _change_html(text: str) -> str:
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    # link a test id (A1F-040_swashes_… or A1F-040) to its page
    return re.sub(r"\b((?:A1P|A1F|A1D|A2A|A2C|A2L|A2F|A12|B)-[A-Za-z0-9]+)(_[a-z0-9_]+)?", r'<a href="tests/\1.html">\1</a>', t, count=1)


def news_page(layout, md, changelog: Path, log: Path) -> str:
    rel = releases(changelog)
    changes = result_changes(log)
    rel_html = []
    for r in rel:
        when = r["date"] or "in progress"
        title = "Next release" if r["version"].lower() == "unreleased" else f"Release {r['version']}"
        leads = "".join(f"<li>{esc(x)}</li>" for x in r["leads"][:8])
        rel_html.append(f"""<article class="card news-item" id="v{esc(r['version'])}">
  <div class="kicker">{esc(when)}</div><h3>{esc(title)}</h3>
  {f'<p>{esc(r["summary"])}</p>' if r["summary"] else ''}
  {f'<ul>{leads}</ul>' if leads else ''}
  <details><summary>Everything in this release</summary><div class="prose">{md(r['body'], drop_h1=False)}</div></details>
</article>""")
    ch_html = []
    for e in changes[:40]:
        items = "".join(f"<li><span class=\"muted\">{esc(WF_NAMES.get(i.get('workflow') or '', i.get('workflow') or ''))}:</span> {_change_html(i['text'])}</li>"
                        for i in e["items"][:30])
        more = f'<li class="muted">…and {len(e["items"]) - 30} more</li>' if len(e["items"]) > 30 else ""
        ch_html.append(f'<article class="news-change"><div class="kicker">{esc(e["date"].replace("T", " "))}</div><ul>{items}{more}</ul></article>')
    body = f"""<div class="wrap">
<section class="page-head">
  <h1>What's new</h1>
  <p class="lede">New tests, new models and every change in a result, as it happens. <a href="feed.xml">Follow the feed</a>.</p>
</section>
<div class="news-cols">
  <section><h2>Releases</h2>{''.join(rel_html) or '<p class="muted">No releases yet.</p>'}</section>
  <section><h2>Result changes</h2>
    <p class="muted">Recorded each time the solvers are re-run and a result moves: a new score card, a pass that became a fail (or the reverse), a number that changed, a shift in SWMM compatibility.</p>
    {''.join(ch_html) or '<p class="muted">No result has changed since this log began.</p>'}
  </section>
</div>
</div>"""
    return layout("What's new", body, "news.html", description="New tests, new models and every change in a benchmark result.")


def atom_feed(changelog: Path, log: Path, out: Path) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []
    for r in releases(changelog):
        if not r["date"]:
            continue
        summary = r["summary"] + ("\n\n" + "\n".join("• " + x for x in r["leads"]) if r["leads"] else "")
        entries.append((f"{r['date']}T12:00:00Z", f"Release {r['version']}", f"{SITE_URL}news.html#v{r['version']}", summary))
    for e in result_changes(log)[:30]:
        n = len(e["items"])
        summary = "\n".join("• " + re.sub(r"[*`]", "", i["text"]) for i in e["items"][:20])
        entries.append((e["date"].replace("Z", ":00Z"), f"{n} result change{'s' if n != 1 else ''}", f"{SITE_URL}news.html", summary))
    entries.sort(key=lambda x: x[0], reverse=True)
    xml = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom">',
           "<title>OpenHydro Bench: what's new</title>", f'<link href="{SITE_URL}news.html"/>', f'<link rel="self" href="{SITE_URL}feed.xml"/>',
           f"<id>{SITE_URL}feed.xml</id>", f"<updated>{now}</updated>", "<author><name>OpenHydro Bench</name></author>"]
    for when, title, link, summary in entries[:50]:
        xml += ["<entry>", f"<title>{esc(title)}</title>", f'<link href="{esc(link)}"/>', f"<id>{esc(link)}#{esc(when)}</id>",
                f"<updated>{esc(when)}</updated>", f"<summary>{esc(summary)}</summary>", "</entry>"]
    xml.append("</feed>")
    out.write_text("\n".join(xml) + "\n", encoding="utf-8")
