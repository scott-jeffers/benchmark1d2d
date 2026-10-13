"""Tests for the Ritter dry-bed dam-break reference."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from references.ritter import depth_contour_position, depth_velocity, front_position


def test_front_position_at_t60():
    """Exact front at t=60 s is ≈ 1375.8 m (h0=1, x0=1000, g=9.81)."""
    xf = front_position(t=60.0, h0=1.0, x0=1000.0, g=9.81)
    assert_allclose(xf, 1375.8, atol=0.1)


def test_undisturbed_and_dry_regions():
    x = np.array([500.0, 2000.0])
    sol = depth_velocity(x, t=60.0, h0=1.0, x0=1000.0, g=9.81)
    assert_allclose(sol["h"][0], 1.0)
    assert_allclose(sol["u"][0], 0.0)
    assert_allclose(sol["h"][1], 0.0)
    assert_allclose(sol["u"][1], 0.0)


def test_interior_rarefaction_at_dam():
    """At the dam abscissa, Ritter gives h = 4/9 h0 and u = 2/3 c0."""
    h0, g, x0, t = 1.0, 9.81, 1000.0, 60.0
    c0 = np.sqrt(g * h0)
    sol = depth_velocity(np.array([x0]), t=t, h0=h0, x0=x0, g=g)
    assert_allclose(sol["h"][0], (4.0 / 9.0) * h0, rtol=1e-12)
    assert_allclose(sol["u"][0], (2.0 / 3.0) * c0, rtol=1e-12)


def test_front_matches_depth_velocity():
    t, h0, x0, g = 60.0, 1.0, 1000.0, 9.81
    xf = front_position(t, h0=h0, x0=x0, g=g)
    # Just upstream of front: wet; just downstream: dry.
    sol = depth_velocity(
        np.array([xf - 1e-6, xf + 1e-6]), t=t, h0=h0, x0=x0, g=g
    )
    assert sol["h"][0] > 0.0
    assert_allclose(sol["h"][1], 0.0)


def test_negative_time_raises():
    with pytest.raises(ValueError):
        depth_velocity(np.array([0.0]), t=-1.0)


def test_depth_contour_matches_solution():
    """Iso-contour abscissa agrees with depth_velocity at that location."""
    t, h0, x0, g = 60.0, 1.0, 1000.0, 9.81
    h_thresh = 1e-3 * h0
    xc = depth_contour_position(t, h_thresh, h0=h0, x0=x0, g=g)
    tip = front_position(t, h0=h0, x0=x0, g=g)
    assert xc < tip
    sol = depth_velocity(np.array([xc]), t=t, h0=h0, x0=x0, g=g)
    assert_allclose(sol["h"][0], h_thresh, rtol=1e-10)
