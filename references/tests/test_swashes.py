"""Checks on the SWASHES bump-channel references."""

from __future__ import annotations

import numpy as np
import pytest

from references import swashes as s

X = np.linspace(0.0, 25.0, 2501)


@pytest.mark.parametrize("case", ["subcritical", "transcritical", "shock"])
def test_discharge_constant_and_head_conserved_between_shocks(case: str) -> None:
    r = s.steady_bump(X, case=case)
    q = s.CASES[case]["q"]
    assert np.allclose(r["h"] * r["u"], q, rtol=1e-12)
    head = q * q / (2 * s.G * r["h"] ** 2) + r["h"] + r["z"]
    if case == "shock":
        xs = s.shock_position()
        for part in (X < xs - 1e-6, X > xs + 1e-6):
            assert np.ptp(head[part]) < 1e-10
    else:
        assert np.ptp(head) < 1e-10


def test_critical_at_crest() -> None:
    q = s.CASES["transcritical"]["q"]
    h = s.steady_bump(np.array([10.0]), case="transcritical")["h"][0]
    assert h == pytest.approx((q * q / s.G) ** (1 / 3), rel=1e-9)


def test_jump_satisfies_rankine_hugoniot() -> None:
    xs = s.shock_position()
    assert 11.6 < xs < 11.7
    h1 = s.steady_bump(np.array([xs - 1e-9]), case="shock")["h"][0]
    h2 = s.steady_bump(np.array([xs + 1e-9]), case="shock")["h"][0]
    q = 0.18
    m = lambda h: q * q / h + 0.5 * s.G * h * h  # noqa: E731
    assert h1 < h2
    assert m(h1) == pytest.approx(m(h2), rel=1e-7)


def test_lake_at_rest() -> None:
    r = s.lake_at_rest(X)
    dry = (X > 10 - np.sqrt(2) + 1e-9) & (X < 10 + np.sqrt(2) - 1e-9)
    assert np.all(r["h"][dry] == 0.0) and np.all(r["u"] == 0.0)
    assert np.allclose((r["h"] + r["z"])[~dry], 0.1)
