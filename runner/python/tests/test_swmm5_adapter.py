"""SWMM5 .rpt adapter → results Parquet."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from benchmark1d2d.adapters.swmm5 import adapt_rpt_to_parquet, parse_rpt
from benchmark1d2d.io.results import read_results_parquet

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample.rpt"


def test_parse_rpt_extracts_nodes_and_links():
    parsed = parse_rpt(FIXTURE)
    assert len(parsed["nodes"]) == 3
    assert parsed["nodes"][0]["id"] == "J1"
    assert parsed["nodes"][0]["max_depth"] == pytest.approx(1.25)
    assert parsed["nodes"][1]["max_depth"] == pytest.approx(2.1)
    assert len(parsed["links"]) == 2
    assert parsed["links"][0]["id"] == "C1"
    assert parsed["links"][0]["max_flow"] == pytest.approx(3.5)


def test_adapt_rpt_to_parquet(tmp_path: Path):
    out = tmp_path / "sample.parquet"
    adapt_rpt_to_parquet(FIXTURE, out)
    assert out.is_file()

    df = read_results_parquet(out)
    # 3 nodes + 2 links
    assert len(df) == 5
    assert set(["t", "x", "y", "h", "u", "v", "p", "Q"]).issubset(df.columns)
    # Node depths land in h for the first three rows
    assert np.allclose(df["h"].to_numpy()[:3], [1.25, 2.1, 0.8])
    # Link max flows in Q for the last two rows
    assert np.allclose(df["Q"].to_numpy()[3:], [3.5, 2.75])
