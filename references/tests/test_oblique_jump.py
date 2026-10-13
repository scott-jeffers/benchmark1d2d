"""Tests for the oblique hydraulic jump reference (exact shallow-water jump conditions)."""

import numpy as np
from numpy.testing import assert_allclose

from references.oblique_jump import conjugate_depth_ratio, depth_velocity, shock_angle, states

G = 9.81


def test_weak_jump_angle_matches_ippen_chow_relation():
    F, th = 2.5, np.deg2rad(15.0)
    b = np.deg2rad(shock_angle(F, 15.0))
    s = np.sqrt(1.0 + 8.0 * F**2 * np.sin(b) ** 2)
    assert_allclose(np.tan(th), np.tan(b) * (s - 3.0) / (2.0 * np.tan(b) ** 2 + s - 1.0), rtol=1e-9)
    assert_allclose(np.rad2deg(b), 39.577, atol=0.001)


def test_rankine_hugoniot_holds_across_the_jump():
    st = states(2.5, 15.0, 1.0, G)
    b, th = np.deg2rad(st["beta_deg"]), np.deg2rad(15.0)
    V1 = np.hypot(st["u1"], st["v1"])
    n1, n2 = V1 * np.sin(b), st["u2"] * np.sin(b - th)  # normal speeds
    assert_allclose(st["h1"] * n1, st["h2"] * n2, rtol=1e-12)  # mass
    assert_allclose(st["h1"] * n1**2 + 0.5 * G * st["h1"] ** 2, st["h2"] * n2**2 + 0.5 * G * st["h2"] ** 2, rtol=1e-12)
    assert_allclose(V1 * np.cos(b), st["u2"] * np.cos(b - th), rtol=1e-12)  # tangential


def test_region_between_wall_and_jump_is_downstream():
    """Regression: an earlier version labelled this region upstream."""
    st = states()
    near_wall = depth_velocity(30.0, 1.0)
    far = depth_velocity(5.0, 25.0)
    assert_allclose(near_wall["h"], st["h2"])
    assert near_wall["v"] == 0.0
    assert_allclose(far["h"], 1.0)
    assert far["v"] < 0.0


def test_depth_ratio_and_supercritical_outflow():
    st = states()
    assert st["h2"] > st["h1"]
    assert_allclose(st["h2"], conjugate_depth_ratio(2.5, st["beta_deg"]))
    assert st["Fr2"] > 1.0
