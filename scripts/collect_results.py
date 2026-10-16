#!/usr/bin/env python3
"""Collect the latest CI results into the site's fixtures.

Several solvers only run in scheduled or Windows workflows (open-source
solvers, slow runs, HEC-RAS, Track A jobs, the nightly corpus parity). This
script finds each workflow's latest successful run on ``master``, downloads
its artifacts with the GitHub CLI, verifies every score card's signature, and
files it under ``site/fixtures/`` by the solver named inside the card, so the
site never shows results older than the last good run. Nightly parity tables
go to ``test_catalog/track_b/parity/``.

It writes a Markdown summary of what changed (new cards, changed pass/fail,
moved numbers) to ``--summary``; the collect-results workflow commits the
changes and opens an issue when a pass/fail result changes.

Usage (needs ``gh`` authenticated for the repository)::

    python scripts/collect_results.py [--repo owner/name] [--summary out/collect.md] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

FIXTURES = REPO / "site" / "fixtures"
CURVES = FIXTURES / "curves"
INPUTS = FIXTURES / "inputs"  # model files per test and model (scripts/export_inputs.py)
NEWS = FIXTURES / "news.jsonl"  # one line per collection that changed something: the site's "What's new" page  # chart extracts (scripts/export_curves.py), one per test and model
PARITY = REPO / "test_catalog" / "track_b" / "parity"

# workflow file -> artifact names to collect (None = all of the run's artifacts)
WORKFLOWS = {
    "open-solvers.yml": None,
    "slow-runs.yml": None,
    "hecras.yml": None,
    "track-a.yml": ["telemac-scorecards", "swmm-track-a-scorecards"],
    "nightly.yml": ["nightly-census"],
    "bellinge.yml": None,
}

# solver name (from the card) -> fixture directory, first match wins
ROUTES = [
    (r"^openTELEMAC", "telemac"),
    (r"^ANUGA", "anuga"),
    (r"^GeoClaw", "geoclaw"),
    (r"^LISFLOOD-FP .*\bFV1\b", "lisflood/fv1"),
    (r"^LISFLOOD-FP .*\bDG2\b", "lisflood/dg2"),
    (r"^LISFLOOD-FP .*\bACC\b", "lisflood/acc"),
    (r"^HEC-RAS .*2D SWE-ELM", "hecras2d/elm"),
    (r"^HEC-RAS .*2D SWE-EM", "hecras2d/em"),
    (r"^HEC-RAS", "hecras"),
    (r"^HydroNet FVM-PINN", "hydronet/pinn"),
    (r"^HydroNet finite volume", "hydronet/fvm"),
    (r"^EPA SWMM 5\.2\.4$", "swmm_track_a/swmm524"),
    (r"^OpenSWMM Engine v6 dynamic wave", "swmm_track_a/openswmm-dw"),
    (r"^OpenSWMM Engine v6 finite volume", "swmm_track_a/openswmm-fv"),
    (r"^Hydra urban drainage \(", "swmm_track_a/hydra-uds"),
    (r"^SWMM–ANUGA coupled", "coupled/swmm-anuga"),
    (r"^OpenSWMM Engine v6 1D/2D \(four", "coupled/openswmm-2d-x"),
    (r"^OpenSWMM Engine v6 1D/2D", "coupled/openswmm-2d"),
]
HISTORY = PARITY / "history.csv"
HISTORY_COLS = ["date", "run", "tier", "candidate", "candidate_version", "upstream_commit", "models", "scored",
                "within_1pct", "within_5pct", "candidate_error", "median_worst_pct"]
# a nightly parity change worth an issue: this many models moving in or out of "within 1 %",
# or any change in the number the candidate cannot run
SHIFT_MODELS = 5
PARITY_FILES = re.compile(r"^(nightly|pr|release|bellinge)_(?!census)[\w.-]+\.(parquet|summary\.json)$|^epanet_[\w.-]+\.(parquet|summary\.json)$")


def gh(*args: str, check: bool = True) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {p.stderr.strip()[:400]}")
    return p.stdout


def latest_run(repo: str, workflow: str) -> dict | None:
    out = gh("run", "list", "-R", repo, "--workflow", workflow, "--branch", "master", "--status", "success",
             "--limit", "1", "--json", "databaseId,headSha,createdAt,displayTitle")
    runs = json.loads(out or "[]")
    return runs[0] if runs else None


def route(card: dict) -> str | None:
    name = (card.get("solver") or {}).get("name", "")
    for pat, d in ROUTES:
        if re.search(pat, name):
            return d
    return None


def verify(card: dict) -> bool:
    """Content hash and the suite's public development-key signature."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.scoring.scorecard import verify_scorecard

    pub = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32)).public_key()
    try:
        return bool(verify_scorecard(card, pub))
    except Exception:  # noqa: BLE001
        return False


