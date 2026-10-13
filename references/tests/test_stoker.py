"""Tests for the Stoker wet-bed dam-break reference."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from references.stoker import depth_velocity, intermediate_state

# Published / independently computed intermediate depth for the classic
# hl=1, hr=0.1, g=9.81 Stoker dam break (SWE Riemann problem).
H_STAR_REF = 0.396175


def test_intermediate_depth_classic():
    star = intermediate_state(hl=1.0, hr=0.1, g=9.81)
    assert_allclose(star["h_star"], H_STAR_REF, atol=1e-3)


def test_intermediate_velocity_consistency():
    hl, hr, g = 1.0, 0.1, 9.81
    star = intermediate_state(hl=hl, hr=hr, g=g)
    u_rare = 2.0 * (np.sqrt(g * hl) - np.sqrt(g * star["h_star"]))
    assert_allclose(star["u_star"], u_rare, rtol=1e-10)
    assert star["u_star"] > 0.0
    assert hr < star["h_star"] < hl


def test_depth_velocity_regions():
    hl, hr, g, x0, t = 1.0, 0.1, 9.81, 0.0, 10.0
    star = intermediate_state(hl, hr, g=g)
    # Far left / far right undisturbed.
    x = np.array([-1000.0, 1000.0])
    sol = depth_velocity(x, t=t, hl=hl, hr=hr, x0=x0, g=g)
    assert_allclose(sol["h"][0], hl)
    assert_allclose(sol["u"][0], 0.0)
    assert_allclose(sol["h"][1], hr)
    assert_allclose(sol["u"][1], 0.0)

    # A point inside the star plateau (between rarefaction tail and shock).
    c_star = np.sqrt(g * star["h_star"])
    x_mid = 0.5 * (
        (star["u_star"] - c_star) * t + star["shock_speed"] * t
    )
    sol_mid = depth_velocity(np.array([x_mid]), t=t, hl=hl, hr=hr, x0=x0, g=g)
    assert_allclose(sol_mid["h"][0], star["h_star"], rtol=1e-10)
    assert_allclose(sol_mid["u"][0], star["u_star"], rtol=1e-10)


def test_invalid_depths_raise():
    with pytest.raises(ValueError):
        intermediate_state(hl=0.1, hr=1.0)
    with pytest.raises(ValueError):
        intermediate_state(hl=1.0, hr=0.0)
