"""Ed25519-signed, byte-deterministic score cards."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_json(obj: Any) -> bytes:
    """UTF-8 JSON with sorted keys and compact separators (deterministic)."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def content_hash(canonical_bytes: bytes) -> str:
    """SHA-256 hex digest of canonical payload bytes."""
    return hashlib.sha256(canonical_bytes).hexdigest()


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private = Ed25519PrivateKey.generate()
    return private, private.public_key()


def _load_private_key(private_key: Ed25519PrivateKey | bytes | str | None) -> Ed25519PrivateKey:
    if private_key is None:
        return Ed25519PrivateKey.generate()
    if isinstance(private_key, Ed25519PrivateKey):
        return private_key
    raw = private_key
    if isinstance(raw, str):
        raw = bytes.fromhex(raw) if all(c in "0123456789abcdefABCDEF" for c in raw) and len(raw) == 64 else base64.b64decode(raw)
    if len(raw) == 32:
        return Ed25519PrivateKey.from_private_bytes(raw)
    return serialization.load_pem_private_key(raw, password=None)  # type: ignore[return-value]


def sign_bytes(payload: bytes, private_key: Ed25519PrivateKey) -> bytes:
    return private_key.sign(payload)


def _payload_for_hash(card: dict[str, Any]) -> dict[str, Any]:
    """Copy of card with signature.value cleared for hashing/signing."""
    out = json.loads(canonical_json(card).decode("utf-8"))
    sig = out.get("signature")
    if isinstance(sig, dict):
        sig = dict(sig)
        sig["value"] = ""
        out["signature"] = sig
    return out


def build_scorecard(
    *,
    test_id: str,
    track: str,
    solver: dict[str, str],
    catalog_version: str,
    criteria_results: list[dict[str, Any]],
    passed: bool,
    certification_claims: list[str] | None = None,
    case_version: str | None = None,
    convergence_result: dict[str, Any] | None = None,
    score: float | None = None,
    notes: str | None = None,
    timestamp: str | None = None,
    private_key: Ed25519PrivateKey | bytes | str | None = None,
    key_id: str = "benchmark1d2d-dev",
    schema_version: str = "1.0.0",
) -> dict[str, Any]:
    """Build a signed score card. Same inputs + timestamp + key ⇒ identical JSON."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    priv = _load_private_key(private_key)

    card: dict[str, Any] = {
        "schema_version": schema_version,
        "test_id": test_id,
        "track": track,
        "solver": {
            "name": solver["name"],
            "version": solver["version"],
            "adapter": solver["adapter"],
            **({"submitted_by": solver["submitted_by"]} if solver.get("submitted_by") else {}),
        },
        "catalog_version": catalog_version,
        "timestamp": timestamp,
        "criteria_results": criteria_results,
        "passed": bool(passed),
        "certification_claims": list(certification_claims or []),
        "signature": {"alg": "Ed25519", "key_id": key_id, "value": ""},
        "content_hash": "",
    }
    if case_version is not None:
        card["case_version"] = case_version
    if convergence_result is not None:
        card["convergence_result"] = convergence_result
    if score is not None:
        card["score"] = float(score)
    if notes is not None:
        card["notes"] = notes

    payload = _payload_for_hash(card)
    # Hash excludes signature.value (already ""); also exclude content_hash itself
    # by hashing the payload with empty content_hash.
    payload["content_hash"] = ""
    canonical = canonical_json(payload)
    digest = content_hash(canonical)
    signature = sign_bytes(canonical, priv)

    card["content_hash"] = digest
    card["signature"] = {
        "alg": "Ed25519",
        "key_id": key_id,
        "value": base64.b64encode(signature).decode("ascii"),
    }
    # Re-canonicalize to guarantee key order in returned structure matches dumps.
    return json.loads(canonical_json(card).decode("utf-8"))


def verify_scorecard(
    card: dict[str, Any],
    public_key: Ed25519PublicKey | bytes | None = None,
) -> bool:
    """Verify content_hash (and optionally Ed25519 signature)."""
    payload = _payload_for_hash(card)
    payload["content_hash"] = ""
    canonical = canonical_json(payload)
    if content_hash(canonical) != card.get("content_hash"):
        return False
    if public_key is None:
        return True
    if isinstance(public_key, (bytes, bytearray)):
        public_key = Ed25519PublicKey.from_public_bytes(bytes(public_key))
    sig_b64 = card.get("signature", {}).get("value", "")
    try:
        public_key.verify(base64.b64decode(sig_b64), canonical)
    except Exception:
        return False
    return True
