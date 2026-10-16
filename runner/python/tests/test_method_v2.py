"""The proposed scoring method (v2): fitted order with its interval, margins, verdicts."""

import math

from benchmark1d2d.scoring.method_v2 import assess, fit_order, margin


def card(errors, spacings=None, pmin=0.8, name="Some solver", checks=((0.5, 1.0, True),)):
    spacings = spacings or [1.25 * 2**i for i in range(len(errors))]
    return {
        "passed": True,
        "solver": {"name": name},
        "criteria_results": [{"id": f"c{i}", "gating": True, "passed": ok, "observed": obs,
                              "threshold": {"op": "abs<=", "value": lim}} for i, (obs, lim, ok) in enumerate(checks)],
        "convergence_result": {"errors": errors, "spacings": spacings, "min_observed_order": pmin, "variable": "h",
                               "observed_order": 0.0},
    }


def test_fit_recovers_exact_order_with_zero_width_interval():
    f = fit_order([1e-3 * 2**i for i in range(4)], [1.25 * 2**i for i in range(4)])
    assert math.isclose(f["order"], 1.0, rel_tol=1e-12)
    assert math.isclose(f["ci"][0], 1.0, rel_tol=1e-9) and math.isclose(f["ci"][1], 1.0, rel_tol=1e-9)


def test_steady_order_just_below_minimum_fails_and_erratic_one_is_inconclusive():
    steady = assess(card([0.00098, 0.00166, 0.00291, 0.0050]))  # LISFLOOD-FP FV1, A1F-011: ~0.78
    erratic = assess(card([0.00039, 0.00042, 0.00138, 0.00138]))  # ANUGA, A1F-011: 1.72 then 0.11
    assert steady["converges"]["verdict"] in ("fail", "inconclusive")
    assert erratic["converges"]["verdict"] == "inconclusive"
    assert erratic["overall"] == "inconclusive"


def test_clean_first_order_passes_and_flat_error_fails():
    assert assess(card([1e-3 * 2**i for i in range(4)]))["overall"] == "pass"
    flat = assess(card([0.0137, 0.0140, 0.0146, 0.0160]))
    assert flat["converges"]["verdict"] == "fail" and flat["overall"] == "fail"


def test_three_grids_give_a_wide_interval():
    c = assess(card([0.00094, 0.00172, 0.00346]))  # ANUGA, A1F-040
    assert c["converges"]["levels"] == 3
    assert c["converges"]["ci"][1] - c["converges"]["ci"][0] > 0.4


def test_precision_floor_applies_only_to_the_declared_solver():
    errs = [0.0001, 0.0001, 0.00009, 0.00005]
    assert assess(card(errs, name="HEC-RAS 6.6"))["converges"]["verdict"] == "at_floor"
    assert assess(card(errs, name="HEC-RAS 6.6"))["overall"] == "pass"
    assert assess(card(errs, name="Other"))["converges"]["verdict"] == "fail"


def test_round_off_on_every_grid_still_fails():
    assert assess(card([1e-15, 1e-15, 1e-15]))["overall"] == "fail"


def test_margins_and_accuracy_verdict():
    a = assess(card([1e-3 * 2**i for i in range(4)], checks=((0.0056, 0.005, False), (0.0001, 0.001, True))))
    assert a["accurate"] == "fail" and a["overall"] == "fail"
    assert math.isclose(a["worst_margin"], 1.12)
    assert margin(-0.3, {"op": "abs<=", "value": 0.5}) == 0.6
    assert margin(None, {"op": "abs<=", "value": 0.5}) is None


def test_no_convergence_study_is_not_applicable():
    c = card([1e-3])
    c["convergence_result"] = {}
    assert assess(c)["converges"]["verdict"] == "n/a"
    assert assess(c)["overall"] == "pass"
