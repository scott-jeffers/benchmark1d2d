#!/usr/bin/env python3
"""Prove SWMM 5.2.4 scores 100% self-parity on B-EXTRAN-001.

Runs the pinned ``runswmm.exe`` twice on the same ``.inp``, asserts byte-
identical ``.rpt`` / ``.out``, adapts both reports to the results contract,
and scores relative peak/volume (must be ~0).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "runner" / "python"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from benchmark1d2d.adapters.swmm5 import adapt_rpt_to_parquet
from benchmark1d2d.catalog import load_manifest
from benchmark1d2d.engines import assert_pin_matches_sha256sums, load_swmm_pin
from benchmark1d2d.scoring.scorer import score_case

BIN = _REPO / "reference_engines" / "swmm-5.2.4" / "bin"
EXE = BIN / "runswmm.exe"
PIN_PATH = _REPO / "reference_engines" / "swmm-5.2.4" / "pin.json"
SUMS = _REPO / "reference_engines" / "swmm-5.2.4" / "SHA256SUMS"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_pin(pin: dict) -> None:
    assert_pin_matches_sha256sums(_REPO)
    binaries = pin.get("binaries") or {}
    for name, expected in binaries.items():
        got = _sha256(BIN / name)
        if got != expected.lower():
            raise SystemExit(f"PIN MISMATCH {name}: {got} != {expected}")
    dll = binaries.get("swmm5.dll", "")
    print(f"PIN OK: SWMM {pin.get('version')} swmm5.dll={dll[:16]}…")


def main() -> int:
    if not EXE.is_file():
        print("SWMM binary missing; fetch USEPA v5.2.4 win64 release first.")
        return 2
    if not PIN_PATH.is_file():
        print(f"Missing pin file: {PIN_PATH}")
        return 2
    pin = load_swmm_pin(_REPO)
    _verify_pin(pin)
    version = str(pin.get("version") or "5.2.4")

    manifest = load_manifest("B-EXTRAN-001", repo=_REPO)
    inp = _REPO / "test_catalog/track_b/tier_pr/B-EXTRAN-001_extran_parity/inputs/network.inp"
    out_dir = _REPO / "out" / "swmm_self_parity"
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = []
    for i in (1, 2):
        rpt = out_dir / f"run{i}.rpt"
        out = out_dir / f"run{i}.out"
        cmd = [str(EXE), str(inp), str(rpt), str(out)]
        print(" ".join(cmd))
        subprocess.run(cmd, check=True, cwd=str(out_dir))
        runs.append((rpt, out))

    r1, o1 = runs[0]
    r2, o2 = runs[1]
    identical = _sha256(r1) == _sha256(r2) and _sha256(o1) == _sha256(o2)
    print(f"byte-identical rpt+out: {identical}")
    if not identical:
        return 1

    pq1 = out_dir / "run1.parquet"
    pq2 = out_dir / "run2.parquet"
    adapt_rpt_to_parquet(r1, pq1)
    adapt_rpt_to_parquet(r2, pq2)

    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))
    card = score_case(
        manifest,
        pq1,
        timestamp="2024-01-01T00:00:00Z",
        private_key=key,
        solver={"name": str(pin.get("engine") or "SWMM"), "version": version, "adapter": "swmm5"},
    )
    # Force parity against the second run's adapted series by reusing identity
    # stub path — relative metrics on identical adapted tables.
    from benchmark1d2d.io.results import read_results_parquet
    from benchmark1d2d.metrics import relative_peak, relative_volume
    import numpy as np

    a = read_results_parquet(pq1)
    b = read_results_parquet(pq2)
    # Align on shared column
    col = "h" if "h" in a.columns else a.columns[0]
    rp = float(relative_peak(a[col].to_numpy(float), b[col].to_numpy(float)))
    rv = float(relative_volume(a[col].to_numpy(float), b[col].to_numpy(float)))
    print(f"relative_peak={rp:.3e} relative_volume={rv:.3e}")
    score_path = out_dir / "B-EXTRAN-001_self_parity.scorecard.json"
    score_path.write_text(
        json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    ok = identical and abs(rp) < 1e-12 and abs(rv) < 1e-12
    print(f"GATE PASS: SWMM {version} 100% self-parity" if ok else "GATE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
