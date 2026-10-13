#!/usr/bin/env python3
"""Dependency-light static site generator for benchmark1d2d.

Discovers manifests under test_catalog/ and optional scorecards under out/
(or --scorecards). Writes plain HTML into site/dist/.

Usage:
  python site/build.py
  python site/build.py --scorecards out
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Any

PLACEHOLDER_NOTE = "No scorecard yet"


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


def discover_scorecards(score_dir: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    if not score_dir.is_dir():
        return cards
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


def find_results_parquet(root: Path, test_id: str, scorecard: dict[str, Any]) -> Path | None:
    """Locate a results parquet near score output or under out/."""
    candidates: list[Path] = []
    out = root / "out"
    short = test_id.split("_", 1)[0] if "_" in test_id else test_id
    for base in (out, out / "vertical_slice"):
        if not base.is_dir():
            continue
        candidates.extend(base.glob(f"{test_id}*.parquet"))
        candidates.extend(base.glob(f"{short}*.parquet"))
        candidates.extend(base.rglob(f"*{test_id}*.parquet"))
    solver = scorecard.get("solver") or {}
    # Prefer exact test_id match.
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
        # Last time slice if t present.
        plot_df = df
        if "t" in df.columns:
            t_max = plot_df["t"].max()
            plot_df = plot_df[plot_df["t"] == t_max]
        ax.plot(plot_df["x"], plot_df[var], label=f"solver {var}", color="#0a5f7a")
        ax.set_xlabel("x")
    elif "t" in df.columns:
        ax.plot(df["t"], df[var], label=f"solver {var}", color="#0a5f7a")
        ax.set_xlabel("t")
    else:
        ax.plot(df[var].values, label=f"solver {var}", color="#0a5f7a")
        ax.set_xlabel("index")

    # Overlay analytic reference when available.
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
                    ax.plot(
                        x_arr, y_ref, "--", label=f"reference {var}", color="#c45c26"
                    )
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


def page_shell(title: str, body: str, *, root_href: str = ".") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{esc(title)} — benchmark1d2d</title>
  <link rel="stylesheet" href="{root_href}/style.css"/>
</head>
<body>
  <div class="wrap">
    <header class="site">
      <h1>benchmark1d2d</h1>
      <p>Open V&amp;V benchmarks for water solvers</p>
      <nav class="site">
        <a href="{root_href}/index.html">Results</a>
        <a href="{root_href}/methodology.html">Methodology</a>
      </nav>
    </header>
    {body}
    <footer class="site">
      Track A proves equations; Track B proves parity. Tables are never merged.
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
) -> str:
    rows: list[str] = []
    for m in manifests:
        tid = str(m.get("test_id", ""))
        card = scorecards.get(tid)
        title = m.get("title") or tid
        status = m.get("status", "")
        test_class = m.get("test_class", "")
        href = f"tests/{esc(tid)}.html"
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


def build_index(
    manifests: list[dict[str, Any]],
    scorecards: dict[str, dict[str, Any]],
) -> str:
    track_a = [m for m in manifests if m.get("track") == "A"]
    track_b = [m for m in manifests if m.get("track") == "B"]
    other = [m for m in manifests if m.get("track") not in ("A", "B")]

    body = f"""
    <p class="lede">
      Benchmark1d2d certifies solvers on two independent axes. Track A asks whether
      the equations are solved correctly (verification / validation). Track B asks
      whether the solver matches a pinned industry reference engine (parity).
      A solver may pass one track and fail the other — every badge and table
      keeps the tracks apart.
    </p>
    <div class="tracks">
      <section class="track a">
        <h3>Track A — Physics &amp; Verification</h3>
        <p>Ground truth: exact solutions, laboratory and field measurements.
        Can prove the solver is <strong>wrong</strong>.</p>
      </section>
      <section class="track b">
        <h3>Track B — Industry Parity</h3>
        <p>Ground truth: pinned reference-engine output (e.g. SWMM 5.2.4).
        Can only prove the solver <strong>differs</strong>.</p>
      </section>
    </div>

    <h2>Track A results</h2>
    <table class="results">
      <thead>
        <tr><th>Test</th><th>Class</th><th>Status</th><th>Solver</th><th>Result</th></tr>
      </thead>
      <tbody>
        {results_table_rows(track_a, scorecards)}
      </tbody>
    </table>

    <h2>Track B results</h2>
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
    return page_shell("Results", body, root_href=".")


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

    phys_bits = (
        f'<span class="badge">{esc(physics.get("dimensionality"))}</span>'
        f'<span class="badge">{esc(physics.get("flow_type"))}</span>'
        f'<span class="badge">{esc(manifest.get("test_class"))}</span>'
        f'<span class="badge">status: {esc(manifest.get("status"))}</span>'
        f'<span class="badge">track {esc(manifest.get("track"))}</span>'
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
        plot_html = f'<h2>Reference vs solver</h2><img class="plot" src="{esc(tid)}.png" alt="plot for {esc(tid)}"/>'

    body = f"""
    <h2>{esc(manifest.get("title") or tid)}</h2>
    <p class="meta"><code>{esc(tid)}</code> · case v{esc(manifest.get("case_version"))}</p>
    <p>{phys_bits}</p>
    <p>{esc(manifest.get("description") or "")}</p>

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
    return page_shell(tid, body, root_href="..")


def simple_md_to_html(text: str) -> str:
    """Minimal markdown: headings, paragraphs, lists, bold/code."""
    lines = text.splitlines()
    blocks: list[str] = []
    para: list[str] = []
    list_items: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if para:
            joined = " ".join(para)
            joined = html.escape(joined)
            joined = joined.replace("**", "")  # strip leftover markers simply
            blocks.append(f"<p>{joined}</p>")
            para = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            items = "".join(f"<li>{html.escape(i)}</li>" for i in list_items)
            blocks.append(f"<ul>{items}</ul>")
            list_items = []

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            flush_list()
            continue
        if line.startswith("#"):
            flush_para()
            flush_list()
            level = len(line) - len(line.lstrip("#"))
            level = min(max(level, 1), 4)
            content = html.escape(line.lstrip("# ").strip())
            blocks.append(f"<h{level}>{content}</h{level}>")
            continue
        if line.lstrip().startswith(("- ", "* ")):
            flush_para()
            list_items.append(line.lstrip()[2:].strip())
            continue
        flush_list()
        para.append(line.strip())
    flush_para()
    flush_list()
    return "\n".join(blocks)


def build_methodology(root: Path) -> str:
    method_dir = root / "docs" / "methodology"
    parts: list[str] = ["<p class='lede'>How benchmark1d2d sets tolerances and runs V&amp;V.</p>"]
    if method_dir.is_dir():
        for path in sorted(method_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            parts.append(
                f'<section class="method-block"><h2>{esc(path.stem.replace("_", " ").title())}</h2>'
                f"{simple_md_to_html(text)}</section>"
            )
    else:
        parts.append("<p>No methodology documents found.</p>")
    return page_shell("Methodology", "\n".join(parts), root_href=".")


def build(root: Path, scorecards_dir: Path) -> dict[str, int]:
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
    scorecards = discover_scorecards(scorecards_dir)

    (dist / "index.html").write_text(
        build_index(manifests, scorecards), encoding="utf-8"
    )
    (dist / "methodology.html").write_text(
        build_methodology(root), encoding="utf-8"
    )

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
        "index": 1,
        "methodology": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build benchmark1d2d static site")
    parser.add_argument(
        "--scorecards",
        type=Path,
        default=None,
        help="Directory of scorecard JSON files (default: <repo>/out)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: parent of site/)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    score_dir = args.scorecards.resolve() if args.scorecards else root / "out"
    counts = build(root, score_dir)
    pages = counts["index"] + counts["methodology"] + counts["test_pages"]
    print(
        f"Built site/dist: {pages} HTML pages "
        f"({counts['test_pages']} tests, {counts['scorecards']} scorecards, "
        f"{counts['plots']} plots)"
    )
    return 0


if __name__ == "__main__":
    # Fix shebang typo guard — allow running as python site/build.py
    sys.exit(main())
