"""Tests for the MacDonald-style 2D manufactured reference."""

import numpy as np
from numpy.testing import assert_allclose

from references.macdonald_2d import bed_elevation, depth_profile, depth_velocity


def test_depth_positive():
    x = np.linspace(0.0, 1000.0, 51)
    y = np.linspace(0.0, 100.0, 11)
    X, Y = np.meshgrid(x, y, indexing="xy")
    h = depth_profile(X, Y)
    assert np.all(h > 0.0)


def test_free_surface_constant_datum():
    x = np.array([100.0, 500.0, 900.0])
    y = np.array([10.0, 50.0, 90.0])
    sol = depth_velocity(x, y, t=0.0)
    assert_allclose(sol["zb"] + sol["h"], sol["zs"])
    assert_allclose(sol["zs"], sol["zs"][0])  # constant zs0


def test_unit_discharge():
    x = np.linspace(0.0, 1000.0, 21)
    y = np.full_like(x, 50.0)
    qx, qy = 0.2, 0.0
    sol = depth_velocity(x, y, qx=qx, qy=qy)
    assert_allclose(sol["u"] * sol["h"], qx, rtol=1e-12)
    assert_allclose(sol["v"], 0.0)


def test_bed_below_free_surface():
    zb = bed_elevation(500.0, 50.0)
    h = depth_profile(500.0, 50.0)
    assert h > 0.0
    assert zb < zb + h  # free surface above bed
