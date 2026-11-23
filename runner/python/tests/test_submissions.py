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
    assert any(ln.startswith("- **A1F-011**:") and "off the right answer" in ln and "PASS" not in ln for ln in lines)
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


def test_intake_records_github_account_and_keeps_others_folders(tmp_path, monkeypatch) -> None:
    """Auto-published submissions carry the sender's GitHub account; a second sender never overwrites the first."""
    import json

    import intake_submission as intake

    monkeypatch.setattr(intake, "SUBMISSIONS", tmp_path)
    ex = REPO / "submissions" / "_example"
    sheets = sorted(p for p in ex.iterdir() if p.suffix == ".csv")
    body = tmp_path / "body.md"
    body.write_text("### Software\n\nQASoft\n\n### Version\n\n1\n\n### Organisation or your name\n\nQA\n\n### Tests\n\nA1F-011\n", encoding="utf-8")
    for who in ("alice", "mallory"):
        monkeypatch.setattr(sys, "argv", ["x", "--issue-body", str(body), "--issue-number", "1", "--reply", str(tmp_path / f"{who}.md"),
                                          "--publish", "--author", who, "--local-files", *map(str, sheets)])
        assert intake.main() == 0, (tmp_path / f"{who}.md").read_text(encoding="utf-8")
    folders = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    assert folders == ["qasoft-1-qa", "qasoft-1-qa-mallory"]
    assert json.loads((tmp_path / "qasoft-1-qa" / "submission.json").read_text())["github_user"] == "alice"
