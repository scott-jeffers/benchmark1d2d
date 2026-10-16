"""Measured-gauge scoring on a network: probes matched by node name, several events, levels above datum."""

from __future__ import annotations

import numpy as np
import pandas as pd

from benchmark1d2d.io.results import write_results_parquet
from benchmark1d2d.scoring.scorer import _score_measured


def _case(tmp_path, units="m", value=0.1):
    t = np.arange(0, 3600, 60.0)
    obs = []
    for ev, off in (("a", 0.0), ("b", 1e6)):
        lvl = 10.0 + np.exp(-((t - 1800) / 600) ** 2)
        obs.append(pd.DataFrame({"t": t + off, "gauge": "G1", "wse": lvl, "event": ev}))
    (tmp_path / "reference").mkdir()
    pd.concat(obs).to_parquet(tmp_path / "reference" / "levels.parquet", index=False)
    return {
        "test_id": "X-1_net", "_case_dir": str(tmp_path),
        "reference": {"kind": "measured", "data_path": "reference/levels.parquet"},
        "simulation": {"t_end": 3600, "output_interval": 60, "required_outputs": ["h"],
                       "probes": [{"id": "G1", "x": 0.0, "element": "N1"}]},
        "scoring": {"pass_rule": "all_gating", "criteria": [
            {"id": "nse", "metric": "NSE", "variable": "wse", "threshold": {"op": ">=", "value": 0.5}, "gating": True},
            {"id": "peak", "metric": "peak_error", "variable": "wse", "threshold": {"op": "abs<=", "value": value, "units": units}, "gating": True},
        ]},
    }


def _results(tmp_path, events=(0.0, 1e6), bias=0.0):
    t = np.arange(0, 3600, 60.0)
    rows = []
    for off in events:
        for node, scale in (("N1", 1.0), ("N2", 5.0)):  # N2 is far off, and must not be read for G1
            h = 1.0 + scale * np.exp(-((t - 1800) / 600) ** 2) + bias
            rows.append(dict(t=t + off, h=h, z=np.full(len(t), 9.0), element_id=[node] * len(t)))
    cols = {k: np.concatenate([r[k] for r in rows]) for k in ("t", "h", "z")}
    n = len(cols["t"])
    nan = np.full(n, np.nan)
    cols.update(x=nan, y=nan, u=nan, v=nan, p=nan, element_id=np.concatenate([r["element_id"] for r in rows]),
                element_type=["node"] * n)
    return write_results_parquet(tmp_path / "r.parquet", cols)


def test_exact_levels_pass(tmp_path):
    rows, _, passed = _score_measured(_case(tmp_path), _results(tmp_path))
    assert passed
    assert rows[0]["observed"] > 0.999
    assert abs(rows[1]["observed"]) < 1e-9
    assert "2 gauge records" in rows[0]["detail"]


def test_peak_in_metres(tmp_path):
    rows, _, passed = _score_measured(_case(tmp_path), _results(tmp_path, bias=0.3))
    assert not passed
    assert abs(rows[1]["observed"] - 0.3) < 1e-9


def test_an_event_not_simulated_fails(tmp_path):
    rows, _, passed = _score_measured(_case(tmp_path), _results(tmp_path, events=(0.0,)))
    assert not passed
    assert rows[0]["observed"] is None
    assert "not simulated" in rows[0]["detail"]
