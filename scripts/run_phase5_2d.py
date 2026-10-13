#!/usr/bin/env python3
"""Phase 5 gate: score Thacker (and optionally all A2A cases) with two solvers.

Independent MVP solvers (see ``examples/demo_solver/solve_2d.py``):

1. **exact** — analytic sample writer (machine-zero L1 vs. reference).
2. **perturbed** — deliberately O(dx)-diffused exact field that still converges
   under mesh refinement (MVP stand-in for a first-order 2D FV scheme).

Primary gate: A2A-001 Thacker with mesh refinement + convergence evidence for
both solvers. MacDonald 2D and oblique jump are scored with the exact writer.
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

from hydrobench.catalog import load_manifest
from hydrobench.scoring.scorer import score_case
from solve_2d import run_case

# (short_id, case_key, modes_to_run)
CASES = [
    ("A2A-001", "thacker", ("exact", "perturbed")),
    ("A2A-010", "macdonald_2d", ("exact",)),
    ("A2A-020", "oblique_jump", ("exact",)),
]


def _refinement_levels(manifest: dict) -> list[float]:
    mr = (manifest.get("simulation") or {}).get("mesh_refinement") or {}
    levels = mr.get("levels")
    if levels:
        return [float(x) for x in levels]
    return [0.1]


def main() -> int:
    out_dir = _REPO / "out" / "phase5_2d"
    out_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.from_private_bytes(bytes([11] * 32))
    timestamp = "2024-01-01T00:00:00Z"
    results: list[tuple[str, str, bool]] = []

    for test_id, case, modes in CASES:
        manifest = load_manifest(test_id, repo=_REPO)
        levels = _refinement_levels(manifest)
        levels_sorted = sorted(levels, reverse=True)  # coarse → fine

        for mode in modes:
            tag = f"{manifest['test_id']}_{mode}"
            paths: list[Path] = []
            print(f"==> solving {tag} (levels={levels_sorted})")
            for dx in levels_sorted:
                parquet = out_dir / f"{tag}_dx{dx}.parquet"
                run_case(
                    case,
                    dx=dx,
                    t_end=None,
                    out=parquet,
                    manifest=manifest,
                    mode=mode,
                )
                paths.append(parquet)

            finest = paths[-1]
            canonical = out_dir / f"{tag}.parquet"
            canonical.write_bytes(finest.read_bytes())

            solver_name = "demo_2d_exact" if mode == "exact" else "demo_2d_perturbed"
            card = score_case(
                manifest,
                finest,
                refinement_results=paths if len(paths) >= 2 else None,
                timestamp=timestamp,
                private_key=key,
                solver={
                    "name": solver_name,
                    "version": "0.1.0",
                    "adapter": "generic_parquet",
                },
            )
            score_path = out_dir / f"{tag}.scorecard.json"
            score_path.write_text(
                json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                + "\n",
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
            results.append((tag, mode, bool(card["passed"])))

    print("\nSummary:")
    for tag, mode, ok in results:
        print(f"  {tag}: {'PASS' if ok else 'FAIL'}")

    # Gate: Thacker exact + perturbed must both pass with multi-mesh evidence.
    thacker = [r for r in results if r[0].startswith("A2A-001")]
    failed = [r[0] for r in thacker if not r[2]]
    if failed:
        print(f"GATE FAIL (Thacker): {failed}")
        return 1
    if len(thacker) < 2:
        print("GATE FAIL: expected both exact and perturbed Thacker runs")
        return 1
    print(
        "GATE PASS: Thacker exact + perturbed passed "
        "(MVP second solver = O(dx)-perturbed exact; converges at first order)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
