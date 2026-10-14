"""A results template filled in as CSV scores exactly like the same Parquet."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from benchmark1d2d.catalog import load_manifest
from benchmark1d2d.io.results import read_results_parquet, write_results_parquet
from benchmark1d2d.scoring.scorer import score_case
from references.stoker import depth_velocity as stoker

REPO = Path(__file__).resolve().parents[3]


def test_csv_and_parquet_score_the_same(tmp_path):
    m = load_manifest("A1F-011", repo=REPO)

    paths_pq, paths_csv = [], []
    for dx in (10.0, 5.0):
        x = np.arange(-1000 + dx / 2, 1000, dx)
        r = stoker(x, 30.0, **m["reference"]["generator"]["parameters"])
        h = r["h"] * (1 + 0.001 * np.sin(x))
        n = len(x)
        cols = {"t": np.full(n, 30.0), "x": x, "y": np.full(n, np.nan), "h": h, "u": r["u"], "v": np.full(n, np.nan), "p": np.full(n, np.nan)}
        pq = write_results_parquet(tmp_path / f"r_dx{dx:g}.parquet", cols)
        csv = tmp_path / f"r_dx{dx:g}.csv"
        pd.DataFrame(cols).to_csv(csv, index=False)
        paths_pq.append(pq)
        paths_csv.append(csv)
    assert read_results_parquet(paths_csv[0]).shape[0] == read_results_parquet(paths_pq[0]).shape[0]
    a = score_case(m, paths_pq[-1], refinement_results=paths_pq, timestamp="2024-01-01T00:00:00Z")
    b = score_case(m, paths_csv[-1], refinement_results=paths_csv, timestamp="2024-01-01T00:00:00Z")
    # CSV holds 17 significant digits at most, so agreement is to round-off.
    assert [r["observed"] for r in a["criteria_results"]] == pytest.approx([r["observed"] for r in b["criteria_results"]], rel=1e-9)
    assert a["convergence_result"]["errors"] == pytest.approx(b["convergence_result"]["errors"], rel=1e-9)
    assert a["passed"] == b["passed"]
