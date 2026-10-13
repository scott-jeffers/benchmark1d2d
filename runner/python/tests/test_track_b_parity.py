"""Self-parity scoring: identical series → ~0 error; diffs show in scorecard."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from benchmark1d2d.io.results import write_results_parquet
from benchmark1d2d.metrics import relative_peak, relative_volume
from benchmark1d2d.scoring.scorecard import build_scorecard


def _series_columns(h: np.ndarray, *, t: float = 1.0) -> dict[str, np.ndarray]:
    n = len(h)
    return {
        "t": np.full(n, t, dtype=np.float64),
        "x": np.arange(n, dtype=np.float64),
        "y": np.zeros(n, dtype=np.float64),
        "h": np.asarray(h, dtype=np.float64),
        "u": np.zeros(n, dtype=np.float64),
        "v": np.zeros(n, dtype=np.float64),
        "p": np.zeros(n, dtype=np.float64),
    }


def _parity_criteria(sim_h: np.ndarray, ref_h: np.ndarray) -> list[dict]:
    """Score relative_peak / relative_volume as percent (Track B style)."""
    peak_pct = relative_peak(sim_h, ref_h) * 100.0
    vol_pct = relative_volume(sim_h, ref_h) * 100.0
    return [
        {
            "id": "peak_depth",
            "metric": "relative_peak",
            "variable": "h",
            "observed": float(peak_pct),
            "threshold": {"op": "abs<=", "value": 1.0, "units": "%"},
            "passed": bool(abs(peak_pct) <= 1.0),
            "gating": True,
        },
        {
            "id": "volume",
            "metric": "relative_volume",
            "variable": "h",
            "observed": float(vol_pct),
            "threshold": {"op": "abs<=", "value": 1.0, "units": "%"},
            "passed": bool(abs(vol_pct) <= 1.0),
            "gating": True,
        },
    ]


def test_self_parity_identical_near_zero(tmp_path: Path):
    h = np.array([1.0, 2.0, 3.0, 2.5, 1.5], dtype=np.float64)
    cols = _series_columns(h)
    write_results_parquet(tmp_path / "sim.parquet", cols)
    write_results_parquet(tmp_path / "ref.parquet", cols)

    assert relative_peak(h, h) == pytest.approx(0.0)
    assert relative_volume(h, h) == pytest.approx(0.0)

    criteria = _parity_criteria(h, h)
    assert all(c["passed"] for c in criteria)
    assert all(abs(c["observed"]) < 1e-12 for c in criteria)

    card = build_scorecard(
        test_id="B-EXTRAN-001_extran_parity",
        track="B",
        case_version="1.0.0",
        solver={"name": "self", "version": "0.0.0", "adapter": "generic_parquet"},
        catalog_version="0.1.0",
        criteria_results=criteria,
        passed=True,
        certification_claims=["B-1%"],
        timestamp="2024-01-15T12:00:00Z",
    )
    assert card["passed"] is True
    assert card["criteria_results"][0]["observed"] == pytest.approx(0.0)


def test_self_parity_diff_readable_in_scorecard():
    ref = np.array([1.0, 2.0, 3.0, 2.0], dtype=np.float64)
    # 10% higher peak; ~6.25% higher volume → fails ±1% gate
    sim = np.array([1.0, 2.0, 3.3, 2.2], dtype=np.float64)

    criteria = _parity_criteria(sim, ref)
    assert criteria[0]["metric"] == "relative_peak"
    assert criteria[0]["observed"] == pytest.approx(10.0)
    assert criteria[0]["passed"] is False

    assert criteria[1]["metric"] == "relative_volume"
    # (8.5 - 8.0) / 8.0 * 100 = 6.25
    assert criteria[1]["observed"] == pytest.approx(6.25)
    assert criteria[1]["passed"] is False

    card = build_scorecard(
        test_id="B-EXTRAN-001_extran_parity",
        track="B",
        case_version="1.0.0",
        solver={"name": "self", "version": "0.0.0", "adapter": "generic_parquet"},
        catalog_version="0.1.0",
        criteria_results=criteria,
        passed=False,
        certification_claims=[],
        timestamp="2024-01-15T12:00:00Z",
    )
    assert card["passed"] is False
    # Readable diff: observed values appear on the scorecard criteria_results
    by_id = {c["id"]: c for c in card["criteria_results"]}
    assert "peak_depth" in by_id and "volume" in by_id
    assert by_id["peak_depth"]["observed"] == pytest.approx(10.0)
    assert by_id["volume"]["observed"] == pytest.approx(6.25)
    assert by_id["peak_depth"]["threshold"]["units"] == "%"
