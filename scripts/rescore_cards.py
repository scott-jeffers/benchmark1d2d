#!/usr/bin/env python3
"""Rescore existing score cards from their saved results after a case changes.

For every ``<test_id>.scorecard.json`` of the given case in each directory,
the results Parquet files next to it (``<test_id>_dx<spacing>.parquet``, one
per grid level) are scored again against the current manifest, keeping the
card's solver block and timestamp. Production solvers are not re-run.

Usage::

    python scripts/rescore_cards.py A1F-010 out/telemac out/anuga ... [--copy-to-fixtures]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]


def dx_of(p: Path) -> float:
    return float(p.stem.rsplit("dx", 1)[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("case")
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--fixtures", nargs="*", type=Path, default=[],
                    help="fixture directories, matched to dirs by position, to receive the new cards")
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.scoring.scorer import score_case

    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    m = load_manifest(args.case, repo=REPO)
    tid = m["test_id"]
    for k, d in enumerate(args.dirs):
        card_path = d / f"{tid}.scorecard.json"
        if not card_path.is_file():
            print(f"skip {d}: no card")
            continue
        old = json.loads(card_path.read_text())
        paths = sorted(d.glob(f"{tid}_dx*.parquet"), key=dx_of, reverse=True)
        if not paths:
            print(f"skip {d}: no results")
            continue
        card = score_case(m, paths[-1], refinement_results=paths if len(paths) > 1 else None,
                          timestamp=old["timestamp"], private_key=key, solver=old["solver"])
        text = json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n"
        card_path.write_text(text, encoding="utf-8")
        if k < len(args.fixtures):
            (args.fixtures[k] / card_path.name).write_text(text, encoding="utf-8")
        crit = "; ".join(f"{r['id']} {'ok' if r['passed'] else 'FAIL'} {r['observed']:.3g}" for r in card["criteria_results"])
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {old['solver']['name']}: {crit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
