#!/usr/bin/env python3
"""Score the results submitted under ``submissions/``.

Each ``submissions/<slug>/submission.json`` (schema
``schemas/v1/submission.schema.json``) names a solver, who ran it and the
results files for each case. This script validates the submission, checks
that every listed file exists and that the case version matches the catalog,
scores each case with the suite's own scorer (all refinement levels, so the
convergence check runs too) and writes signed score cards to
``out/submitted/<slug>/`` with ``solver.submitted_by`` set. A submission never
carries its own pass/fail.

It prints a Markdown summary (``--summary``) and exits non-zero if any
submission is malformed, so the Submissions check fails on a broken pull
request. Folders starting with ``_`` (the worked example) are scored but
marked as examples; the site skips them.

Cards are signed with the key in ``BENCHMARK1D2D_SIGNING_KEY`` (32-byte hex
Ed25519 seed) when set, otherwise with the public development key.

Usage::

    python scripts/score_submissions.py [--only SLUG ...] [--summary out/submissions.md]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

SUBMISSIONS = REPO / "submissions"
OUT = REPO / "out" / "submitted"
TS = "2024-01-01T00:00:00Z"  # deterministic cards; the submission's own date is in submission.json


def _key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    seed = os.environ.get("BENCHMARK1D2D_SIGNING_KEY")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed) if seed else bytes([5] * 32))


def validate(sub: dict) -> list[str]:
    import jsonschema

    schema = json.loads((REPO / "schemas" / "v1" / "submission.schema.json").read_text(encoding="utf-8"))
    return [f"{'/'.join(map(str, e.path)) or '(top)'}: {e.message}" for e in jsonschema.Draft202012Validator(schema).iter_errors(sub)]


def score_folder(folder: Path, key) -> tuple[list[str], list[str]]:
    """Returns (summary lines, problems)."""
    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.scoring.scorer import score_case

    lines, problems = [], []
    path = folder / "submission.json"
    try:
        sub = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"{folder.name}: cannot read submission.json ({exc})"]
    errs = validate(sub)
    if errs:
        return [], [f"{folder.name}: {e}" for e in errs]
    solver = {"name": f"{sub['solver']['name']} {sub['solver']['version']}", "version": sub["solver"]["version"],
              "adapter": "submitted results" + (f"; options: {sub['solver']['options']}" if sub["solver"].get("options") else ""),
              "submitted_by": sub["submitted_by"]}
    out = OUT / folder.name
    out.mkdir(parents=True, exist_ok=True)
    lines.append(f"### {sub['solver']['name']} {sub['solver']['version']} — submitted by {sub['submitted_by']}"
                 + (" (worked example)" if folder.name.startswith("_") else ""))
    lines.append("")
    for case in sub["cases"]:
        tid = case["test_id"]
        try:
            m = load_manifest(tid, repo=REPO)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{folder.name}/{tid}: no such case ({exc})")
            continue
        if case["case_version"] != m["case_version"]:
            lines.append(f"- {tid}: not scored — submitted for v{case['case_version']}, the catalog is at v{m['case_version']}")
            continue
        files = [folder / f for f in case["results"]]
        missing = [f.name for f in files if not f.is_file()]
        if missing:
            problems.append(f"{folder.name}/{tid}: missing results files {missing}")
            continue
        try:
            card = score_case(m, files[-1], refinement_results=files if len(files) > 1 else None,
                              timestamp=TS, private_key=key, solver=solver)
        except Exception as exc:  # noqa: BLE001 - a results file that cannot be scored is the submitter's to fix
            problems.append(f"{folder.name}/{tid}: could not score ({type(exc).__name__}: {exc})")
            continue
        (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        crit = "; ".join(f"{r['id']} {r['observed']:.4g} {r['threshold']['units']} ({'pass' if r['passed'] else 'FAIL'})"
                         for r in card["criteria_results"] if r.get("observed") is not None)
        conv = card.get("convergence_result") or {}
        if conv:
            order = conv.get("observed_order")
            crit += f"; convergence order {order:.2f}" if order is not None else "; convergence not measured"
        lines.append(f"- **{tid}**: {card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} — {crit}")
    lines.append("")
    return lines, problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="submission folder names to score (default: all)")
    ap.add_argument("--summary", type=Path, default=REPO / "out" / "submissions.md")
    args = ap.parse_args()
    key = _key()
    folders = sorted(p for p in SUBMISSIONS.iterdir() if p.is_dir() and (not args.only or p.name in args.only)) if SUBMISSIONS.is_dir() else []
    md, problems = ["# Submitted results", ""], []
    for f in folders:
        lines, probs = score_folder(f, key)
        md += lines
        problems += probs
    if problems:
        md += ["## Problems", ""] + [f"- {p}" for p in problems] + [""]
    if not folders:
        md.append("No submissions.")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
