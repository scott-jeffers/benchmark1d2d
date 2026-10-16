#!/usr/bin/env python3
"""Fetch and check the Bellinge EPA SWMM model (Pedersen et al. 2021, CC BY 4.0).

``fetch`` downloads item 7 (Models, SWMM) of the Bellinge data set from DTU
Data, checks the published MD5, records the SHA-256, unpacks it under
``<out>/model/`` and writes an inventory. ``run`` runs every ``.inp`` it
finds once in EPA SWMM 5.2.4 (swmm-toolkit) and records the run time and the
report's continuity errors.

DTU's file store is not reachable from the build sandbox, so this runs in CI
(``.github/workflows/bellinge.yml``).

Usage::

    python scripts/bellinge.py fetch --out out/bellinge
    python scripts/bellinge.py run --out out/bellinge [--timeout 3000]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

_RUN = (
    "import sys\n"
    "from swmm.toolkit import solver\n"
    "solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n"
)


def network_input() -> dict:
    from benchmark1d2d.catalog import load_manifest

    m = load_manifest("A1F-100", repo=REPO)
    return next(e for e in m["inputs"] if e["role"] == "network")


def fetch(out: Path) -> None:
    entry = network_input()
    url, md5_expected = entry["source"]["url"], entry["source"].get("md5")
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / Path(entry["path"]).name
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d (github.com/scott-jeffers/benchmark1d2d)"})
    with urllib.request.urlopen(req, timeout=600) as r, zpath.open("wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    data = zpath.read_bytes()
    md5, sha = hashlib.md5(data).hexdigest(), hashlib.sha256(data).hexdigest()
    info = {"url": url, "bytes": len(data), "md5": md5, "md5_expected": md5_expected,
            "md5_ok": (md5 == md5_expected) if md5_expected else None, "sha256": sha,
            "seconds": round(time.perf_counter() - t0, 1)}
    print(json.dumps(info, indent=1))
    if md5_expected and md5 != md5_expected:
        raise SystemExit("MD5 does not match the published value")
    dest = out / "model"
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
        lines = [f"{zi.file_size:>12,d}  {zi.filename}" for zi in z.infolist() if not zi.is_dir()]
    (out / "inventory.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    info["inp_files"] = sorted(str(p.relative_to(dest)) for p in dest.rglob("*.inp"))
    (out / "fetch.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    zpath.unlink()  # the archive itself is not needed once unpacked and hashed
    print(f"{len(lines)} files; .inp: {info['inp_files']}")


def continuity(rpt: Path) -> dict:
    text = rpt.read_text(encoding="latin-1", errors="replace") if rpt.is_file() else ""
    errs = re.findall(r"Continuity Error \(%\) \.+\s+(-?[\d.]+)", text)
    keys = ["runoff", "routing"] if len(errs) >= 2 else ["routing"]
    out = {k: float(v) for k, v in zip(keys, errs[-len(keys):])} if errs else {}
    m = re.search(r"Version\s+([\d.]+)", text)
    if m:
        out["version"] = m.group(1)
    return out


def run(out: Path, timeout: float) -> None:
    dest = out / "model"
    results = []
    for inp in sorted(dest.rglob("*.inp")):
        rpt, bin_ = inp.with_suffix(".rpt"), out / (inp.stem + ".out")
        t0 = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, "-c", _RUN, str(inp), str(rpt), str(bin_)], cwd=inp.parent,
                               capture_output=True, text=True, timeout=timeout)
            status = "ran" if p.returncode == 0 else f"exit {p.returncode}: {(p.stderr or p.stdout)[-300:]}"
        except subprocess.TimeoutExpired:
            status = f"timeout after {timeout:g} s"
        rec = {"inp": str(inp.relative_to(dest)), "status": status, "seconds": round(time.perf_counter() - t0, 1),
               "continuity_pct": continuity(rpt), "out_bytes": bin_.stat().st_size if bin_.is_file() else 0}
        if rpt.is_file():
            (out / (inp.stem + ".rpt")).write_text(rpt.read_text(encoding="latin-1", errors="replace"), encoding="utf-8")
        if bin_.is_file():
            bin_.unlink()  # large; the parity job re-runs it
        results.append(rec)
        print(json.dumps(rec))
    (out / "run.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=["fetch", "run"])
    ap.add_argument("--out", type=Path, default=REPO / "out" / "bellinge")
    ap.add_argument("--timeout", type=float, default=3000)
    a = ap.parse_args()
    fetch(a.out) if a.action == "fetch" else run(a.out, a.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
