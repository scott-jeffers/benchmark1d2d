"""Tests for the MacDonald-type 2D steady channel reference."""

import numpy as np
from numpy.testing import assert_allclose

from references.macdonald_2d import bed_elevation, depth_profile, depth_velocity

G, Q, N = 9.81, 0.2, 0.03


def test_depth_positive_and_subcritical():
    x = np.linspace(0.0, 1000.0, 201)
    h = depth_profile(x)
    assert np.all(h > 0.0)
    assert np.all(Q / h / np.sqrt(G * h) < 1.0)


def test_steady_momentum_balance_holds():
    """The 1D steady momentum equation (exact for v = 0) has zero residual."""
    x = np.linspace(50.0, 950.0, 9001)
    s = depth_velocity(x, np.full_like(x, 50.0))
    h, u, zb = s["h"], s["u"], s["zb"]
    dx = x[1] - x[0]
    residual = u * np.gradient(u, dx) + G * np.gradient(h + zb, dx) + G * N**2 * u * u / h ** (4.0 / 3.0)
    scale = G * np.max(np.abs(np.gradient(zb, dx)))
    assert np.max(np.abs(residual)) < 1e-4 * scale


def test_free_surface_is_not_flat():
    """Regression: an earlier version held zs constant, which cannot carry flow."""
    s = depth_velocity(np.array([0.0, 1000.0]), np.array([50.0, 50.0]))
    assert s["zs"][0] - s["zs"][1] > 0.05


def test_unit_discharge_and_no_cross_flow():
    x = np.linspace(0.0, 1000.0, 21)
    s = depth_velocity(x, np.full_like(x, 10.0))
    assert_allclose(s["u"] * s["h"], Q, rtol=1e-12)
    assert_allclose(s["v"], 0.0)


def test_bed_anchored_at_outlet():
    assert abs(float(bed_elevation(1000.0))) < 1e-9
