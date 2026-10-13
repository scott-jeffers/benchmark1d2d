"""Tests for the Ippen oblique hydraulic jump reference."""

import numpy as np
from numpy.testing import assert_allclose

from references.oblique_jump import (
    conjugate_depth_ratio,
    depth_velocity,
    shock_angle,
)


def test_shock_angle_supercritical():
    beta = shock_angle(Fr1=2.5, theta_deg=15.0)
    assert 15.0 < beta < 90.0


def test_conjugate_depth_greater_than_one():
    beta = shock_angle(2.5, 15.0)
    ratio = conjugate_depth_ratio(2.5, beta)
    assert ratio > 1.0


def test_upstream_state_on_sample():
    # Point well below a ~40° shock: (x,y)=(10, 0) should be upstream.
    sol = depth_velocity(10.0, 0.0, Fr1=2.5, theta_deg=15.0, h1=1.0, g=9.81)
    assert_allclose(sol["h"], 1.0)
    assert sol["v"] == 0.0
    assert sol["u"] > 0.0


def test_downstream_deeper():
    beta = shock_angle(2.5, 15.0)
    # Point above the shock ray.
    x, y = 5.0, 5.0 * np.tan(np.deg2rad(beta)) + 2.0
    sol = depth_velocity(x, y, Fr1=2.5, theta_deg=15.0, h1=1.0)
    assert sol["h"] > 1.0
    assert_allclose(sol["h"], sol["h2"])


def test_deflection_angle_approx():
    sol = depth_velocity(20.0, 25.0, Fr1=2.5, theta_deg=15.0, h1=1.0)
    if sol["h"] > 1.0 + 1e-9:
        ang = np.rad2deg(np.arctan2(sol["v"], sol["u"]))
        assert_allclose(ang, 15.0, atol=2.0)
