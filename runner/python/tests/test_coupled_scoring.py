"""Exact-state scoring of the coupled 1D/2D cases on synthetic results."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from benchmark1d2d.catalog import load_manifest
from benchmark1d2d.io.results import write_results_parquet
from benchmark1d2d.scoring.scorer import score_case

REPO = Path(__file__).resolve().parents[3]


def _results(tmp_path: Path, leak: float) -> Path:
    """A12-012-shaped results: 180 m³ in, all out, surface empty; `leak` m³ lost on the way."""
    t = np.array([0.0, 600.0, 1200.0, 10800.0])
    rows = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "Q", "V", "element_id", "element_type")}

    def add(tt, eid, etype, V=np.nan, Q=np.nan, x=np.nan, y=np.nan, h=np.nan):
        for k, v in (("t", tt), ("x", x), ("y", y), ("h", h), ("u", np.nan), ("v", np.nan), ("p", np.nan), ("Q", Q), ("V", V),
                     ("element_id", eid), ("element_type", etype)):
            rows[k].append(v)

    inflow = [0.0, 90.0, 180.0, 180.0]
    surface = [0.0, 30.0, 50.0, 0.0]
    network = [0.0, 15.0, 15.0, 0.0]
    for i, tt in enumerate(t):
        out = inflow[i] - surface[i] - network[i] - (leak if i == len(t) - 1 else 0.0)
        add(tt, "surface", "account", V=surface[i])
        add(tt, "network", "account", V=network[i])
        add(tt, "inflow", "account", V=inflow[i])
        add(tt, "outflow", "account", V=out)
        add(tt, "M1", "exchange", Q=0.1)
        add(tt, "P1", "cell", x=10.0, y=10.0, h=0.0)
    cols = {k: (np.asarray(v, float) if k not in ("element_id", "element_type") else v) for k, v in rows.items()}
    return write_results_parquet(tmp_path / f"r{leak}.parquet", cols)


def test_exact_states_and_continuity(tmp_path: Path) -> None:
    m = load_manifest("A12-012", repo=REPO)
    good = score_case(m, _results(tmp_path, 0.0), timestamp="2024-01-01T00:00:00Z")
    assert good["passed"], good["criteria_results"]
    r = {c["id"]: c for c in good["criteria_results"]}
    assert abs(r["water_balance"]["observed"]) < 1e-9
    assert abs(r["discharged_volume"]["observed"]) < 1e-9

    bad = score_case(m, _results(tmp_path, 1.8), timestamp="2024-01-01T00:00:00Z")
    r = {c["id"]: c for c in bad["criteria_results"]}
    # 1.8 m³ lost of 180 m³: −1 % discharged, and a −1 % end-of-run imbalance
    assert np.isclose(r["discharged_volume"]["observed"], -1.0)
    assert np.isclose(r["water_balance"]["observed"], -1.0)
    assert not bad["passed"]
