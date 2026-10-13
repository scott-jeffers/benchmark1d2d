#!/usr/bin/env python3
"""Run the pinned SWMM 5.2.4 engine over the federated Track B corpus.

For every ``model.inp`` in a HydroCouple ``openswmm.engine.benchmarks``
checkout, run EPA SWMM 5.2.4 (via ``swmm-toolkit``, which bundles the
official 5.2.4 engine) in an isolated subprocess and record:

- whether it ran, the engine error code, and wall-clock runtime
- runoff / flow-routing / quality continuity error (%) from the report

The census is what tier selection is built from: a model joins a tier only
if it actually runs on the reference engine, and the measured runtime
decides which tier can afford it.

Usage::

    python scripts/corpus_census.py --corpus ../hc/corpus --out test_catalog/track_b/corpus_census.parquet
    python scripts/corpus_census.py --corpus ../hc/corpus --limit 20 --timeout 60
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

_RUN = (
    "import sys\n"
    "from swmm.toolkit import solver\n"
    "try:\n"
    "    solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n"
    "    print('OK')\n"
    "except Exception as exc:\n"
    "    print('ERR', exc)\n"
    "    sys.exit(3)\n"
)

_CONT = {
    "runoff": re.compile(r"Runoff Quantity Continuity.*?Continuity Error \(%\)\s*\.*\s*(-?[\d.]+)", re.S),
    "routing": re.compile(r"Flow Routing Continuity.*?Continuity Error \(%\)\s*\.*\s*(-?[\d.]+)", re.S),
}
_ERR = re.compile(r"ERROR\s+(\d+)")


def engine_version() -> str:
    from swmm.toolkit import solver

    return str(solver.swmm_version_info())


def _continuity(rpt_text: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key, rx in _CONT.items():
        m = rx.search(rpt_text)
        out[f"continuity_{key}_pct"] = float(m.group(1)) if m else None
    return out


def run_one(inp: Path, timeout: float) -> dict:
    rec: dict = {"status": "error", "runtime_s": None, "error_codes": ""}
    with tempfile.TemporaryDirectory() as td:
        rpt = Path(td) / "model.rpt"
        out = Path(td) / "model.out"
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-c", _RUN, str(inp), str(rpt), str(out)],
                cwd=str(inp.parent),
                capture_output=True,
                timeout=timeout,
            )
            rec["runtime_s"] = round(time.perf_counter() - t0, 3)
            text = rpt.read_text(encoding="latin-1", errors="replace") if rpt.is_file() else ""
            codes = sorted(set(_ERR.findall(text)))
            rec["error_codes"] = ",".join(codes)
            rec.update(_continuity(text))
            if proc.returncode == 0 and not codes:
                rec["status"] = "ran"
            elif codes:
                rec["status"] = "input_error"
            else:
                rec["status"] = "engine_error"
        except subprocess.TimeoutExpired:
            rec["status"] = "timeout"
            rec["runtime_s"] = float(timeout)
        except Exception as exc:  # one bad model must never stop the census
            rec["status"] = "harness_error"
            rec["error_codes"] = type(exc).__name__
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", type=Path, required=True, help="HydroCouple corpus/ directory")
    ap.add_argument("--out", type=Path, default=Path("test_catalog/track_b/corpus_census.parquet"))
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", type=Path, help="tier selection.json: run only its model_ids")
    ap.add_argument("--fail-on-error", action="store_true", help="exit 1 if any selected model does not run cleanly (CI gate)")
    args = ap.parse_args()

    models = sorted(args.corpus.glob("*/*/model.inp"))
    if args.only:
        wanted = set(json.loads(args.only.read_text(encoding="utf-8")).get("model_ids") or [])
        models = [m for m in models if f"{m.parent.parent.name}/{m.parent.name}" in wanted]
    if args.limit:
        models = models[: args.limit]
    version = engine_version()
    print(f"SWMM {version}: {len(models)} models, {args.workers} workers, timeout {args.timeout}s")

    checkpoint = args.out.with_suffix(".partial.parquet")
    rows: list[dict] = []
    if checkpoint.is_file():
        rows = pd.read_parquet(checkpoint).to_dict("records")
        done = {r["model_id"] for r in rows}
        models = [m for m in models if f"{m.parent.parent.name}/{m.parent.name}" not in done]
        print(f"resuming: {len(done)} already done, {len(models)} to go", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one, m, args.timeout): m for m in models}
        for i, fut in enumerate(as_completed(futs), 1):
            m = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:  # defensive: run_one already catches
                rec = {"status": "harness_error", "runtime_s": None, "error_codes": type(exc).__name__}
            rec["model_id"] = f"{m.parent.parent.name}/{m.parent.name}"
            rec["engine"] = "EPA SWMM"
            rec["engine_version"] = version
            rows.append(rec)
            if i % 25 == 0 or i == len(models):
                ok = sum(r["status"] == "ran" for r in rows)
                print(f"  {len(rows)} done, {ok} ran", flush=True)
                pd.DataFrame(rows).to_parquet(checkpoint, index=False)

    df = pd.DataFrame(rows).sort_values("model_id").reset_index(drop=True)
    df.to_parquet(args.out, index=False)
    checkpoint.unlink(missing_ok=True)
    summary = df["status"].value_counts().to_dict()
    print(json.dumps(summary))
    if args.fail_on_error and set(summary) - {"ran"}:
        bad = df[df["status"] != "ran"][["model_id", "status", "error_codes"]]
        print(bad.to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
