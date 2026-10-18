"""The key score cards are signed with.

A card's signature says the card has not changed since it was written, and by
whom it was written only if the key is private. The suite's CI signs with the
key in the ``BENCH_SIGNING_KEY`` secret (64 hex characters, an Ed25519 seed)
when it is set. Without it, cards are signed with the **public development
key** (32 bytes of 0x05, in this repository): such a signature proves integrity
against accidental change, not authorship, and the site says so (review F4).
"""

from __future__ import annotations

import os

DEV_SEED = bytes([5] * 32)


def seed() -> bytes:
    v = os.environ.get("BENCH_SIGNING_KEY", "").strip()
    if v:
        b = bytes.fromhex(v)
        if len(b) != 32:
            raise ValueError("BENCH_SIGNING_KEY must be 64 hex characters (an Ed25519 seed)")
        return b
    return DEV_SEED


def private_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(seed())


def is_development() -> bool:
    return seed() == DEV_SEED


def public_keys() -> list[bytes]:
    """Raw public keys a card may be signed with: the CI key (``BENCH_SIGNING_PUBKEY``, hex) and the development key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    raw = serialization.Encoding.Raw, serialization.PublicFormat.Raw
    keys = [Ed25519PrivateKey.from_private_bytes(DEV_SEED).public_key().public_bytes(*raw)]
    v = os.environ.get("BENCH_SIGNING_PUBKEY", "").strip()
    if v:
        keys.insert(0, bytes.fromhex(v))
    return keys
