"""Scoring paths added with the pipe-network, tracer, jump and water-hammer cases.

Each test feeds a case the exact answer (must pass) and a plausible wrong one
(must fail), so a metric that cannot tell them apart is caught.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from benchmark1d2d.catalog import load_manifest
from benchmark1d2d.io.results import write_results_parquet
from benchmark1d2d.scoring.scorer import score_case
from references.darcy_weisbach import head_loss
from references.ogata_banks import concentration
from references.todini import steady_network

REPO = Path(__file__).resolve().parents[3]
TS = "2024-01-01T00:00:00Z"


def _cols(n: int, **kw) -> dict:
    nan = np.full(n, np.nan)
    base = {k: nan.copy() for k in ("t", "x", "y", "h", "u", "v", "p")}
    base["t"] = np.zeros(n)
    base.update(kw)
    return base


def _crit(card: dict, cid: str) -> dict:
    return next(r for r in card["criteria_results"] if r["id"] == cid)


def test_head_loss_passes_exact_and_fails_wrong_friction(tmp_path: Path) -> None:
    m = load_manifest("A1P-001", repo=REPO)
    prm = m["reference"]["generator"]["parameters"]
    x = np.linspace(0.0, prm["L"], 11)
    exact = head_loss(x, **prm)["h"]
    ok = score_case(m, write_results_parquet(tmp_path / "ok.parquet", _cols(len(x), x=x, h=exact)), timestamp=TS)
    assert ok["passed"] and not ok.get("convergence_result")  # not applicable for a steady network
    # f = 0.02 (the old fixed value) instead of Colebrook's 0.0182: a 9.8 % error in head loss.
    wrong = prm["H0"] - (prm["H0"] - exact) * 0.02 / head_loss(x, **prm)["friction_factor"]
    bad = score_case(m, write_results_parquet(tmp_path / "bad.parquet", _cols(len(x), x=x, h=wrong)), timestamp=TS)
    assert not _crit(bad, "head_loss")["passed"]


def test_network_reference_aligns_on_type_and_id(tmp_path: Path) -> None:
    """Node "2" and pipe "2" share a name; scoring must not mix them up."""
    m = load_manifest("A1P-010", repo=REPO)
    ref = steady_network(network_path=str(Path(m["_case_dir"]) / "inputs/network.json"))
    n = len(ref["element_id"])
    order = np.arange(n)[::-1]  # deliberately shuffled
    cols = _cols(n, x=np.arange(n, dtype=float), h=np.asarray(ref["h"])[order], Q=np.asarray(ref["Q"])[order])
    cols["element_id"] = [ref["element_id"][i] for i in order]
    cols["element_type"] = [ref["element_type"][i] for i in order]
    card = score_case(m, write_results_parquet(tmp_path / "net.parquet", cols), timestamp=TS)
    assert card["passed"], card["criteria_results"]
    q = np.asarray(cols["Q"]).copy()
    q[np.isfinite(q)] *= 1.01  # 1 % flow error everywhere
    cols["Q"] = q
    bad = score_case(m, write_results_parquet(tmp_path / "bad.parquet", cols), timestamp=TS)
    assert not _crit(bad, "link_flow")["passed"]


def test_storage_balance_is_exact_for_a_smeared_but_conservative_front(tmp_path: Path) -> None:
    m = load_manifest("A1P-020", repo=REPO)
    prm = m["reference"]["generator"]["parameters"]
    t = float(m["simulation"]["t_end"])
    x = np.linspace(0.0, prm["L"], 401)
    dp = prm["rho"] * prm["a"] * prm["V0"]
    front = prm["L"] - prm["a"] * t
    smeared = dp * 0.5 * (1.0 + np.tanh((x - front) / 20.0))  # a front smeared over ~80 m, same area as the step
    ok = score_case(m, write_results_parquet(tmp_path / "ok.parquet", _cols(len(x), t=np.full(len(x), t), x=x, p=smeared, u=np.zeros(len(x)))), timestamp=TS)
    assert abs(_crit(ok, "storage_balance")["observed"]) < 1e-3
    leaky = score_case(m, write_results_parquet(tmp_path / "bad.parquet", _cols(len(x), t=np.full(len(x), t), x=x, p=smeared * 0.97, u=np.zeros(len(x)))), timestamp=TS)
    assert not _crit(leaky, "storage_balance")["passed"]


def test_relative_norm_and_tracer_mass(tmp_path: Path) -> None:
    m = load_manifest("A1P-030", repo=REPO)
    prm = m["reference"]["generator"]["parameters"]
    t = float(m["simulation"]["t_end"])
    x = (np.arange(2000) + 0.5) * 0.5
    c = concentration(x, t, **prm)["c"]
    ok = score_case(m, write_results_parquet(tmp_path / "ok.parquet", _cols(len(x), t=np.full(len(x), t), x=x, c=c, u=np.full(len(x), 0.1))), timestamp=TS)
    assert _crit(ok, "concentration_L1")["passed"] and _crit(ok, "mass")["passed"]
    lost = score_case(m, write_results_parquet(tmp_path / "bad.parquet", _cols(len(x), t=np.full(len(x), t), x=x, c=c * 0.95, u=np.full(len(x), 0.1))), timestamp=TS)
    assert not _crit(lost, "concentration_L1")["passed"]  # 5 % > 2 %
    assert not _crit(lost, "mass")["passed"]


def test_promotion_checklist_reports_real_blockers() -> None:
    from benchmark1d2d.catalog.promotion import next_stage

    draft = load_manifest("A2F-001", repo=REPO)
    ids = {b["id"] for b in next_stage(draft, [])["blockers"]}
    assert {"licence", "inputs", "reference"} <= ids
    cand = load_manifest("A1F-010", repo=REPO)
    card = {"test_id": cand["test_id"], "passed": True, "solver": {"name": "demo"}, "convergence_result": {"passed": True}}
    other = {**card, "solver": {"name": "another code"}}
    assert {b["id"] for b in next_stage(cand, [card])["blockers"]} == {"independent", "review"}
    assert {b["id"] for b in next_stage(cand, [card, other])["blockers"]} == {"review"}
