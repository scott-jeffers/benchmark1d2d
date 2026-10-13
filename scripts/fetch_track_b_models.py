#!/usr/bin/env python3
"""Fetch Track B corpus models by tier, pinned to the upstream commit, verified by SHA-256.

Each row of ``test_catalog/track_b/corpus_index.parquet`` records the model's
URL at the pinned HydroCouple commit and its SHA-256; this script downloads
into ``.cache/track_b/<collection>/<case>/model.inp`` and refuses any file
whose hash differs. Models are never committed here.

Usage::

    python scripts/fetch_track_b_models.py --tier pr
    python scripts/fetch_track_b_models.py --tier nightly --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
CACHE = _REPO / ".cache" / "track_b"
INDEX = _REPO / "test_catalog" / "track_b" / "corpus_index.parquet"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_one(model_id: str, url: str, expected_hash: str) -> Path:
    dest = CACHE / model_id / "model.inp"
    if dest.is_file() and _sha256(dest.read_bytes()) == expected_hash:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    got = _sha256(data)
    if got != expected_hash:
        raise SystemExit(f"hash mismatch for {model_id}: {got} != {expected_hash}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="pr", choices=["pr", "nightly", "release"])
    ap.add_argument("--limit", type=int, default=0, help="max models to fetch (0 = all)")
    args = ap.parse_args()
    sel = json.loads((_REPO / "test_catalog" / "track_b" / f"tier_{args.tier}" / "selection.json").read_text(encoding="utf-8"))
    index = pd.read_parquet(INDEX).set_index("model_id")
    ids = sel.get("model_ids") or []
    if args.limit:
        ids = ids[: args.limit]
    for mid in ids:
        row = index.loc[mid]
        path = fetch_one(mid, row["url"], row["hash"])
        print(f"OK {mid} -> {path.relative_to(_REPO)}")
    print(f"{len(ids)} models verified at {sel.get('upstream_commit', '?')[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
