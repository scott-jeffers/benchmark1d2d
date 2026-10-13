"""Scoring must compare against the case's real reference — never against itself.

Regression tests for the parity stub that compared results with themselves
(any solver passed Track B) and for cases with missing references.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from benchmark1d2d.catalog import load_manifest
from benchmark1d2d.io.results import read_results_parquet, write_results_parquet
from benchmark1d2d.scoring.scorer import ReferenceUnavailable, certification_claims, score_case

REPO = Path(__file__).resolve().parents[3]
TS = "2024-01-01T00:00:00Z"


def _ref_path(manifest: dict) -> Path:
    return Path(manifest["_case_dir"]) / manifest["reference"]["results_path"]


def _perturb(src: Path, dst: Path, col: str, factor: float, element: str | None = None) -> Path:
    df = read_results_parquet(src)
    mask = df[col].notna()
    if element is not None:
        mask &= df["element_id"] == element
    df.loc[mask, col] = df.loc[mask, col] * factor
    cols = {c: df[c].to_numpy() for c in df.columns}
    return write_results_parquet(dst, cols)


@pytest.mark.parametrize("case", ["B-EXTRAN-001", "B-RTC-001", "B-EPANET-001"])
def test_reference_engine_scores_itself_as_pass(case: str) -> None:
    m = load_manifest(case, repo=REPO)
    card = score_case(m, _ref_path(m), timestamp=TS)
    assert card["passed"] is True
    for row in card["criteria_results"]:
        assert row["observed"] == pytest.approx(0.0, abs=1e-9)
        assert "worst of" in row["detail"]


def test_perturbed_flows_fail_parity_and_name_the_element(tmp_path: Path) -> None:
    m = load_manifest("B-RTC-001", repo=REPO)
    bad = _perturb(_ref_path(m), tmp_path / "bad.parquet", "Q", 1.05, element="U433_Psan_1_ou_2")
    card = score_case(m, bad, timestamp=TS)
    assert card["passed"] is False
    vol = next(r for r in card["criteria_results"] if r["id"] == "link_volume")
    assert vol["observed"] == pytest.approx(5.0, rel=1e-6)
    assert "U433_Psan_1_ou_2" in vol["detail"]
    assert card["certification_claims"] == []


def test_identical_results_without_reference_are_not_scored(tmp_path: Path) -> None:
    m = load_manifest("B-EXTRAN-001", repo=REPO)
    m["reference"].pop("results_path")
    with pytest.raises(ReferenceUnavailable):
        score_case(m, _ref_path(load_manifest("B-EXTRAN-001", repo=REPO)), timestamp=TS)


def test_results_without_element_ids_are_rejected(tmp_path: Path) -> None:
    m = load_manifest("B-EXTRAN-001", repo=REPO)
    df = read_results_parquet(_ref_path(m)).drop(columns=["element_id", "element_type"])
    p = write_results_parquet(tmp_path / "noid.parquet", {c: df[c].to_numpy() for c in df.columns})
    with pytest.raises(ValueError, match="element_id"):
        score_case(m, p, timestamp=TS)


def test_measured_case_without_data_is_not_scored(tmp_path: Path) -> None:
    m = load_manifest("A2L-EA6A", repo=REPO)
    n = 4
    p = write_results_parquet(tmp_path / "r.parquet", {k: np.zeros(n) for k in ("t", "x", "y", "h", "u", "v", "p")})
    with pytest.raises(ReferenceUnavailable, match="request_from_authors"):
        score_case(m, p, timestamp=TS)


def _flat_grid(h_value: float, t_end: float, dx: float = 50.0) -> dict[str, np.ndarray]:
    xs = np.arange(dx / 2, 1000, dx)
    ys = np.arange(dx / 2, 2000, dx)
    X, Y = np.meshgrid(xs, ys)
    n = X.size
    return {"t": np.full(n, t_end), "x": X.ravel(), "y": Y.ravel(), "h": np.full(n, h_value),
            "u": np.zeros(n), "v": np.zeros(n), "p": np.zeros(n)}


def test_intercomparison_mass_check_on_ea4(tmp_path: Path) -> None:
    m = load_manifest("A2C-EA4", repo=REPO)
    stored = m["reference"]["expected_states"][0]["value"]
    assert stored == pytest.approx(285000.0)
    depth = stored / (1000.0 * 2000.0)
    good = write_results_parquet(tmp_path / "good.parquet", _flat_grid(depth, m["simulation"]["t_end"]))
    card = score_case(m, good, timestamp=TS)
    assert card["passed"] is True
    assert card["certification_claims"] == ["A-C"]
    leaky = write_results_parquet(tmp_path / "leaky.parquet", _flat_grid(depth * 0.99, m["simulation"]["t_end"]))
    card = score_case(m, leaky, timestamp=TS)
    assert card["passed"] is False
    assert card["criteria_results"][0]["observed"] == pytest.approx(-1.0, rel=1e-6)


def test_claims_follow_class_and_tolerance() -> None:
    assert certification_claims(load_manifest("A1F-010", repo=REPO), True) == ["A-V"]
    assert certification_claims(load_manifest("A2L-EA6A", repo=REPO), True) == ["A-L"]
    assert certification_claims(load_manifest("B-RTC-001", repo=REPO), True) == ["B-2%"]
    assert certification_claims(load_manifest("B-EXTRAN-001", repo=REPO), True) == ["B-1%"]
    assert certification_claims(load_manifest("B-EXTRAN-001", repo=REPO), False) == []


def test_probe_on_a_cell_face_uses_one_cell_for_depth_and_bed(tmp_path: Path) -> None:
    """A gauge exactly between cells must not mix one cell's depth with another's bed."""
    m = load_manifest("A2C-EA1", repo=REPO)
    xs = np.arange(5.0, 700.0, 10.0)
    ys = np.arange(5.0, 100.0, 10.0)
    X, Y = np.meshgrid(xs, ys)
    z = 9.0 + 0.004 * X  # sloping bed; probes P1 (400, 50) and P2 (600, 50) sit on faces
    level = 10.25
    h = level - z
    n = X.size
    rows = {"x": [], "y": [], "h": [], "z": [], "t": []}
    for t in (0.0, 72000.0):
        rows["x"].append(X.ravel()); rows["y"].append(Y.ravel()); rows["h"].append(h.ravel())
        rows["z"].append(z.ravel()); rows["t"].append(np.full(n, t))
    cols = {k: np.concatenate(v) for k, v in rows.items()}
    total = len(cols["t"])
    cols.update(u=np.zeros(total), v=np.zeros(total), p=np.zeros(total))
    path = write_results_parquet(tmp_path / "flat.parquet", cols)
    card = score_case(m, path, timestamp=TS)
    finals = {r["id"]: r for r in card["criteria_results"]}
    assert finals["final_level_p1"]["observed"] == pytest.approx(0.0, abs=1e-9)
    assert finals["final_level_p2"]["observed"] == pytest.approx(0.0, abs=1e-9)


def test_verify_card_detects_tampering_and_flags_dev_key(tmp_path: Path, capsys) -> None:
    import json

    from benchmark1d2d.cli.main import main as cli

    card_path = REPO / "site/fixtures/scorecards/A2C-EA1_disconnected_water_body.scorecard.json"
    assert cli(["verify-card", str(card_path)]) == 0
    assert "development key" in capsys.readouterr().out
    card = json.loads(card_path.read_text())
    card["criteria_results"][0]["observed"] = 0.0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(card))
    assert cli(["verify-card", str(bad)]) == 1
