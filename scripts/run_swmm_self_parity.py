#!/usr/bin/env python3
"""Cross-build parity: the official EPA SWMM 5.2.4 Windows binaries vs the committed references.

The Track B references are produced on Linux by the SWMM 5.2.4 engine bundled
in ``swmm-toolkit``. This script runs the pinned official Windows build
(``runswmm.exe``, hashes in ``reference_engines/swmm-5.2.4/pin.json``) on every
SWMM catalog case, adapts its binary output with the same reader, and scores it
against those references. Passing shows the two builds of 5.2.4 agree within
each case's tolerance, so a candidate scored against either is scored against
"SWMM 5.2.4".

It also runs the official binary twice and requires byte-identical output.
Score cards go to ``out/cross_build/`` (job artifact; not merged into the site).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "runner" / "python"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from benchmark1d2d.adapters.swmm5 import adapt_out_to_parquet  # noqa: E402
from benchmark1d2d.catalog import load_manifest  # noqa: E402
from benchmark1d2d.engines import assert_pin_matches_sha256sums, load_swmm_pin  # noqa: E402
from benchmark1d2d.scoring.scorer import score_case  # noqa: E402

BIN = _REPO / "reference_engines" / "swmm-5.2.4" / "bin"
EXE = BIN / "runswmm.exe"
OUT = _REPO / "out" / "cross_build"
CASES = ["B-EXTRAN-001", "B-RTC-001"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not EXE.is_file():
        print("SWMM binary missing; fetch the USEPA v5.2.4 win64 release first (see reference_engines/swmm-5.2.4/README.md).")
        return 2
    pin = load_swmm_pin(_REPO)
    assert_pin_matches_sha256sums(_REPO)
    for name, expected in (pin.get("binaries") or {}).items():
        if _sha256(BIN / name) != expected.lower():
            raise SystemExit(f"PIN MISMATCH {name}")
    print(f"pin OK: official SWMM {pin['version']} binaries")
    OUT.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))
    ok = True
    for tid in CASES:
        m = load_manifest(tid, repo=_REPO)
        inp = Path(m["_case_dir"]) / "inputs" / "network.inp"
        if not inp.is_file():
            subprocess.run([sys.executable, str(_REPO / "scripts" / "fetch_inputs.py"), tid], check=True)
        outs = []
        for i in (1, 2):
            rpt, out = OUT / f"{tid}.run{i}.rpt", OUT / f"{tid}.run{i}.out"
            subprocess.run([str(EXE), str(inp), str(rpt), str(out)], check=True, cwd=str(inp.parent), capture_output=True)
            outs.append(out)
        identical = _sha256(outs[0]) == _sha256(outs[1])
        pq = adapt_out_to_parquet(outs[0], OUT / f"{tid}.official.parquet")
        card = score_case(m, pq, timestamp="2024-01-01T00:00:00Z", private_key=key,
                          solver={"name": f"EPA SWMM {pin['version']} official win64", "version": pin["version"], "adapter": "swmm5"})
        (OUT / f"{tid}.cross_build.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{tid}: repeat runs byte-identical={identical}; vs {m['reference'].get('build')}: {'PASS' if card['passed'] else 'FAIL'}")
        for r in card["criteria_results"]:
            print(f"    {r['id']}: {r['observed']} {r['threshold']['units']} ({r.get('detail', '')})")
        ok &= identical and card["passed"]
    print("CROSS-BUILD PASS" if ok else "CROSS-BUILD FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