_VERSIONS: dict[str, str | None] = {}


def case_version(test_id: str) -> str | None:
    """The catalog's current version of a case (cards from older versions are not collected)."""
    if test_id not in _VERSIONS:
        from benchmark1d2d.catalog import load_manifest

        try:
            _VERSIONS[test_id] = load_manifest(test_id.split("_")[0], repo=REPO)["case_version"]
        except Exception:  # noqa: BLE001
            _VERSIONS[test_id] = None
    return _VERSIONS[test_id]


def history_row(summary: dict, run: dict) -> dict:
    st = summary.get("status") or {}
    w = summary.get("within_pct") or {}
    return {"date": run["createdAt"][:10], "run": str(run["databaseId"]), "tier": summary.get("tier", ""),
            "candidate": summary.get("candidate", ""), "candidate_version": summary.get("candidate_version", ""),
            "upstream_commit": (summary.get("upstream_commit") or "")[:7], "models": summary.get("models", ""),
            "scored": st.get("scored", ""), "within_1pct": w.get("1", ""), "within_5pct": w.get("5", ""),
            "candidate_error": st.get("candidate_error", 0), "median_worst_pct": summary.get("median_worst_pct", "")}


def append_history(row: dict, dry_run: bool) -> str | None:
    """Append a nightly parity summary to history.csv; describe a shift from the previous run, if any."""
    import csv

    rows = []
    if HISTORY.is_file():
        with HISTORY.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    if any(r["run"] == row["run"] and r["candidate"] == row["candidate"] and r["tier"] == row["tier"] for r in rows):
        return None
    prev = next((r for r in reversed(rows) if r["candidate"] == row["candidate"] and r["tier"] == row["tier"]), None)
    shift = None
    if prev is not None:
        try:
            d1 = int(row["within_1pct"]) - int(prev["within_1pct"])
            de = int(row["candidate_error"] or 0) - int(prev["candidate_error"] or 0)
        except (TypeError, ValueError):
            d1 = de = 0
        if abs(d1) >= SHIFT_MODELS or de != 0 or row["candidate_version"] != prev["candidate_version"]:
            shift = (f"**{row['candidate']} ({row['tier']}) parity shift**: within 1 % {prev['within_1pct']} → {row['within_1pct']}, "
                     f"cannot run {prev['candidate_error'] or 0} → {row['candidate_error'] or 0}"
                     + (f", version {prev['candidate_version']} → {row['candidate_version']}" if row["candidate_version"] != prev["candidate_version"] else ""))
    if not dry_run:
        new = not HISTORY.is_file()
        with HISTORY.open("a", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=HISTORY_COLS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerow(row)
    return shift


def record_news(lines: list[str]) -> None:
    """Append what changed, per workflow, to the site's news log."""
    from datetime import datetime, timezone

    items, wf = [], None
    for ln in lines:
        if ln.startswith("- `"):
            wf = ln.split("`")[1]
        elif ln.startswith("  - ") and not ln.startswith(("  - skipped", "  - REJECTED")):
            items.append({"workflow": wf, "text": ln[4:]})
    if not items:
        return
    entry = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "items": items}
    with NEWS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def card_verdict(card: dict) -> str:
    """PASS, FAIL or INCONCLUSIVE under scoring method 2; a method-1 card is re-judged (on a copy)."""
    from benchmark1d2d.scoring import method_v2

    return method_v2.apply(json.loads(json.dumps(card, default=str)))["verdict"].upper()


