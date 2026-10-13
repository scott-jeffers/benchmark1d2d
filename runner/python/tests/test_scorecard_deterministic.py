"""Score cards with fixed timestamp + key must be byte-identical."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from benchmark1d2d.scoring.scorecard import build_scorecard, canonical_json


def test_scorecard_byte_identical_with_fixed_key_and_timestamp():
    # Fixed 32-byte seed for Ed25519 private key (deterministic fixtures).
    seed = bytes(range(32))
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    timestamp = "2024-01-15T12:00:00Z"

    kwargs = dict(
        test_id="A1F-010_ritter_dry_bed_dambreak",
        track="A",
        case_version="1.0.0",
        solver={"name": "demo", "version": "0.1.0", "adapter": "generic_parquet"},
        catalog_version="0.1.0",
        criteria_results=[
            {
                "id": "front_position",
                "metric": "front_position_error",
                "variable": "h",
                "observed": 1.25,
                "threshold": {"op": "abs<=", "value": 2.5, "units": "m"},
                "passed": True,
                "gating": True,
            }
        ],
        passed=True,
        certification_claims=["A-V"],
        timestamp=timestamp,
        private_key=private_key,
        key_id="fixture-key",
    )

    card1 = build_scorecard(**kwargs)
    card2 = build_scorecard(**kwargs)
    b1 = canonical_json(card1)
    b2 = canonical_json(card2)
    assert b1 == b2
    assert card1["content_hash"] == card2["content_hash"]
    assert card1["signature"]["value"] == card2["signature"]["value"]
    assert len(card1["content_hash"]) == 64
