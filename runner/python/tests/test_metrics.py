"""Unit tests for benchmark1d2d.metrics."""

import numpy as np
from numpy.testing import assert_allclose

from benchmark1d2d.metrics import (
    L1,
    L2,
    Linf,
    arrival_time_error,
    continuity_error,
    csi,
    front_position_error,
    global_mass_error,
    kge,
    nse,
    peak_error,
    relative_peak,
    relative_volume,
    timing_error,
)
from references.joukowsky import delta_p


def test_nse_identical_is_one():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert_allclose(nse(y, y), 1.0)


def test_nse_known_value():
    obs = np.array([1.0, 2.0, 3.0])
    sim = np.array([1.0, 2.0, 2.0])
    # denom = (1-2)^2 + (2-2)^2 + (3-2)^2 = 2
    # num = 0 + 0 + 1 = 1 → NSE = 1 - 0.5 = 0.5
    assert_allclose(nse(sim, obs), 0.5)


def test_l1_known_arrays():
    sim = np.array([1.0, 2.0, 3.0])
    ref = np.array([1.0, 1.0, 1.0])
    # mean(|diff|) = mean([0, 1, 2]) = 1
    assert_allclose(L1(sim, ref), 1.0)
    # dx is ignored: norms are domain-normalised so observed orders are not inflated
    assert_allclose(L1(sim, ref, dx=2.0), 1.0)


def test_l2_and_linf():
    sim = np.array([0.0, 3.0, 4.0])
    ref = np.array([0.0, 0.0, 0.0])
    assert_allclose(L2(sim, ref), np.sqrt(np.mean([0.0, 9.0, 16.0])))
    assert_allclose(Linf(sim, ref), 4.0)


def test_norms_broadcast():
    sim = np.array([[1.0, 2.0], [3.0, 4.0]])
    ref = 1.0
    assert L1(sim, ref) > 0.0
    assert Linf(sim, ref) == 3.0


def test_joukowsky_peak_error():
    """Peak relative error against classic Joukowsky Δp = ρ a V0."""
    a, V0, rho = 1000.0, 1.0, 1000.0
    exact = delta_p(a, V0, rho=rho)
    obs = np.array([0.0, exact, exact * 0.5])
    sim_perfect = np.array([0.0, exact, exact])
    assert_allclose(peak_error(sim_perfect, obs), 0.0)

    sim_high = np.array([0.0, 1.1 * exact])
    assert_allclose(peak_error(sim_high, obs), 0.1)


def test_global_mass_error_percent():
    assert_allclose(global_mass_error(101.0, 100.0), 1.0)


def test_kge_perfect():
    y = np.linspace(0.0, 10.0, 50)
    assert_allclose(kge(y, y), 1.0, atol=1e-12)


def test_arrival_and_front():
    t = np.array([0.0, 1.0, 2.0, 3.0])
    obs = np.array([0.0, 0.0, 1.0, 2.0])
    sim = np.array([0.0, 0.0, 0.0, 1.5])
    assert_allclose(arrival_time_error(t, sim, obs, threshold=0.5), 1.0)

    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    h = np.array([1.0, 0.8, 0.4, 0.05, 0.0])
    assert_allclose(front_position_error(x, h, h_threshold=0.1, exact_front=2.0), 0.0)


def test_csi_perfect_and_partial():
    wet = np.array([True, True, False, False])
    assert_allclose(csi(wet, wet), 1.0)

    sim = np.array([True, False, True, False])
    obs = np.array([True, True, False, False])
    # hits=1, misses=1, FA=1 → CSI = 1/3
    assert_allclose(csi(sim, obs), 1.0 / 3.0)


def test_parity_metrics():
    sim = np.array([1.0, 2.0, 3.3])
    ref = np.array([1.0, 2.0, 3.0])
    assert_allclose(relative_peak(sim, ref), 0.1)
    assert_allclose(relative_volume(sim, ref), (6.3 - 6.0) / 6.0)
    assert_allclose(timing_error(5.0, 4.0), 1.0)
    assert_allclose(continuity_error(-0.25), 0.25)


def test_volume_front_matches_ritter_exact():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from references.ritter import depth_velocity, volume_front_position as exact

    from benchmark1d2d.metrics import volume_front_error

    x = np.arange(0.625, 2000.0, 1.25)
    h = depth_velocity(x, 60.0, h0=1.0, x0=1000.0, g=9.81)["h"]
    assert abs(volume_front_error(x, h, 0.05, 1000.0, exact(60.0, 0.05))) < 1e-3
    # a strip with two rows per x gives the same answer
    assert abs(volume_front_error(np.r_[x, x], np.r_[h, h], 0.05, 1000.0, exact(60.0, 0.05))) < 1e-3


def test_volume_front_ignores_a_thin_film():
    from benchmark1d2d.metrics import volume_front_position

    x = np.arange(0.5, 100.0, 1.0)
    h = np.where(x < 50, 1.0, 0.0)
    base = volume_front_position(x, h, 0.1, 0.0)
    film = volume_front_position(x, np.where(x < 50, 1.0, 1e-6), 0.1, 0.0)
    assert abs(base - 45.0) < 1e-9 and abs(film - base) < 0.01