def summarise_change(old: dict | None, new: dict) -> str | None:
    if old is None:
        return f"new: {card_verdict(new)}"
    if card_verdict(old) != card_verdict(new):
        return f"**{card_verdict(old)} → {card_verdict(new)}**"
    a = {r["id"]: r.get("observed") for r in old.get("criteria_results", [])}
    b = {r["id"]: r.get("observed") for r in new.get("criteria_results", [])}
    moved = [k for k in b if isinstance(b[k], (int, float)) and isinstance(a.get(k), (int, float))
             and abs(b[k] - a[k]) > 1e-6 * max(1.0, abs(a[k]))]
    if moved or old.get("solver") != new.get("solver") or old.get("case_version") != new.get("case_version"):
        return "updated (" + ", ".join(moved or ["version"]) + ")"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default="scott-jeffers/benchmark1d2d")
    ap.add_argument("--summary", type=Path, default=REPO / "out" / "collect_results.md")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lines, flips, n_changed, n_curves, n_inputs = ["# Collected results", ""], 0, 0, 0, 0
    for wf, wanted in WORKFLOWS.items():
        run = latest_run(args.repo, wf)
        if run is None:
            lines.append(f"- `{wf}`: no successful run on master")
            continue
        lines.append(f"- `{wf}`: run {run['databaseId']} ({run['createdAt'][:10]}, {run['headSha'][:7]})")
        with tempfile.TemporaryDirectory() as td:
            dl = ["run", "download", str(run["databaseId"]), "-R", args.repo, "-D", td]
            for name in wanted or []:
                dl += ["-n", name]
            gh(*dl, check=False)
            for path in sorted(Path(td).rglob("*")):
                if path.is_file() and PARITY_FILES.match(path.name):
                    dest = PARITY / path.name
                    if not dest.is_file() or dest.read_bytes() != path.read_bytes():
                        lines.append(f"  - parity table `{path.name}` updated")
                        n_changed += 1
                        if not args.dry_run:
                            shutil.copyfile(path, dest)
                    if path.name.endswith(".summary.json") and path.name.startswith("nightly_"):
                        shift = append_history(history_row(json.loads(path.read_text(encoding="utf-8")), run), args.dry_run)
                        if shift:
                            lines.append(f"  - {shift}")
                            flips += 1
                    continue
                if path.name.endswith(".inputs.zip"):  # the model files a runner wrote (Run it yourself)
                    sid, _, key = path.name[: -len(".inputs.zip")].partition(".")
                    dest = INPUTS / sid / f"{key}.zip"
                    if key and (not dest.is_file() or dest.read_bytes() != path.read_bytes()):
                        n_inputs += 1
                        if not args.dry_run:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(path, dest)
                    continue
                if path.name.endswith(".curve.json"):
                    try:
                        rec = json.loads(path.read_text(encoding="utf-8"))
                        sid, key = rec["test_id"].split("_")[0], rec["key"]
                    except (ValueError, KeyError):
                        continue
                    if case_version(rec["test_id"]) not in (None, rec.get("case_version")):
                        continue
                    dest = CURVES / sid / f"{key}.json"
                    if not dest.is_file() or dest.read_bytes() != path.read_bytes():
                        n_curves += 1
                        if not args.dry_run:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(path, dest)
                    continue
                if not path.name.endswith(".scorecard.json"):
                    continue
                card = json.loads(path.read_text(encoding="utf-8"))
                d = route(card)
                if d is None:
                    continue
                current = case_version(card["test_id"])
                if current and card.get("case_version") != current:
                    lines.append(f"  - skipped `{path.name}` ({card['solver']['name']}): case v{card.get('case_version')}, catalog v{current}")
                    continue
                if not verify(card):
                    lines.append(f"  - REJECTED (signature) `{path.name}` from {card['solver']['name']}")
                    continue
                dest = FIXTURES / d / path.name
                old = json.loads(dest.read_text(encoding="utf-8")) if dest.is_file() else None
                change = summarise_change(old, card)
                if change is None:
                    continue
                n_changed += 1
                flips += change.startswith("**")
                lines.append(f"  - {card['test_id']} · {card['solver']['name']}: {change}")
                if not args.dry_run:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    lines += ["", f"{n_changed} file(s) changed, {flips} pass/fail change(s), {n_curves} chart curve(s) updated, {n_inputs} model-file zip(s) updated."]
    if n_changed and not args.dry_run:
        record_news(lines)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    # exit status 0 always; the workflow reads the summary to decide on an issue
    (args.summary.with_suffix(".flips")).write_text(str(flips), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
