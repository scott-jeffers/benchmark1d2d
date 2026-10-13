"""Phase 5: 2D Thacker analytic writer scores cleanly with refinement."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hydrobench.catalog import find_repo_root, load_manifest
from hydrobench.scoring.scorer import score_case

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "examples" / "demo_solver"))
from solve_2d import run_case  # noqa: E402


@pytest.fixture
def repo_root() -> Path:
    return find_repo_root()


def test_thacker_exact_passes(tmp_path: Path, repo_root: Path):
    manifest = load_manifest("A2A-001", repo=repo_root)
    # Use coarser than catalog for a fast unit test; still multi-level.
    dxs = [0.2, 0.1, 0.05]
    paths = []
    for dx in dxs:
        p = tmp_path / f"thacker_dx{dx}.parquet"
        run_case("thacker", dx=dx, t_end=None, out=p, manifest=manifest, mode="exact")
        paths.append(p)

    card = score_case(
        manifest,
        paths[-1],
        refinement_results=paths,
        timestamp="2024-06-01T00:00:00Z",
        private_key=Ed25519PrivateKey.from_private_bytes(bytes([5] * 32)),
        solver={"name": "demo_2d_exact", "version": "0.1.0", "adapter": "generic_parquet"},
    )
    assert card["passed"] is True
    assert card.get("convergence_result") is not None
    assert card["convergence_result"]["passed"] is True


def test_thacker_perturbed_converges(tmp_path: Path, repo_root: Path):
    manifest = load_manifest("A2A-001", repo=repo_root)
    dxs = [0.2, 0.1, 0.05]
    paths = []
    for dx in dxs:
        p = tmp_path / f"thacker_pert_dx{dx}.parquet"
        run_case(
            "thacker", dx=dx, t_end=None, out=p, manifest=manifest, mode="perturbed"
        )
        paths.append(p)

    card = score_case(
        manifest,
        paths[-1],
        refinement_results=paths,
        timestamp="2024-06-01T00:00:00Z",
        private_key=Ed25519PrivateKey.from_private_bytes(bytes([6] * 32)),
        solver={
            "name": "demo_2d_perturbed",
            "version": "0.1.0",
            "adapter": "generic_parquet",
        },
    )
    assert card["passed"] is True
    cr = card["convergence_result"]
    assert cr is not None
    assert cr["passed"] is True
    assert cr["observed_order"] >= 0.8
