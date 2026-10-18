"""Scoring method 3.0: the score is over accuracy checks only (review F6/F7)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "site"))

import difference  # noqa: E402

from benchmark1d2d.scoring.scorer import parity_from_series  # noqa: E402


def _r(i, metric, obs, units="%", op="abs<="):
    return {"id": i, "metric": metric, "observed": obs, "threshold": {"op": op, "units": units, "value": 1}}


def test_score_ignores_mass_timing_and_nse():
    card = {"test_id": "X-001", "criteria_results": [
        _r("depth", "L2", 2.0), _r("mass", "global_mass_error", 50.0),
        _r("arrival", "arrival_time_error", 300.0, "s"), _r("gauge", "NSE", 0.2, "1", ">=")]}
    assert difference.result(card) == 2.0
    assert difference.worst_check(card)["id"] == "depth"
    side = difference.side(card)
    assert side == {"conservation": 50.0, "timing": 300.0, "nse": 0.2}


def test_no_accuracy_check_falls_back_to_nse():
    card = {"test_id": "X-002", "criteria_results": [
        _r("gauge", "NSE", 0.9, "1", ">="), _r("arrival", "arrival_time_error", 10.0, "s")]}
    assert abs(difference.result(card) - 10.0) < 1e-9


def test_timing_is_never_a_percent():
    assert difference.percent("B-EPANET-001", _r("peak_timing", "timing_error", 3600.0, "s")) is None


def test_relative_peak_depth_floor():
    t = np.linspace(0, 1, 5)
    ref = {"wet": (t, np.full(5, 0.3)), "dry": (t, np.full(5, 0.0001))}
    sim = {"wet": (t, np.full(5, 0.3)), "dry": (t, np.full(5, 0.0011))}
    v, _ = parity_from_series("relative_peak", sim, ref, "h")
    assert abs(v) <= 10.0 + 1e-9  # 1 mm over a 1 cm floor, not 1000 % over 0.1 mm
