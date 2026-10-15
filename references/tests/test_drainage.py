"""Checks on the drainage-network exact answers (references.drainage)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from references import drainage as d

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "test_catalog" / "track_a" / "1d_drainage"


def _net(prefix: str) -> Path:
    (case,) = [p for p in CASES.iterdir() if p.name.startswith(prefix)]
    return case / "inputs" / "network.json"


def test_circular_section_limits() -> None:
    D = 1.3
    assert d.area(D, D) == pytest.approx(np.pi * D * D / 4, rel=1e-12)
    assert d.area(D / 2, D) == pytest.approx(np.pi * D * D / 8, rel=1e-12)
    assert d.perimeter(D / 2, D) == pytest.approx(np.pi * D / 2, rel=1e-12)
    assert d.top_width(D / 2, D) == pytest.approx(D, rel=1e-12)


def test_normal_depth_inverts_manning() -> None:
    y = d.normal_depth(0.5, 1.0, 0.013, 0.002)
    assert d.manning_flow(y, 1.0, 0.013, 0.002) == pytest.approx(0.5, rel=1e-10)


def test_uniform_flow_scores_interior_nodes_only() -> None:
    r = d.uniform_flow(network_path=_net("A1D-001"))
    h = dict(zip(r["element_id"], r["h"]))
    assert np.isnan(h["A0"]) and np.isnan(h["A10"])
    assert h["B5"] == pytest.approx(h["BP5"]) == pytest.approx(0.48, abs=1e-3)


def test_surcharged_grade_line_is_linear() -> None:
    r = d.surcharged_pipe(network_path=_net("A1D-002"))
    net = json.loads(_net("A1D-002").read_text())
    inv = {n["id"]: n["invert"] for n in net["junctions"] + net["outfalls"]}
    H = [r["h"][r["element_id"].index(f"S{i}")] + inv[f"S{i}"] for i in range(6)]
    assert np.allclose(np.diff(H), np.diff(H)[0], rtol=1e-12)


def test_storage_drain_satisfies_continuity() -> None:
    A, C, b, h0 = 100.0, 0.5, 0.5, 2.0
    t = np.linspace(0, 400, 4001)
    h = d.storage_depth(t, h0, A, C, b)
    dhdt = np.gradient(h, t)
    assert np.allclose(A * dhdt[1:-1], -C * h[1:-1] ** b, rtol=1e-4)


def test_pump_operating_point() -> None:
    r = d.pump_curve(network_path=_net("A1D-004"))
    h = dict(zip(r["element_id"], r["h"]))
    assert h["WW"] == pytest.approx(10.0 - (10.0 - 4.0 * 0.02 / 0.07), abs=1e-12)


def test_backwater_tends_to_normal_depth_upstream() -> None:
    r = d.backwater(network_path=_net("A1D-005"))
    h = dict(zip(r["element_id"], r["h"]))
    yn = d.normal_depth(0.6, 1.2, 0.013, 0.001)
    assert h["M20"] == pytest.approx(1.0)
    assert yn < h["M0"] < h["M10"] < h["M20"]
    assert h["M0"] - yn < 0.01
