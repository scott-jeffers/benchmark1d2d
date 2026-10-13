#!/usr/bin/env python3
"""Run four Track A cases with the demo solver and score them (gate script)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "runner" / "python"))
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "examples" / "demo_solver"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hydrobench.catalog import load_manifest
from hydrobench.scoring.scorer import score_case
from solve import run_case

CASES = [
    ("A1F-010", "ritter", 10.0),
    ("A1F-011", "stoker", 10.0),
    ("A1F-001", "macdonald", 20.0),
    ("A1P-020", "joukowsky", 10.0),
]


def main() -> int:
    out_dir = _REPO / "out" / "vertical_slice"
    out_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.from_private_bytes(bytes([9] * 32))
    timestamp = "2024-01-01T00:00:00Z"
    results = []

    for test_id, case, dx in CASES:
        manifest = load_manifest(test_id, repo=_REPO)
        parquet = out_dir / f"{manifest['test_id']}.parquet"
        print(f"==> solving {manifest['test_id']} ({case}, dx={dx})")
        run_case(case, dx=dx, t_end=None, out=parquet, manifest=manifest)

        card = score_case(
            manifest,
            parquet,
            timestamp=timestamp,
            private_key=key,
            solver={"name": "demo", "version": "0.1.0", "adapter": "generic_parquet"},
        )
        score_path = out_dir / f"{manifest['test_id']}.scorecard.json"
        score_path.write_text(
            json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        print(f"    passed={card['passed']}  -> {score_path.name}")
        for c in card["criteria_results"]:
            mark = "PASS" if c["passed"] else "FAIL"
            print(f"      [{mark}] {c['id']}: observed={c['observed']}")
        results.append((manifest["test_id"], card["passed"]))

    print("\nSummary:")
    for tid, ok in results:
        print(f"  {tid}: {'PASS' if ok else 'FAIL'}")
    # Gate: all four must produce scorecards; macdonald + joukowsky should pass.
    assert len(results) == 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
