#!/usr/bin/env python3
"""Fetch Track B models from HydroCouple by ID and verify SHA-256.

Does not commit large ``.inp`` files. Cache root: ``.cache/track_b/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
UPSTREAM = "https://raw.githubusercontent.com/HydroCouple/openswmm.engine.benchmarks/dev/corpus"
CACHE = _REPO / ".cache" / "track_b"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_one(model_id: str, expected_hash: str | None = None) -> Path:
    """Fetch ``collection/case`` → ``.cache/track_b/<collection>/<case>/model.inp``."""
    if model_id == "B-EXTRAN-001":
        src = _REPO / "test_catalog/track_b/tier_pr/B-EXTRAN-001_extran_parity/inputs/network.inp"
        return src
    parts = model_id.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"expected collection/case, got {model_id!r}")
    collection, case = parts
    dest = CACHE / collection / case / "model.inp"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and expected_hash:
        if _sha256(dest.read_bytes()) == expected_hash:
            return dest
    url = f"{UPSTREAM}/{collection}/{case}/model.inp"
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if expected_hash and _sha256(data) != expected_hash:
        raise SystemExit(f"hash mismatch for {model_id}")
    dest.write_bytes(data)
    print(f"fetched {model_id} sha256={_sha256(data)}")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="pr", choices=["pr", "nightly", "release"])
    ap.add_argument("--limit", type=int, default=5, help="max models to fetch (smoke)")
    args = ap.parse_args()
    sel = json.loads(
        (_REPO / "test_catalog" / "track_b" / f"tier_{args.tier}" / "selection.json").read_text(
            encoding="utf-8"
        )
    )
    ids = sel.get("model_ids") or []
    for mid in ids[: args.limit]:
        path = fetch_one(mid)
        print(f"OK {mid} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
