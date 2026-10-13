"""Unit tests for hydrobench.convergence (Roache GCI / ASME V&V 20)."""

import numpy as np
from numpy.testing import assert_allclose

from hydrobench.convergence import (
    assess_convergence,
    gci,
    observed_order,
    richardson_extrapolation,
)


def test_observed_order_quadratic_manufactured():
    """Errors scaling as h^2 on three grids with r=2 should give p ≈ 2."""
    h = np.array([0.25, 0.5, 1.0])
    C = 3.7
    errors = C * h**2
    p = observed_order(errors, h)
    assert_allclose(p, 2.0, rtol=1e-12)

    p2 = observed_order(h[0], h[1], h[2], errors[0], errors[1], errors[2])
    assert_allclose(p2, 2.0, rtol=1e-12)


def test_observed_order_two_grid():
    h1, h2 = 0.1, 0.2
    e1, e2 = 0.01, 0.04  # order 2
    assert_allclose(observed_order([e1, e2], [h1, h2]), 2.0)


def test_richardson_extrapolation():
    # f_exact = 1, f_h = 1 + C h^2, r=2, p=2
    C = 0.05
    h1, h2 = 0.1, 0.2
    f1 = 1.0 + C * h1**2
    f2 = 1.0 + C * h2**2
    f_ext = richardson_extrapolation(f1, f2, r=2.0, p=2.0)
    assert_allclose(f_ext, 1.0, rtol=1e-12)


def test_gci_positive_relative():
    f1, f2, r, p = 1.0, 1.04, 2.0, 2.0
    value = gci(f1, f2, r=r, p=p, Fs=1.25)
    assert value > 0.0
    # Fs * |0.04| / (4 - 1) / 1 = 1.25 * 0.04 / 3
    assert_allclose(value, 1.25 * 0.04 / 3.0)


def test_assess_convergence_passes_order():
    h = [0.25, 0.5, 1.0]
    errors = [0.01 * hi**2 for hi in h]
    result = assess_convergence(
        spacings=h,
        errors=errors,
        expected_order=2.0,
        min_observed_order=1.5,
    )
    assert_allclose(result["observed_order"], 2.0, rtol=1e-10)
    assert result["gci_fine"] > 0.0
    assert result["passed_order"] is True
    assert result["expected_order"] == 2.0
    assert result["min_observed_order"] == 1.5


def test_assess_convergence_fails_low_order():
    h = [0.25, 0.5, 1.0]
    # First-order errors
    errors = [0.02 * hi for hi in h]
    result = assess_convergence(
        spacings=h,
        errors=errors,
        expected_order=2.0,
        min_observed_order=1.5,
    )
    assert_allclose(result["observed_order"], 1.0, rtol=1e-10)
    assert result["passed_order"] is False
