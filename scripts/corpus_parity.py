#!/usr/bin/env python3
"""Track B corpus parity: score a candidate SWMM engine against SWMM 5.2.4 on a whole tier.

For every model in a tier selection, run the pinned reference (EPA SWMM 5.2.4
from ``swmm-toolkit`` 0.17.0, this interpreter) and a candidate engine on the
same input, read both binary outputs with the same reader, and score parity
element by element exactly as the catalog cases do:

- ``peak_depth``: worst node, relative difference in peak depth
- ``volume``: worst link, relative difference in the time integral of |Q|

A candidate is a Python interpreter (``--candidate-python``) with either a
``swmm.toolkit`` build (e.g. SWMM 5.1.15 in ``swmm-toolkit`` 0.10.0) or the
``openswmm`` wheel (``--candidate-engine openswmm``: HydroCouple's SWMM 6
engine), or the ``hydra`` CLI (``--candidate-engine hydra``, the path given as
``--candidate-python``: NEER AI Hydra's urban-drainage engine) — or the
reference itself, which must score exactly zero (a
self-check of the harness).

Writes ``<out>/<tier>_<label>.parquet`` (one row per model) and a summary JSON
next to it. Exits non-zero only on harness errors, not on parity differences:
those are findings.

Usage::

    python scripts/corpus_parity.py --corpus hc/corpus --tier pr \\
        --candidate-python /path/py310/bin/python --label swmm-5.1.15
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runner" / "python"))

from benchmark1d2d.adapters.swmm5 import read_out  # noqa: E402
from benchmark1d2d.scoring.scorer import parity_from_series  # noqa: E402

TIER_DIR = REPO / "test_catalog" / "track_b"
TOLERANCES_PCT = (1.0, 2.0, 5.0)

_RUN = (
    "import os, sys\n"
    "from swmm.toolkit import solver\n"
    "os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))\n"
    "solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n"
    "print(solver.swmm_version_info())\n"
)


def _run(python: str, inp: Path, td: Path, tag: str, timeout: float, engine: str = "toolkit") -> tuple[Path, float, str]:
    rpt, out = td / f"{tag}.rpt", td / f"{tag}.out"
    t0 = time.perf_counter()
    if engine == "hydra":
        from benchmark1d2d.adapters import hydra

        hydra.run(python, inp, rpt, out, "uds", timeout=timeout)
        return out, round(time.perf_counter() - t0, 3), hydra.version(python)
    if engine == "openswmm":
        from benchmark1d2d.adapters import openswmm

        version = openswmm.run(python, inp, rpt, out, timeout=timeout)
        return out, round(time.perf_counter() - t0, 3), version
    proc = subprocess.run([python, "-c", _RUN, str(inp), str(rpt), str(out)], capture_output=True, timeout=timeout)
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        tail = (proc.stdout + proc.stderr).decode("latin-1", "replace").strip().splitlines()
        raise RuntimeError(tail[-1][:200] if tail else f"exit {proc.returncode}")
    return out, round(time.perf_counter() - t0, 3), proc.stdout.decode("latin-1").split()[-1].split("data")[-1]


def _series(data: dict, kind: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """{element: (t, depth or flow)} in name order, finite values only — the
    same series the scorer builds from a results table, without building one
    (a long-form table of a big model needs several GB)."""
    t = data["t"]
    out = {}
    for name in sorted(data[kind]):
        v = data[kind][name] if kind == "nodes" else data[kind][name][0]
        ok = np.isfinite(v)
        if ok.any():
            out[str(name)] = (t[ok], v[ok])
    return out


def score_model(model_id: str, corpus: Path, cand_python: str, timeout: float, engine: str = "toolkit") -> dict:
    inp = (corpus / model_id / "model.inp").resolve()
    row: dict = {"model_id": model_id, "status": "scored"}
    with tempfile.TemporaryDirectory() as tdn:
        td = Path(tdn)
        try:
            ref_out, row["ref_runtime_s"], _ = _run(sys.executable, inp, td, "ref", timeout)
        except Exception as exc:  # noqa: BLE001 — record and continue
            return {**row, "status": "reference_error", "detail": str(exc)[:200]}
        try:
            cand_out, row["cand_runtime_s"], row["cand_version"] = _run(cand_python, inp, td, "cand", timeout, engine)
        except subprocess.TimeoutExpired:
            return {**row, "status": "candidate_timeout"}
        except Exception as exc:  # noqa: BLE001
            return {**row, "status": "candidate_error", "detail": str(exc)[:200]}
        ref = read_out(ref_out)
        if not ref["nodes"] and not ref["links"]:
            return {**row, "status": "nothing_reported", "detail": "the model's [REPORT] section lists no nodes or links"}
        try:
            cand = read_out(cand_out)
            row["n_nodes"], row["n_links"] = len(ref["nodes"]), len(ref["links"])
            if row["n_nodes"]:
                row["peak_depth_pct"], row["peak_depth_detail"] = parity_from_series(
                    "relative_peak", _series(cand, "nodes"), _series(ref, "nodes"), "h")
            if row["n_links"]:
                row["volume_pct"], row["volume_detail"] = parity_from_series(
                    "relative_volume", _series(cand, "links"), _series(ref, "links"), "Q")
            del ref, cand
        except Exception as exc:  # noqa: BLE001
            return {**row, "status": "harness_error", "detail": f"{type(exc).__name__}: {exc}"[:200]}
    worst = max(abs(row.get("peak_depth_pct", 0.0) or 0.0), abs(row.get("volume_pct", 0.0) or 0.0))
    row["worst_pct"] = worst if np.isfinite(worst) else float("inf")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", type=Path, required=True, help="HydroCouple corpus/ directory at the pinned commit")
    ap.add_argument("--tier", default="pr", choices=["pr", "nightly", "release"])
    ap.add_argument("--candidate-python", default=sys.executable, help="interpreter with the candidate swmm-toolkit (default: the reference itself)")
    ap.add_argument("--candidate-engine", default="toolkit", choices=["toolkit", "openswmm", "hydra"],
                    help="toolkit: a swmm.toolkit build; openswmm: the OpenSWMM Engine v6 in the openswmm wheel; "
                         "hydra: NEER AI Hydra's urban-drainage engine (--candidate-python is then the hydra CLI)")
    ap.add_argument("--label", default="self", help="short name for the candidate, used in file names")
    ap.add_argument("--out", type=Path, default=REPO / "out" / "corpus_parity")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--expect-identical", action="store_true", help="fail unless every scored model differs by exactly 0 (harness self-check)")
    args = ap.parse_args()

    sel = json.loads((TIER_DIR / f"tier_{args.tier}" / "selection.json").read_text(encoding="utf-8"))
    models = sel["model_ids"][: args.limit] if args.limit else sel["model_ids"]
    print(f"{args.tier} tier: {len(models)} models; reference {sel['engine']} {sel['engine_version']}; candidate {args.label}")
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(score_model, m, args.corpus, args.candidate_python, args.timeout, args.candidate_engine): m for m in models}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            if r["status"] == "scored":
                print(f"  [{i}/{len(models)}] {r['model_id']}: worst {r['worst_pct']:.3g} %")
            else:
                print(f"  [{i}/{len(models)}] {r['model_id']}: {r['status']} {r.get('detail', '')}")
    df = pd.DataFrame(rows).sort_values("model_id").reset_index(drop=True)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.tier}_{args.label}"
    df.to_parquet(args.out / f"{stem}.parquet", index=False)
    scored = df[df["status"] == "scored"]
    summary = {
        "tier": args.tier, "upstream_commit": sel["upstream_commit"],
        "reference": f"{sel['engine']} {sel['engine_version']} (swmm-toolkit 0.17.0)",
        "candidate": args.label, "candidate_version": str(scored["cand_version"].iloc[0]) if len(scored) else None,
        "models": len(df), "status": df["status"].value_counts().to_dict(),
        "within_pct": {f"{t:g}": int((scored["worst_pct"] <= t).sum()) for t in TOLERANCES_PCT},
        "median_worst_pct": float(scored["worst_pct"].median()) if len(scored) else None,
        "metrics": "peak_depth = worst node, relative peak depth; volume = worst link, relative integral of |Q|",
    }
    (args.out / f"{stem}.summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    if args.expect_identical:
        bad = df[(df["status"] != "nothing_reported") & ((df["status"] != "scored") | (df.get("worst_pct", 0) != 0))]
        if len(bad):
            print(f"SELF-CHECK FAIL: {len(bad)} models are not bit-identical to themselves:\n{bad[['model_id', 'status']].to_string()}")
            return 1
        print("SELF-CHECK PASS: every model scores exactly 0 against itself")
    return 1 if (df["status"].isin(["reference_error", "harness_error"])).any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
