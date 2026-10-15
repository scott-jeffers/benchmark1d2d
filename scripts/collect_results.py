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
PARITY = REPO / "test_catalog" / "track_b" / "parity"

# workflow file -> artifact names to collect (None = all of the run's artifacts)
WORKFLOWS = {
    "open-solvers.yml": None,
    "slow-runs.yml": None,
    "hecras.yml": None,
    "track-a.yml": ["telemac-scorecards", "swmm-track-a-scorecards"],
    "nightly.yml": ["nightly-census"],
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
]
PARITY_FILES = re.compile(r"^(nightly|pr|release)_(?!census)[\w.-]+\.(parquet|summary\.json)$|^epanet_[\w.-]+\.(parquet|summary\.json)$")


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


def summarise_change(old: dict | None, new: dict) -> str | None:
    if old is None:
        return f"new: {'PASS' if new['passed'] else 'FAIL'}"
    if old.get("passed") != new.get("passed"):
        return f"**{'PASS' if old['passed'] else 'FAIL'} → {'PASS' if new['passed'] else 'FAIL'}**"
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

    lines, flips, n_changed = ["# Collected results", ""], 0, 0
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
    lines += ["", f"{n_changed} file(s) changed, {flips} pass/fail change(s)."]
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    # exit status 0 always; the workflow reads the summary to decide on an issue
    (args.summary.with_suffix(".flips")).write_text(str(flips), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
