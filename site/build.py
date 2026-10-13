#!/usr/bin/env python3
"""Dependency-light static site generator for benchmark1d2d.

Discovers manifests under test_catalog/ and optional scorecards under one or
more --scorecards directories. Writes plain HTML into site/dist/.

Usage:
  python site/build.py
  python site/build.py --scorecards out --scorecards site/fixtures/scorecards
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

PLACEHOLDER_NOTE = "Awaiting score"
SITE_TAGLINE = "Open V&amp;V benchmarks for water solvers"
FONT_LINKS = """  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet"/>
"""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_manifests(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    catalog = root / "test_catalog"
    out: list[tuple[Path, dict[str, Any]]] = []
    if not catalog.is_dir():
        return out
    for path in sorted(catalog.rglob("manifest.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: skip {path}: {exc}", file=sys.stderr)
            continue
        out.append((path, data))
    return out


def discover_scorecards(score_dirs: list[Path]) -> dict[str, dict[str, Any]]:
    """Merge scorecards from multiple directories. Later dirs override earlier."""
    cards: dict[str, dict[str, Any]] = {}
    for score_dir in score_dirs:
        if not score_dir.is_dir():
            continue
        patterns = ("*.scorecard.json", "*scorecard*.json")
        seen: set[Path] = set()
        for pattern in patterns:
            for path in score_dir.rglob(pattern):
                if path in seen:
                    continue
                seen.add(path)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                test_id = data.get("test_id") or path.stem.replace(".scorecard", "")
                cards[str(test_id)] = data
    return cards


def load_engine_pins(root: Path) -> list[dict[str, Any]]:
    pins: list[dict[str, Any]] = []
    pin_path = root / "reference_engines" / "swmm-5.2.4" / "pin.json"
    if pin_path.is_file():
        try:
            pins.append(json.loads(pin_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: skip {pin_path}: {exc}", file=sys.stderr)
    return pins


def find_results_parquet(root: Path, test_id: str, scorecard: dict[str, Any]) -> Path | None:
    """Locate a results parquet near score output or under out/."""
    candidates: list[Path] = []
    out = root / "out"
    short = test_id.split("_", 1)[0] if "_" in test_id else test_id
    for base in (out, out / "vertical_slice", out / "swmm_self_parity", out / "phase5_2d"):
        if not base.is_dir():
            continue
        candidates.extend(base.glob(f"{test_id}*.parquet"))
        candidates.extend(base.glob(f"{short}*.parquet"))
        candidates.extend(base.rglob(f"*{test_id}*.parquet"))
    _ = scorecard.get("solver") or {}
    for path in candidates:
        if test_id in path.name:
            return path
    return candidates[0] if candidates else None


def try_plot(
    root: Path,
    manifest: dict[str, Any],
    scorecard: dict[str, Any] | None,
    png_path: Path,
) -> bool:
    """Optional matplotlib ref-vs-solver plot. Returns True if written."""
    if scorecard is None:
        return False
    parquet = find_results_parquet(root, str(manifest.get("test_id", "")), scorecard)
    if parquet is None or not parquet.is_file():
        return False
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError:
        print("WARN: matplotlib/pandas unavailable; skipping plots", file=sys.stderr)
        return False

    try:
        df = pd.read_parquet(parquet)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: cannot read {parquet}: {exc}", file=sys.stderr)
        return False

    var = "h"
    criteria = (manifest.get("scoring") or {}).get("criteria") or []
    if criteria:
        var = str(criteria[0].get("variable") or var)
    if var not in df.columns:
        for candidate in ("h", "p", "Q", "u", "c"):
            if candidate in df.columns:
                var = candidate
                break
        else:
            return False

    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    if "x" in df.columns:
        plot_df = df
        if "t" in df.columns:
            t_max = plot_df["t"].max()
            plot_df = plot_df[plot_df["t"] == t_max]
        ax.plot(plot_df["x"], plot_df[var], label=f"solver {var}", color="#0b6e8a")
        ax.set_xlabel("x")
    elif "t" in df.columns:
        ax.plot(df["t"], df[var], label=f"solver {var}", color="#0b6e8a")
        ax.set_xlabel("t")
    else:
        ax.plot(df[var].values, label=f"solver {var}", color="#0b6e8a")
        ax.set_xlabel("index")

    ref = manifest.get("reference") or {}
    if ref.get("kind") == "analytic":
        gen = ref.get("generator") or {}
        module_name = gen.get("module")
        func_name = gen.get("function")
        params = gen.get("parameters") or {}
        if module_name and func_name and "x" in df.columns:
            try:
                import importlib

                mod = importlib.import_module(str(module_name))
                fn = getattr(mod, str(func_name))
                x = df["x"].unique() if "t" not in df.columns else df.loc[df["t"] == df["t"].max(), "x"]
                t_end = float((manifest.get("simulation") or {}).get("t_end") or 0)
                x_arr = x.to_numpy()
                try:
                    out = fn(x_arr, t_end, **params)
                except TypeError:
                    out = fn(x_arr, **params)
                if isinstance(out, tuple):
                    y_ref = out[0]
                elif isinstance(out, dict):
                    y_ref = out.get(var, out.get("h"))
                    if y_ref is None and out:
                        y_ref = next(iter(out.values()))
                else:
                    y_ref = out
                if y_ref is not None:
                    ax.plot(x_arr, y_ref, "--", label=f"reference {var}", color="#2c4a6e")
            except Exception as exc:  # noqa: BLE001
                print(f"WARN: reference overlay failed: {exc}", file=sys.stderr)

    ax.set_ylabel(var)
    ax.set_title(str(manifest.get("test_id", "results")))
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=120)
    plt.close(fig)
    return True


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def inline_md(text: str) -> str:
    """Escape then apply inline ``code`` and **bold**."""
    s = html.escape(text)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def page_shell(
    title: str,
    body: str,
    *,
    root_href: str = ".",
    active: str = "",
    full_bleed_hero: bool = False,
) -> str:
    nav = [
        ("index.html", "Home", "home"),
        ("catalog.html", "Catalog", "catalog"),
        ("get-started.html", "Get started", "get-started"),
        ("engines.html", "Engines", "engines"),
        ("methodology.html", "Methodology", "methodology"),
    ]
    nav_html = []
    for href, label, key in nav:
        cls = ' class="active"' if key == active else ""
        nav_html.append(f'<a href="{root_href}/{href}"{cls}>{label}</a>')
    wrap_cls = "wrap wrap-wide" if not full_bleed_hero else "wrap wrap-home"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="description" content="benchmark1d2d — open verification and validation benchmarks for free-surface and pressurized water solvers. Track A proves physics; Track B proves industry parity."/>
  <meta property="og:title" content="{esc(title)} — benchmark1d2d"/>
  <meta property="og:description" content="Open V&amp;V benchmarks for water solvers. Dual-track certification: physics verification and SWMM parity."/>
  <title>{esc(title)} — benchmark1d2d</title>
{FONT_LINKS}  <link rel="stylesheet" href="{root_href}/style.css"/>
</head>
<body>
  <div class="{wrap_cls}">
    <header class="site">
      <div class="brand-block">
        <a class="brand" href="{root_href}/index.html">benchmark1d2d</a>
        <p class="tagline">{SITE_TAGLINE}</p>
      </div>
      <nav class="site" aria-label="Primary">
        {"".join(nav_html)}
      </nav>
    </header>
    {body}
    <footer class="site">
      <p>Track A proves equations; Track B proves parity. Tables are never merged.</p>
      <p class="meta"><a href="https://github.com/scott-jeffers/benchmark1d2d">GitHub</a></p>
    </footer>
  </div>
</body>
</html>
"""


