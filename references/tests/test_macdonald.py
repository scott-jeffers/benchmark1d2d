"""Tests for MacDonald analytic bed construction."""

import numpy as np
from numpy.testing import assert_allclose

from references.macdonald import (
    M1_PARAMS,
    bed_elevation,
    depth_profile,
    gvf_residual,
    manning_friction,
)


def test_m1_depth_positive_and_peaked_at_mid():
    x = np.linspace(0.0, M1_PARAMS["L"], 401)
    h = depth_profile(x, case="m1", g=9.81)
    assert np.all(h > 0.0)
    assert h[np.argmin(np.abs(x - 500.0))] == np.max(h)


def test_bed_construction_gvf_consistency():
    """Constructed bed satisfies the steady GVF residual to truncation error."""
    x = np.linspace(0.0, M1_PARAMS["L"], 2001)
    h = depth_profile(x, case="m1")
    zb = bed_elevation(x, case="m1")
    residual = gvf_residual(
        x,
        h,
        zb,
        Q=M1_PARAMS["Q"],
        B=M1_PARAMS["B"],
        n_manning=M1_PARAMS["n_manning"],
        g=9.81,
    )
    # Exclude a few end points where np.gradient is less accurate.
    assert_allclose(residual[5:-5], 0.0, atol=5e-4)


def test_steady_mass_conservation_constant_Q():
    """Discharge is prescribed constant ⇒ discrete dQ/dx ~ 0."""
    x = np.linspace(0.0, M1_PARAMS["L"], 501)
    h = depth_profile(x, case="m1")
    Q = np.full_like(h, M1_PARAMS["Q"])
    dQ_dx = np.gradient(Q, x)
    assert_allclose(dQ_dx, 0.0, atol=1e-15)

    # Sanity: friction slope finite and positive.
    Sf = manning_friction(h, M1_PARAMS["Q"], M1_PARAMS["B"], M1_PARAMS["n_manning"])
    assert np.all(Sf > 0.0)


def test_bed_monotone_overall_drop():
    """M1 backwater: bed falls overall from upstream to downstream."""
    x = np.linspace(0.0, M1_PARAMS["L"], 501)
    zb = bed_elevation(x, case="m1", zb0=0.0)
    assert zb[-1] < zb[0]
