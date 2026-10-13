"""Tests for the Joukowsky water-hammer reference."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from references.joukowsky import delta_p, pressure_wave


def test_delta_p_classic():
    assert_allclose(delta_p(1000.0, 1.0), 1.0e6)


def test_delta_p_scales_with_rho():
    assert_allclose(delta_p(1000.0, 1.0, rho=500.0), 5.0e5)


def test_pressure_wave_before_reflection():
    L, a, V0, rho = 1000.0, 1000.0, 1.0, 1000.0
    t = 0.25  # front at x = L - a t = 750
    x = np.array([0.0, 500.0, 800.0, 1000.0])
    sol = pressure_wave(x, t=t, L=L, a=a, V0=V0, rho=rho, p0=0.0)
    assert_allclose(sol["delta_p"], 1.0e6)
    # Ahead of front: undisturbed.
    assert_allclose(sol["p"][:2], 0.0)
    assert_allclose(sol["u"][:2], V0)
    # Behind front: Joukowsky state.
    assert_allclose(sol["p"][2:], 1.0e6)
    assert_allclose(sol["u"][2:], 0.0)


def test_rejects_time_after_reflection():
    with pytest.raises(ValueError):
        pressure_wave(np.array([0.0]), t=2.0, L=1000.0, a=1000.0, V0=1.0)