def format_citation(c: dict[str, Any]) -> str:
    authors = ", ".join(c.get("authors") or []) or "—"
    year = c.get("year", "")
    title = c.get("title", "")
    bits = [f"<strong>{esc(title)}</strong>", f"{esc(authors)} ({esc(year)})"]
    for key in ("doi", "url", "isbn", "report_number"):
        if c.get(key):
            bits.append(f"{esc(key)}: {esc(c[key])}")
    return " — ".join(bits)


def pass_cell(card: dict[str, Any] | None) -> str:
    if card is None:
        return f'<span class="status-none">{PLACEHOLDER_NOTE}</span>'
    passed = card.get("passed")
    if passed is True:
        return '<span class="status-pass">PASS</span>'
    if passed is False:
        return '<span class="status-fail">FAIL</span>'
    return f'<span class="status-none">{esc(passed)}</span>'


def results_table_rows(
    manifests: list[dict[str, Any]],
    scorecards: dict[str, dict[str, Any]],
    *,
    tests_prefix: str = "tests/",
) -> str:
    rows: list[str] = []
    for m in manifests:
        tid = str(m.get("test_id", ""))
        card = scorecards.get(tid)
        title = m.get("title") or tid
        status = m.get("status", "")
        test_class = m.get("test_class", "")
        href = f"{tests_prefix}{esc(tid)}.html"
        solver = ""
        if card:
            s = card.get("solver") or {}
            solver = f"{s.get('name', '')} {s.get('version', '')}".strip()
        rows.append(
            "<tr>"
            f'<td><a href="{href}"><code>{esc(tid)}</code></a><div class="meta">{esc(title)}</div></td>'
            f"<td>{esc(test_class)}</td>"
            f"<td>{esc(status)}</td>"
            f"<td>{esc(solver) if solver else '—'}</td>"
            f"<td>{pass_cell(card)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5" class="meta">No cases in this track yet.</td></tr>')
    return "\n".join(rows)


def engines_strip_html(pins: list[dict[str, Any]], *, root_href: str = ".") -> str:
    if not pins:
        return ""
    items = []
    for pin in pins:
        dll = (pin.get("binaries") or {}).get("swmm5.dll", "")
        short = dll[:12] + "…" if len(dll) > 12 else dll
        items.append(
            f'<li><strong>{esc(pin.get("engine"))} {esc(pin.get("version"))}</strong>'
            f' <span class="meta">({esc(pin.get("build"))})</span>'
            f' · <code class="hash">{esc(short)}</code>'
            f' · <a href="{root_href}/engines.html">details</a></li>'
        )
    return (
        '<section class="engines-strip" aria-label="Pinned reference engines">'
        "<h2>Pinned reference engines</h2>"
        f"<ul>{''.join(items)}</ul>"
        "</section>"
    )


def build_home(
    manifests: list[dict[str, Any]],
    scorecards: dict[str, dict[str, Any]],
    pins: list[dict[str, Any]],
) -> str:
    n_a = sum(1 for m in manifests if m.get("track") == "A")
    n_b = sum(1 for m in manifests if m.get("track") == "B")
    n_scored = sum(1 for m in manifests if scorecards.get(str(m.get("test_id"))))
    swmm = next((p for p in pins if p.get("engine") == "SWMM"), None)
    swmm_label = f"SWMM {swmm['version']}" if swmm else "pinned SWMM"

    body = f"""
    <section class="hero">
      <p class="brand-hero">benchmark1d2d</p>
      <h1>Prove your water solver — or prove it differs.</h1>
      <p class="hero-lede">
        Dual-track open V&amp;V: Track A checks the equations; Track B checks parity
        with industry engines such as {esc(swmm_label)}.
      </p>
      <div class="cta-group">
        <a class="cta primary" href="get-started.html">Get started</a>
        <a class="cta secondary" href="catalog.html">Browse catalog</a>
      </div>
    </section>

    <section class="how-it-works">
      <h2>How it works</h2>
      <ol class="steps">
        <li><strong>Pick a case</strong> from the catalog — analytic, lab, field, or parity.</li>
        <li><strong>Run your solver</strong> (or the demo) and adapt output to the results contract.</li>
        <li><strong>Score</strong> against published tolerances; publish a signed scorecard.</li>
      </ol>
    </section>

    <div class="tracks">
      <section class="track a">
        <h3>Track A — Physics</h3>
        <p>Exact solutions, laboratory and field measurements. Can prove a solver is
        <strong>wrong</strong>. {n_a} cases in catalog.</p>
      </section>
      <section class="track b">
        <h3>Track B — Industry parity</h3>
        <p>Pinned reference-engine output ({esc(swmm_label)}). Can only prove a solver
        <strong>differs</strong>. {n_b} cases in catalog.</p>
      </section>
    </div>

    <p class="meta scored-note">{n_scored} of {len(manifests)} cases currently show a scorecard on this build.</p>

    {engines_strip_html(pins)}
    """
    return page_shell("Home", body, root_href=".", active="home", full_bleed_hero=True)


def build_catalog(
    manifests: list[dict[str, Any]],
    scorecards: dict[str, dict[str, Any]],
    pins: list[dict[str, Any]],
) -> str:
    track_a = [m for m in manifests if m.get("track") == "A"]
    track_b = [m for m in manifests if m.get("track") == "B"]
    other = [m for m in manifests if m.get("track") not in ("A", "B")]
    swmm = next((p for p in pins if p.get("engine") == "SWMM"), None)
    swmm_note = ""
    if swmm:
        swmm_note = (
            f'<p class="meta">Track B ground truth: pinned '
            f'<a href="engines.html">{esc(swmm.get("engine"))} {esc(swmm.get("version"))}</a>.</p>'
        )

    body = f"""
    <p class="lede">
      Every published case. Track A and Track B are listed separately — a solver may
      pass one track and fail the other.
    </p>
    <p class="track-anchors">
      <a href="#track-a">Track A</a> · <a href="#track-b">Track B</a>
    </p>

    <h2 id="track-a">Track A — Physics &amp; verification</h2>
    <table class="results">
      <thead>
        <tr><th>Test</th><th>Class</th><th>Status</th><th>Solver</th><th>Result</th></tr>
      </thead>
      <tbody>
        {results_table_rows(track_a, scorecards)}
      </tbody>
    </table>

    <h2 id="track-b">Track B — Industry parity</h2>
    {swmm_note}
    <table class="results">
      <thead>
        <tr><th>Test</th><th>Class</th><th>Status</th><th>Solver</th><th>Result</th></tr>
      </thead>
      <tbody>
        {results_table_rows(track_b, scorecards)}
      </tbody>
    </table>
    """
    if other:
        body += f"""
    <h2>Unassigned track</h2>
    <table class="results">
      <thead>
        <tr><th>Test</th><th>Class</th><th>Status</th><th>Solver</th><th>Result</th></tr>
      </thead>
      <tbody>
        {results_table_rows(other, scorecards)}
      </tbody>
    </table>
    """
    return page_shell("Catalog", body, root_href=".", active="catalog")


def build_engines(
    pins: list[dict[str, Any]],
    scorecards: dict[str, dict[str, Any]],
) -> str:
    extran = scorecards.get("B-EXTRAN-001_extran_parity")
    parity_status = pass_cell(extran)

    rows = []
    for pin in pins:
        binaries = pin.get("binaries") or {}
        dll = binaries.get("swmm5.dll", "")
        bin_rows = "".join(
            f"<tr><td><code>{esc(name)}</code></td><td><code class=\"hash\">{esc(digest)}</code></td></tr>"
            for name, digest in binaries.items()
        )
        rows.append(
            f"""
    <section class="engine-detail">
      <h2>{esc(pin.get("engine"))} {esc(pin.get("version"))}</h2>
      <p>Build {esc(pin.get("build"))}. Official EPA release
      <a href="{esc(pin.get("upstream_url"))}">{esc(pin.get("upstream_tag"))}</a>
      · asset <code>{esc(pin.get("asset"))}</code>.</p>
      <table class="results pin-table">
        <thead><tr><th>Binary</th><th>SHA-256</th></tr></thead>
        <tbody>{bin_rows}</tbody>
      </table>
      <p>Self-parity on <a href="tests/B-EXTRAN-001_extran_parity.html"><code>B-EXTRAN-001</code></a>:
      {parity_status}</p>
      <p class="meta">Hashes are authoritative in <code>reference_engines/swmm-5.2.4/SHA256SUMS</code>;
      <code>pin.json</code> is the machine-readable mirror used by the CLI and this site.</p>
    </section>
            """
        )

    if not rows:
        rows.append("<p>No pinned engines found.</p>")

    body = f"""
    <p class="lede">
      Track B compares candidate solvers to pinned industry binaries. References are
      regenerated by CI — never hand-edited.
    </p>
    {"".join(rows)}
    <section class="engine-detail planned">
      <h2>EPANET</h2>
      <p class="meta">Planned pin (not yet published). See repository roadmap.</p>
    </section>
    """
    return page_shell("Engines", body, root_href=".", active="engines")


def build_test_page(
    manifest: dict[str, Any],
    scorecard: dict[str, Any] | None,
    *,
    has_plot: bool,
) -> str:
    tid = str(manifest.get("test_id", ""))
    physics = manifest.get("physics") or {}
    provenance = manifest.get("provenance") or {}
    scoring = manifest.get("scoring") or {}
    citations = provenance.get("citations") or []
    criteria = scoring.get("criteria") or []
    track = manifest.get("track")

    phys_bits = (
        f'<span class="badge">{esc(physics.get("dimensionality"))}</span>'
        f'<span class="badge">{esc(physics.get("flow_type"))}</span>'
        f'<span class="badge">{esc(manifest.get("test_class"))}</span>'
        f'<span class="badge">status: {esc(manifest.get("status"))}</span>'
        f'<span class="badge track-{esc(track)}">track {esc(track)}</span>'
    )
    eq = ", ".join(physics.get("governing_equations") or [])
    phen = ", ".join(physics.get("phenomena") or [])

    cite_html = "\n".join(f"<li>{format_citation(c)}</li>" for c in citations) or "<li>—</li>"
    crit_html_parts: list[str] = []
    for c in criteria:
        thr = c.get("threshold") or {}
        crit_html_parts.append(
            "<li>"
            f"<code>{esc(c.get('id'))}</code> — {esc(c.get('metric'))}({esc(c.get('variable'))}) "
            f"{esc(thr.get('op'))} {esc(thr.get('value'))} {esc(thr.get('units'))}"
            f'<span class="rationale">Rationale: {esc(c.get("rationale"))}</span>'
            "</li>"
        )
    crit_html = "\n".join(crit_html_parts) or "<li>No criteria declared.</li>"

    conv = scoring.get("convergence")
    conv_html = ""
    if conv:
        conv_html = (
            f'<p class="meta">Convergence: {esc(conv.get("norm"))}({esc(conv.get("variable"))}), '
            f'expected order {esc(conv.get("expected_order"))}, '
            f'min observed {esc(conv.get("min_observed_order"))}</p>'
        )

    score_html = f"<p>{pass_cell(scorecard)}</p>"
    if scorecard:
        solver = scorecard.get("solver") or {}
        score_html += (
            f'<p class="meta">Solver: {esc(solver.get("name"))} {esc(solver.get("version"))} '
            f'(adapter {esc(solver.get("adapter"))})</p>'
        )
        cr = scorecard.get("criteria_results") or []
        if cr:
            items = []
            for r in cr:
                mark = "PASS" if r.get("passed") else "FAIL"
                items.append(
                    f"<li><code>{esc(r.get('id'))}</code>: {esc(mark)} "
                    f"(observed {esc(r.get('observed'))})</li>"
                )
            score_html += "<ul class='criteria'>" + "\n".join(items) + "</ul>"

    plot_html = ""
    if has_plot:
        plot_html = (
            f'<h2>Reference vs solver</h2>'
            f'<img class="plot" src="{esc(tid)}.png" alt="plot for {esc(tid)}"/>'
        )

    adapter = "swmm5" if track == "B" else "generic_parquet"
    run_block = f"""
    <h3>Run this case</h3>
    <pre class="run-block"><code>benchmark1d2d run {esc(tid)} \\
  --solver path/to/your_solver \\
  --adapter {esc(adapter)} \\
  --out out/demo

benchmark1d2d score {esc(tid)} \\
  --results out/demo/{esc(tid)}.parquet \\
  --solver-name my_solver --solver-version 1.0.0</code></pre>
    <p class="meta">See <a href="../get-started.html">Get started</a> for install and demo solver paths.</p>
    """

    body = f"""
    <h2>{esc(manifest.get("title") or tid)}</h2>
    <p class="meta"><code>{esc(tid)}</code> · case v{esc(manifest.get("case_version"))}</p>
    <p>{phys_bits}</p>
    <p>{esc(manifest.get("description") or "")}</p>

    {run_block}

    <h3>Physics</h3>
    <p>Governing equations: <code>{esc(eq)}</code></p>
    <p>Phenomena: <code>{esc(phen)}</code></p>

    <h3>Citations</h3>
    <ul class="citations">{cite_html}</ul>
    <p class="meta">License: <code>{esc(provenance.get("license"))}</code></p>

    <h3>Scoring tolerances</h3>
    <ul class="criteria">{crit_html}</ul>
    {conv_html}

    <h3>Latest scorecard</h3>
    {score_html}
    {plot_html}
    """
    return page_shell(tid, body, root_href="..", active="catalog")


def simple_md_to_html(text: str) -> str:
    """Markdown subset: headings, paragraphs, ul/ol, tables, fenced code, bold/code."""
    lines = text.splitlines()
    blocks: list[str] = []
    para: list[str] = []
    list_items: list[str] = []
    list_ordered = False
    table_rows: list[list[str]] = []
    in_fence = False
    fence_lines: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if para:
            blocks.append(f"<p>{inline_md(' '.join(para))}</p>")
            para = []

    def flush_list() -> None:
        nonlocal list_items, list_ordered
        if list_items:
            tag = "ol" if list_ordered else "ul"
            items = "".join(f"<li>{inline_md(i)}</li>" for i in list_items)
            blocks.append(f"<{tag}>{items}</{tag}>")
            list_items = []
            list_ordered = False

    def flush_table() -> None:
        nonlocal table_rows
        if not table_rows:
            return
        # Drop markdown separator row (|---|---|)
        body_rows = [
            r
            for r in table_rows
            if not all(re.fullmatch(r":?-+:?", c.strip()) for c in r)
        ]
        if not body_rows:
            table_rows = []
            return
        head, *rest = body_rows
        thead = "".join(f"<th>{inline_md(c.strip())}</th>" for c in head)
        tbody = ""
        for row in rest:
            tbody += "<tr>" + "".join(f"<td>{inline_md(c.strip())}</td>" for c in row) + "</tr>"
        blocks.append(
            f'<table class="results md-table"><thead><tr>{thead}</tr></thead>'
            f"<tbody>{tbody}</tbody></table>"
        )
        table_rows = []

    def flush_fence() -> None:
        nonlocal fence_lines, in_fence
        if in_fence or fence_lines:
            code = html.escape("\n".join(fence_lines))
            blocks.append(f'<pre class="run-block"><code>{code}</code></pre>')
            fence_lines = []
            in_fence = False

    for raw in lines:
        line = raw.rstrip()
        if in_fence:
            if line.strip().startswith("```"):
                flush_fence()
            else:
                fence_lines.append(raw.rstrip("\n"))
            continue
        if line.strip().startswith("```"):
            flush_para()
            flush_list()
            flush_table()
            in_fence = True
            fence_lines = []
            continue
        if not line.strip():
            flush_para()
            flush_list()
            flush_table()
            continue
        if line.startswith("#"):
            flush_para()
            flush_list()
            flush_table()
            level = len(line) - len(line.lstrip("#"))
            level = min(max(level, 1), 4)
            content = inline_md(line.lstrip("# ").strip())
            blocks.append(f"<h{level}>{content}</h{level}>")
            continue
        if "|" in line and line.strip().startswith("|"):
            flush_para()
            flush_list()
            cells = [c for c in line.strip().strip("|").split("|")]
            table_rows.append(cells)
            continue
        m_ol = re.match(r"^(\d+)\.\s+(.*)$", line.lstrip())
        if m_ol:
            flush_para()
            flush_table()
            if list_items and not list_ordered:
                flush_list()
            list_ordered = True
            list_items.append(m_ol.group(2).strip())
            continue
        if line.lstrip().startswith(("- ", "* ")):
            flush_para()
            flush_table()
            if list_items and list_ordered:
                flush_list()
            list_ordered = False
            list_items.append(line.lstrip()[2:].strip())
            continue
        # Soft-wrapped continuation of a list item (indent or plain prose).
        if list_items and (raw.startswith("   ") or raw.startswith("\t") or not re.match(r"^[#`|\-\*]", line.lstrip())):
            list_items[-1] = list_items[-1] + " " + line.strip()
            continue
        flush_list()
        flush_table()
        para.append(line.strip())
    flush_para()
    flush_list()
    flush_table()
    flush_fence()
    return "\n".join(blocks)


def build_methodology(root: Path) -> str:
    method_dir = root / "docs" / "methodology"
    parts: list[str] = [
        "<p class='lede'>How benchmark1d2d sets tolerances and runs verification, "
        "validation, and industry parity.</p>"
    ]
    if method_dir.is_dir():
        for path in sorted(method_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            # Drop the first H1 from the body; section title comes from the filename.
            text_wo_h1 = re.sub(r"^#\s+.*\n+", "", text, count=1)
            parts.append(
                f'<section class="method-block"><h2>{esc(path.stem.replace("_", " ").title())}</h2>'
                f"{simple_md_to_html(text_wo_h1)}</section>"
            )
    else:
        parts.append("<p>No methodology documents found.</p>")
    return page_shell("Methodology", "\n".join(parts), root_href=".", active="methodology")


def build_get_started(root: Path) -> str:
    path = root / "docs" / "get_started.md"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        text_wo_h1 = re.sub(r"^#\s+.*\n+", "", text, count=1)
        body = f"<p class='lede'>Install the CLI, score a demo case, and build this site locally.</p>\n{simple_md_to_html(text_wo_h1)}"
    else:
        body = "<p>Get-started guide missing.</p>"
    return page_shell("Get started", body, root_href=".", active="get-started")


def build(root: Path, scorecards_dirs: list[Path]) -> dict[str, int]:
    site_dir = root / "site"
    dist = site_dir / "dist"
    static = site_dir / "static"

    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    tests_dir = dist / "tests"
    tests_dir.mkdir()

    if static.is_dir():
        for asset in static.iterdir():
            if asset.is_file():
                shutil.copy2(asset, dist / asset.name)

    loaded = discover_manifests(root)
    manifests = [m for _, m in loaded]
    manifests.sort(key=lambda m: str(m.get("test_id", "")))
    scorecards = discover_scorecards(scorecards_dirs)
    pins = load_engine_pins(root)

    (dist / "index.html").write_text(build_home(manifests, scorecards, pins), encoding="utf-8")
    (dist / "catalog.html").write_text(
        build_catalog(manifests, scorecards, pins), encoding="utf-8"
    )
    (dist / "get-started.html").write_text(build_get_started(root), encoding="utf-8")
    (dist / "engines.html").write_text(build_engines(pins, scorecards), encoding="utf-8")
    (dist / "methodology.html").write_text(build_methodology(root), encoding="utf-8")

    n_plots = 0
    for _path, manifest in loaded:
        tid = str(manifest.get("test_id", "unknown"))
        card = scorecards.get(tid)
        png_path = tests_dir / f"{tid}.png"
        has_plot = try_plot(root, manifest, card, png_path)
        if has_plot:
            n_plots += 1
        (tests_dir / f"{tid}.html").write_text(
            build_test_page(manifest, card, has_plot=has_plot),
            encoding="utf-8",
        )

    return {
        "manifests": len(manifests),
        "test_pages": len(loaded),
        "scorecards": len(scorecards),
        "plots": n_plots,
        "pages": 5 + len(loaded),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build benchmark1d2d static site")
    parser.add_argument(
        "--scorecards",
        type=Path,
        action="append",
        default=None,
        help="Directory of scorecard JSON files (repeatable; later overrides earlier)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: parent of site/)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    if args.scorecards:
        score_dirs = [p.resolve() for p in args.scorecards]
    else:
        score_dirs = [
            root / "site" / "fixtures" / "scorecards",
            root / "out",
        ]
    counts = build(root, score_dirs)
    print(
        f"Built site/dist: {counts['pages']} HTML pages "
        f"({counts['test_pages']} tests, {counts['scorecards']} scorecards, "
        f"{counts['plots']} plots)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
