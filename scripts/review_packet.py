#!/usr/bin/env python3
"""Write the outside-review packet: every case, its truth, its limits and its results.

``docs/review/packet.md`` is generated from the manifests and the published
score cards, so it always matches the catalog. For each case it lists the
reference and its source, every check with its limit and the stated reason,
which models pass and fail, and what the case still needs before it can be
frozen. Reviewers read it next to ``docs/review/README.md`` (what we ask them
to check and how to send their review).

Usage::

    python scripts/review_packet.py [--out docs/review/packet.md]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "site")]

CARD_DIRS = ["site/fixtures"]


def _ref(m: dict) -> str:
    r = m["reference"]
    k = r["kind"]
    if k == "analytic":
        g = r["generator"]
        return f"exact solution, `{g['module']}.{g['function']}`"
    if k in ("intercomparison", "exact_states"):
        return ("exact states from conservation" if k == "exact_states" else "objective expected states") + ": " + "; ".join(
            f"{s['id']} = {s['value']:g} {s['units']}" for s in r["expected_states"])
    if k == "pinned_engine":
        return f"pinned engine {r.get('engine')} {r.get('version')}"
    return f"measurements ({str(r.get('availability', '')).replace('_', ' ')})"


def _cite(m: dict) -> str:
    out = []
    for c in m["provenance"].get("citations", []):
        a = c.get("authors") or []
        who = a[0].split(",")[0] + (" et al." if len(a) > 2 else (" and " + a[1].split(",")[0] if len(a) == 2 else "")) if a else ""
        link = f" doi:{c['doi']}" if c.get("doi") else ""
        out.append(f"{who} ({c.get('year', '')}){link}")
    return "; ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "review" / "packet.md")
    args = ap.parse_args()

    import pages  # site/pages.py: solver names and run loading
    from benchmark1d2d.catalog import list_catalog, load_manifest
    from benchmark1d2d.catalog.promotion import next_stage

    runs = pages.load_runs([REPO / d for d in CARD_DIRS])
    manifests = sorted((load_manifest(c["test_id"], repo=REPO) for c in list_catalog(repo=REPO)), key=lambda m: m["test_id"])
    status = Counter(m["status"] for m in manifests)
    lines = ["# Outside-review packet", "",
             f"Generated from the catalog ({len(manifests)} cases: {status.get('frozen', 0)} frozen, "
             f"{status.get('candidate', 0)} candidate, {status.get('draft', 0)} draft) and the published score cards. "
             "Read `docs/review/README.md` first: it says what we ask reviewers to check and how to send a review.", ""]
    for m in manifests:
        sid = m["test_id"].split("_")[0]
        if m["status"] == "draft":
            continue
        lines += [f"## {sid} — {m['title']}", "", f"*{m['test_class'].replace('_', ' ')}, version {m['case_version']}, {m['status']}.* {m['description']}", "",
                  f"**Reference:** {_ref(m)}.", f"**Sources:** {_cite(m)}.", "",
                  "| Check | Metric | Limit | Gating | Why this limit |", "|---|---|---|---|---|"]
        for c in m["scoring"]["criteria"]:
            t = c["threshold"]
            lines.append(f"| {c['id']} | {c['metric']} of {c.get('variable', '')} | {t['op']} {t['value']:g} {t.get('units', '')} | "
                         f"{'yes' if c.get('gating') else 'no'} | {c.get('rationale', '').replace('|', '/')} |")
        conv = m["scoring"].get("convergence") or {}
        if conv.get("not_applicable"):
            lines += ["", f"Convergence: not applicable — {conv['not_applicable']}"]
        elif conv:
            lines += ["", f"Convergence: {conv.get('norm')} of {conv.get('variable')}, expected order {conv.get('expected_order')}, "
                          f"at least {conv.get('min_observed_order')} required."]
        by = runs.get(m["test_id"]) or {}
        if by:
            ok = [pages.SOLVER[k]["name"] + " " + pages.SOLVER[k]["sub"] for k in pages.SOLVERS_ORDER(by) if by[k].get("passed")]
            bad = [pages.SOLVER[k]["name"] + " " + pages.SOLVER[k]["sub"] for k in pages.SOLVERS_ORDER(by) if not by[k].get("passed")]
            lines += ["", f"**Passes:** {', '.join(ok) or 'none'}.  ", f"**Fails:** {', '.join(bad) or 'none'}."]
        need = [f"{b['label'].lower()} ({b['detail']})" for b in next_stage(m, list(by.values()))["blockers"]]
        if need:
            lines += ["", f"**Before it can be frozen:** {'; '.join(need)}."]
        lines.append("")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out.relative_to(REPO)} ({sum(1 for m in manifests if m['status'] != 'draft')} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
