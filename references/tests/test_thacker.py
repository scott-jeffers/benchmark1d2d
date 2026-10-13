"""Tests for the Thacker parabolic-bowl reference."""

import numpy as np
from numpy.testing import assert_allclose

from references.thacker import (
    angular_frequency,
    bed_elevation,
    depth_velocity,
    planar_oscillation,
)


def test_center_depth_at_t0():
    h0, L, eta = 0.1, 1.0, 0.02
    sol = depth_velocity(0.0, 0.0, t=0.0, h0=h0, L=L, eta=eta, g=9.81)
    assert_allclose(sol["h"], h0)
    assert_allclose(sol["u"], 0.0)
    assert_allclose(sol["v"], 0.0)


def test_omega_default():
    h0, L, g = 0.1, 1.0, 9.81
    assert_allclose(angular_frequency(h0, L, g), np.sqrt(8.0 * g * h0) / L)


def test_bed_at_origin_and_shore():
    h0, L = 0.1, 1.0
    assert_allclose(bed_elevation(0.0, 0.0, h0, L), -h0)
    assert_allclose(bed_elevation(L, 0.0, h0, L), 0.0)


def test_mass_conserved_over_period():
    """Wet-area mass (∫ h dA) returns to the initial value after one period."""
    h0, L, eta, g = 0.1, 1.0, 0.02, 9.81
    omega = angular_frequency(h0, L, g)
    period = 2.0 * np.pi / omega

    n = 201
    coord = np.linspace(-L, L, n)
    dx = coord[1] - coord[0]
    X, Y = np.meshgrid(coord, coord, indexing="xy")

    def wet_mass(t):
        sol = depth_velocity(X, Y, t=t, h0=h0, L=L, eta=eta, omega=omega, g=g)
        return float(np.sum(sol["h"]) * dx * dx)

    m0 = wet_mass(0.0)
    mT = wet_mass(period)
    assert_allclose(mT, m0, rtol=1e-3)


def test_velocity_peaks_at_quarter_period():
    h0, L, eta, g = 0.1, 1.0, 0.02, 9.81
    omega = angular_frequency(h0, L, g)
    sol = depth_velocity(
        0.0, 0.0, t=0.25 * 2.0 * np.pi / omega, h0=h0, L=L, eta=eta, g=g
    )
    u_expected = -(g * eta / (omega * L))  # sin(π/2) = 1
    assert_allclose(sol["u"], u_expected, rtol=1e-12)


def test_planar_oscillation_alias():
    assert planar_oscillation is depth_velocity
    sol = planar_oscillation(0.0, 0.0, t=0.0, h0=0.1, L=1.0, eta=0.02)
    assert_allclose(sol["h"], 0.1)
