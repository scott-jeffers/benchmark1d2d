#!/usr/bin/env python3
"""Run the 1D Track A cases with the demo solver and score them (gate script).

Verification cases with ``mesh_refinement.levels`` are solved on every level;
scoring uses the finest result for gating criteria and all levels for GCI /
observed order (ASME V&V 20).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "runner" / "python"))
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "examples" / "demo_solver"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from benchmark1d2d.clock import run_timestamp  # noqa: E402
from benchmark1d2d.catalog import load_manifest
from benchmark1d2d.scoring.scorer import score_case
from solve import run_case

CASES = [
    ("A1F-010", "ritter"),
    ("A1F-011", "stoker"),
    ("A1F-001", "macdonald"),
    ("A1P-020", "joukowsky"),
    ("A1F-020", "belanger"),
    ("A1P-030", "tracer"),
]


def _refinement_levels(manifest: dict) -> list[float]:
    mr = (manifest.get("simulation") or {}).get("mesh_refinement") or {}
    levels = mr.get("levels")
    if levels:
        return [float(x) for x in levels]
    return [10.0]


def main() -> int:
    out_dir = _REPO / "out" / "vertical_slice"
    out_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.from_private_bytes(bytes([9] * 32))
    timestamp = run_timestamp()
    results = []

    for test_id, case in CASES:
        manifest = load_manifest(test_id, repo=_REPO)
        levels = _refinement_levels(manifest)
        # Coarse → fine for discovery; score with fine as primary.
        levels_sorted = sorted(levels, reverse=True)
        paths: list[Path] = []
        print(f"==> solving {manifest['test_id']} ({case}, levels={levels_sorted})")
        for dx in levels_sorted:
            parquet = out_dir / f"{manifest['test_id']}_dx{dx}.parquet"
            run_case(case, dx=dx, t_end=None, out=parquet, manifest=manifest)
            paths.append(parquet)

        finest = paths[-1]  # smallest dx after reverse-sort
        # Also write canonical name expected by the site builder.
        canonical = out_dir / f"{manifest['test_id']}.parquet"
        canonical.write_bytes(finest.read_bytes())

        refinement = paths if len(paths) >= 2 else None
        card = score_case(
            manifest,
            finest,
            refinement_results=refinement,
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
        if card.get("convergence_result"):
            cr = card["convergence_result"]
            mark = "PASS" if cr.get("passed") else "FAIL"
            print(
                f"      [{mark}] convergence: p={cr.get('observed_order')} "
                f"gci={cr.get('gci')} (min_p={cr.get('min_observed_order')})"
            )
        results.append((manifest["test_id"], card["passed"]))

    print("\nSummary:")
    for tid, ok in results:
        print(f"  {tid}: {'PASS' if ok else 'FAIL'}")
    assert len(results) == len(CASES)
    # Gate: every verification case must pass with multi-mesh evidence.
    failed = [tid for tid, ok in results if not ok]
    if failed:
        print(f"GATE FAIL: {failed}")
        return 1
    print("GATE PASS: all cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
