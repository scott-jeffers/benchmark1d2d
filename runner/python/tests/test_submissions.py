"""The submission pipeline and the per-case kit, on the worked example."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))


def test_example_submission_scores(tmp_path, monkeypatch) -> None:
    import score_submissions as ss

    monkeypatch.setattr(ss, "OUT", tmp_path)
    lines, problems = ss.score_folder(REPO / "submissions" / "_example", ss._key())
    assert problems == []
    # the example is the demo solver: its rate range straddles 0.8, so method 2 calls it inconclusive
    assert any("**A1F-011**: INCONCLUSIVE" in ln for ln in lines)
    card = next(tmp_path.rglob("*.scorecard.json")).read_text(encoding="utf-8")
    assert '"submitted_by":"benchmark1d2d maintainers"' in card


def test_malformed_submission_is_reported(tmp_path) -> None:
    import score_submissions as ss

    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "submission.json").write_text('{"schema_version": "1.0.0", "solver": {"name": "x"}}', encoding="utf-8")
    lines, problems = ss.score_folder(bad, ss._key())
    assert lines == [] and problems


def test_kit_lists_network_elements() -> None:
    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.catalog.kit import kit_files

    kit = kit_files(load_manifest("A1D-005", repo=REPO))
    rows = list(csv.reader(io.StringIO(kit["RESULTS_TEMPLATE.csv"])))
    assert rows[0][-2:] == ["element_id", "element_type"]
    ids = {r[-2] for r in rows[1:]}
    assert {"M0", "M20", "MP1", "MP20"} <= ids
    assert "benchmark1d2d score A1D-005" in kit["HOW_TO_SUBMIT.md"]
