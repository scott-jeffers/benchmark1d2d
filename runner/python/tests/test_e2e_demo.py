"""End-to-end: demo solver → scorecard structure (gating may fail on coarse mesh)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hydrobench.catalog import find_repo_root, load_manifest
from hydrobench.scoring.scorer import score_case

# Import demo solver helpers
_REPO = Path(__file__).resolve().parents[3]
import sys

sys.path.insert(0, str(_REPO / "examples" / "demo_solver"))
from solve import run_case  # noqa: E402


@pytest.fixture
def repo_root() -> Path:
    return find_repo_root()


def test_e2e_ritter_scorecard_structure(tmp_path: Path, repo_root: Path):
    out = tmp_path / "ritter.parquet"
    run_case("ritter", dx=20.0, t_end=60.0, out=out, manifest=None)
    assert out.is_file()

    manifest = load_manifest("A1F-010", repo=repo_root)
    seed = bytes([7] * 32)
    key = Ed25519PrivateKey.from_private_bytes(seed)
    card = score_case(
        manifest,
        out,
        timestamp="2024-06-01T00:00:00Z",
        private_key=key,
        solver={"name": "demo", "version": "0.1.0", "adapter": "generic_parquet"},
    )

    assert card["test_id"].startswith("A1F-010")
    assert card["track"] == "A"
    assert isinstance(card["passed"], bool)
    assert isinstance(card["criteria_results"], list) and len(card["criteria_results"]) >= 1
    for c in card["criteria_results"]:
        assert "id" in c and "metric" in c and "observed" in c
        assert "passed" in c and "gating" in c
        assert "threshold" in c
    assert "signature" in card and card["signature"]["alg"] == "Ed25519"
    assert len(card["content_hash"]) == 64
    # Round-trip JSON
    raw = json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert json.loads(raw)["content_hash"] == card["content_hash"]


def test_e2e_ritter_refinement_observed_order(tmp_path: Path, repo_root: Path):
    manifest = load_manifest("A1F-010", repo=repo_root)
    dxs = [40.0, 20.0, 10.0]
    paths = []
    for dx in dxs:
        p = tmp_path / f"ritter_dx{dx}.parquet"
        run_case("ritter", dx=dx, t_end=60.0, out=p, manifest=manifest)
        paths.append(p)

    card = score_case(
        manifest,
        paths[-1],
        refinement_results=paths,
        timestamp="2024-06-01T00:00:00Z",
        private_key=Ed25519PrivateKey.from_private_bytes(bytes([3] * 32)),
        solver={"name": "demo", "version": "0.1.0", "adapter": "generic_parquet"},
    )
    assert card.get("convergence_result") is not None
    cr = card["convergence_result"]
    assert "observed_order" in cr
    assert isinstance(cr["observed_order"], float)
    assert cr["norm"] == "L1"
    assert cr["variable"] == "h"
