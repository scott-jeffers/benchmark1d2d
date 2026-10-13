"""Tests for the Darcy–Weisbach, Ogata–Banks, Bélanger and Todini generators."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from references.belanger import sequent_depth_ratio, sequent_depths
from references.darcy_weisbach import colebrook_white, head_loss
from references.ogata_banks import concentration
from references.todini import solve_network

REPO = Path(__file__).resolve().parents[2]
NET = REPO / "test_catalog/track_a/1d_pressurized/A1P-010_todini_multiloop/inputs/network.json"


def test_darcy_weisbach_closed_form() -> None:
    r = head_loss(np.array([0.0, 500.0, 1000.0]), L=1000.0, D=0.3, V=1.0, f=0.02, H0=100.0)
    expected = 0.02 * (1000.0 / 0.3) * 1.0**2 / (2 * 9.81)
    assert r["head_loss_total"] == pytest.approx(expected, rel=1e-12)
    assert r["H"][-1] == pytest.approx(100.0 - expected)
    assert r["H"][1] == pytest.approx(100.0 - expected / 2)


def test_colebrook_matches_moody_values() -> None:
    # Smooth pipe, Re = 1e5: Prandtl–Kármán value ≈ 0.0180
    assert colebrook_white(1e5, 0.0) == pytest.approx(0.0180, abs=2e-4)
    assert colebrook_white(1000.0, 0.0) == pytest.approx(0.064)


def test_ogata_banks_boundary_and_limits() -> None:
    x = np.linspace(0, 1000, 2001)
    c = concentration(x, 3600.0, u=0.1, D=0.01, c0=1.0)["c"]
    assert c[0] == pytest.approx(1.0, abs=1e-12)
    assert c[-1] == pytest.approx(0.0, abs=1e-12)
    # Front sits at u t = 360 m where c ≈ 0.5
    assert np.interp(360.0, x, c) == pytest.approx(0.5, abs=0.01)
    assert np.all(np.diff(c) <= 1e-12)


def test_ogata_banks_high_peclet_is_finite() -> None:
    c = concentration(np.linspace(0, 5000, 101), 10000.0, u=1.0, D=1e-4)["c"]
    assert np.all(np.isfinite(c))


def test_belanger_ratio_and_momentum() -> None:
    assert sequent_depth_ratio(2.5) == pytest.approx((np.sqrt(51.0) - 1.0) / 2.0)
    r = sequent_depths(np.array([10.0, 90.0]), Fr1=2.5, h1=0.2)
    g, q, h1, h2 = 9.81, r["q"], r["h1"], r["h2"]
    momentum = lambda h: q**2 / (g * h) + h**2 / 2  # noqa: E731
    assert momentum(h1) == pytest.approx(momentum(h2), rel=1e-12)
    assert r["Fr2"] < 1.0
    with pytest.raises(ValueError):
        sequent_depth_ratio(0.8)


def test_todini_continuity_and_energy() -> None:
    net = json.loads(NET.read_text())
    sol = solve_network(net)
    flows = dict(zip(sol["pipes"], sol["flow"]))
    heads = dict(zip(sol["nodes"], sol["head"]))
    heads.update({r["id"]: r["head"] for r in net["reservoirs"]})
    for j in net["junctions"]:
        inflow = sum(flows[p["id"]] for p in net["pipes"] if p["to"] == j["id"])
        outflow = sum(flows[p["id"]] for p in net["pipes"] if p["from"] == j["id"])
        assert inflow - outflow == pytest.approx(j["demand_m3s"], abs=1e-12)
    for p in net["pipes"]:
        q = flows[p["id"]]
        hf = 10.667 * p["C"] ** -1.852 * p["D"] ** -4.871 * p["L"] * abs(q) ** 1.852 * np.sign(q)
        assert heads[p["from"]] - heads[p["to"]] == pytest.approx(hf, abs=1e-9)


def test_todini_matches_epanet_22(tmp_path: Path) -> None:
    wntr = pytest.importorskip("wntr")
    net = json.loads(NET.read_text())
    sol = solve_network(net)
    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.headloss = "H-W"
    wn.options.hydraulic.accuracy = 1e-9
    for r in net["reservoirs"]:
        wn.add_reservoir(r["id"], base_head=r["head"])
    for j in net["junctions"]:
        wn.add_junction(j["id"], base_demand=j["demand_m3s"], elevation=j["elevation"])
    for p in net["pipes"]:
        wn.add_pipe(p["id"], p["from"], p["to"], length=p["L"], diameter=p["D"], roughness=p["C"], minor_loss=0.0)
    res = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(tmp_path / "run"), version=2.2)
    h = res.node["head"].iloc[0]
    for n, v in zip(sol["nodes"], sol["head"]):
        assert h[n] == pytest.approx(v, abs=1e-3)
