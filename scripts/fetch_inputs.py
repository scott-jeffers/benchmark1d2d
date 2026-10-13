#!/usr/bin/env python3
"""Fetch non-committed catalog inputs and verify them by SHA-256.

Manifest inputs with ``"committed": false`` carry a ``source`` block:
``url`` (an archive or file), optional ``archive_sha256``, and ``members`` —
the path chain through nested zip archives to the file. This script downloads
each source once (cached under ``.cache/sources/<sha256>``), checks the
archive hash, extracts the member, checks the file hash, and writes it to the
input's ``path`` inside the case folder (those paths are git-ignored).

Usage::

    python scripts/fetch_inputs.py                # every case
    python scripts/fetch_inputs.py A2C-EA5        # cases whose id starts with A2C-EA5
    python scripts/fetch_inputs.py --check        # report what is missing; no downloads
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / ".cache" / "sources"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_source(url: str, expected: str | None) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    if expected:
        cached = CACHE / expected
        if cached.is_file():
            return cached.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d-fetch"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = resp.read()
    got = sha256(data)
    if expected and got != expected.lower():
        raise SystemExit(f"source hash mismatch for {url}: {got} != {expected}")
    (CACHE / got).write_bytes(data)
    return data


def extract(data: bytes, members: list[str]) -> bytes:
    for name in members:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            data = zf.read(name)
    return data


def iter_remote_inputs(selector: str | None):
    for mpath in sorted((REPO / "test_catalog").rglob("manifest.json")):
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        tid = str(manifest.get("test_id", ""))
        if selector and not tid.startswith(selector):
            continue
        for entry in manifest.get("inputs") or []:
            if entry.get("pending"):
                print(f"pending  {tid}: {entry['path']} ({entry['pending'].get('reason', '')[:70]})")
                continue
            if entry.get("committed", True) is False and "source" in entry:
                yield tid, mpath.parent, entry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("selector", nargs="?", help="test id prefix")
    ap.add_argument("--check", action="store_true", help="only report status")
    args = ap.parse_args()

    missing = 0
    sources: dict[str, bytes] = {}
    for tid, case_dir, entry in iter_remote_inputs(args.selector):
        target = case_dir / entry["path"]
        if target.is_file() and sha256(target.read_bytes()) == entry["sha256"].lower():
            print(f"ok       {tid}: {entry['path']}")
            continue
        if args.check:
            print(f"missing  {tid}: {entry['path']}")
            missing += 1
            continue
        src = entry["source"]
        key = src.get("archive_sha256") or src["url"]
        if key not in sources:
            print(f"source   {src['url']}")
            sources[key] = get_source(src["url"], src.get("archive_sha256"))
        data = extract(sources[key], src.get("members") or [])
        got = sha256(data)
        if got != entry["sha256"].lower():
            raise SystemExit(f"{tid}: {entry['path']} hash mismatch: {got} != {entry['sha256']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"fetched  {tid}: {entry['path']} ({len(data):,} bytes)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
