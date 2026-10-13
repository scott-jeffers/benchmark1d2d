#!/usr/bin/env python3
"""Generate Track B reference results by running the pinned engine.

For every catalog case whose reference is ``pinned_engine``, run the case's
network input on the reference engine and write
``reference/<engine>-<version>.parquet`` (per-element time series), then
record ``results_path`` and ``build`` in the manifest.

Engines:

- ``SWMM`` 5.2.4 — the official engine bundled in ``swmm-toolkit``
- ``EPANET`` 2.2 — the official library bundled in ``wntr`` (``libepanet22``)

Usage::

    python scripts/make_reference.py               # all pinned-engine cases
    python scripts/make_reference.py B-EXTRAN-001  # one case
    python scripts/make_reference.py --check       # fail if a committed reference is stale
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runner" / "python"))

import pandas as pd  # noqa: E402

from benchmark1d2d.adapters import epanet22, swmm5  # noqa: E402


def engine_build(engine: str) -> tuple[str, str]:
    if engine.upper() == "SWMM":
        from importlib.metadata import version

        return swmm5.engine_version(), f"swmm-toolkit {version('swmm-toolkit')} (EPA SWMM {swmm5.engine_version()} engine)"
    if engine.upper() == "EPANET":
        from importlib.metadata import version

        return epanet22.engine_version(), f"wntr {version('wntr')} (EPANET 2.2 library libepanet22)"
    raise SystemExit(f"no reference runner for engine {engine!r}")


def network_input(manifest: dict, case_dir: Path) -> Path:
    for entry in manifest["inputs"]:
        if entry.get("format") == "inp":
            return case_dir / entry["path"]
    raise SystemExit(f"{manifest['test_id']}: no .inp input")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("selector", nargs="?")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    stale = 0
    for mpath in sorted((REPO / "test_catalog").rglob("manifest.json")):
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        ref = manifest.get("reference") or {}
        if ref.get("kind") != "pinned_engine":
            continue
        if args.selector and not manifest["test_id"].startswith(args.selector):
            continue
        case_dir = mpath.parent
        engine = ref["engine"]
        version, build = engine_build(engine)
        if version != ref["version"]:
            raise SystemExit(f"{manifest['test_id']}: engine reports {version}, manifest pins {ref['version']}")
        inp = network_input(manifest, case_dir)
        rel = f"reference/{engine.lower()}-{version}.parquet"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "ref.parquet"
            if engine.upper() == "SWMM":
                swmm5.run_to_parquet(inp, tmp)
            else:
                epanet22.run_to_parquet(inp, tmp)
            new = pd.read_parquet(tmp)
            target = case_dir / rel
            if args.check:
                old = pd.read_parquet(target) if target.is_file() else None
                same = old is not None and old.shape == new.shape and bool(
                    (old.select_dtypes("number").fillna(-1e300) - new.select_dtypes("number").fillna(-1e300)).abs().max().max() < 1e-9
                )
                print(("ok      " if same else "STALE   ") + manifest["test_id"])
                stale += 0 if same else 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            new.to_parquet(target, index=False, compression="zstd")
        ref["results_path"] = rel
        ref["build"] = build
        mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
        print(f"wrote   {manifest['test_id']}: {rel} ({len(new):,} rows, sha256 {digest}…) via {build}")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
