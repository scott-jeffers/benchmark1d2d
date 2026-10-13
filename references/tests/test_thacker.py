"""Tests for the Thacker parabolic-bowl reference.

The decisive checks are the PDE residuals: an "exact solution" must satisfy
continuity and momentum pointwise, not just return to its initial state after
one period (a check the pre-v2 solution passed while violating continuity).
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from references.thacker import (
    angular_frequency,
    bed_elevation,
    depth_velocity,
    planar_oscillation,
)

H0, L, ETA, G = 0.1, 1.0, 0.05, 9.81


def test_omega_default():
    assert_allclose(angular_frequency(H0, L, G), np.sqrt(2.0 * G * H0) / L)


def test_center_depth_at_t0():
    sol = depth_velocity(0.0, 0.0, t=0.0, h0=H0, L=L, eta=ETA, g=G)
    # zs(0, 0) = -η² h0 / L²
    assert_allclose(sol["h"], H0 - ETA**2 * H0 / L**2)
    assert_allclose(sol["u"], 0.0)
    assert_allclose(sol["v"], 0.0)


def test_bed_at_origin_and_shore():
    assert_allclose(bed_elevation(0.0, 0.0, H0, L), -H0)
    assert_allclose(bed_elevation(L, 0.0, H0, L), 0.0)


@pytest.mark.parametrize("t", [0.05, 0.3, 0.77, 1.4])
def test_satisfies_shallow_water_equations(t):
    """Pointwise continuity and x-momentum residuals vanish in the wet region."""
    x = np.linspace(-0.8, 0.8, 33)
    y = np.zeros_like(x)
    e = 1e-6

    def f(tt, xx):
        return depth_velocity(xx, y, tt, h0=H0, L=L, eta=ETA, g=G)

    def zs(tt, xx):
        return f(tt, xx)["h"] + bed_elevation(xx, y, H0, L)

    dh_dt = (f(t + e, x)["h"] - f(t - e, x)["h"]) / (2 * e)
    dq_dx = (f(t, x + e)["h"] * f(t, x + e)["u"] - f(t, x - e)["h"] * f(t, x - e)["u"]) / (2 * e)
    du_dt = (f(t + e, x)["u"] - f(t - e, x)["u"]) / (2 * e)
    dzs_dx = (zs(t, x + e) - zs(t, x - e)) / (2 * e)
    assert np.max(np.abs(dh_dt + dq_dx)) < 1e-8
    assert np.max(np.abs(du_dt + G * dzs_dx)) < 1e-8


def test_mass_conserved_at_every_quarter_period():
    period = 2.0 * np.pi / angular_frequency(H0, L, G)
    coord = np.linspace(-1.2 * L, 1.2 * L, 481)
    dx = coord[1] - coord[0]
    X, Y = np.meshgrid(coord, coord, indexing="xy")

    def wet_mass(t):
        return float(np.sum(depth_velocity(X, Y, t=t, h0=H0, L=L, eta=ETA, g=G)["h"]) * dx * dx)

    m0 = wet_mass(0.0)
    for k in (1, 2, 3, 4):
        assert_allclose(wet_mass(k * period / 4.0), m0, rtol=2e-3)


def test_velocity_peaks_at_quarter_period():
    omega = angular_frequency(H0, L, G)
    sol = depth_velocity(0.0, 0.0, t=0.25 * 2.0 * np.pi / omega, h0=H0, L=L, eta=ETA, g=G)
    assert_allclose(sol["u"], -ETA * omega, rtol=1e-12)


def test_planar_oscillation_alias():
    assert planar_oscillation is depth_velocity
