"""Proposed set-ups (benchmark1d2d.setups), kept outputs (benchmark1d2d.keep) and owner-run cards."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "scripts")]


def _setup(tmp_path: Path, **kw) -> Path:
    s = {"schema_version": "1.0.0", "base": "swmm524", "title": "tight iteration", "proposed_by": "Jane Doe",
         "settings": {"HEAD_TOLERANCE": "0.00001"}, "reason": "Converges the iteration on short conduits."}
    s.update(kw)
    f = tmp_path / "jane-tight" / "setup.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s), encoding="utf-8")
    return f


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    from benchmark1d2d import keep, setups

    monkeypatch.setattr(setups, "_SETUP", None)
    monkeypatch.setattr(setups, "APPLIED", {})
    monkeypatch.setattr(keep, "_CURRENT", {})


def test_check_rejects_test_settings_unknown_bases_and_bad_values() -> None:
    from benchmark1d2d import setups

    base = {"schema_version": "1.0.0", "title": "abc", "proposed_by": "Jane", "reason": "long enough reason"}
    assert setups.check({**base, "base": "swmm524", "settings": {"HEAD_TOLERANCE": "0.00001"}}) == []
    assert any("defined by the test" in p for p in setups.check({**base, "base": "swmm524", "settings": {"FLOW_ROUTING": "KINWAVE"}}))
    assert any("defined by the test" in p for p in setups.check({**base, "base": "lisflood-acc", "settings": {"DEMfile": "x.asc"}}))
    assert any("defined by the test" in p for p in setups.check({**base, "base": "telemac", "settings": {"EQUATIONS": "'SAINT-VENANT FE'"}}))
    assert any("can re-run" in p for p in setups.check({**base, "base": "hydra-uds", "settings": {"x": "1"}}))
    assert any("one simple value" in p for p in setups.check({**base, "base": "swmm524", "settings": {"HEAD_TOLERANCE": "1\n[JUNCTIONS]"}}))
    assert any("guidance_source" in p for p in setups.check({**base, "base": "swmm524", "tier": "T1", "settings": {"MAX_TRIALS": "20"}}))


def test_apply_edits_each_format_and_records_what_it_was(tmp_path, monkeypatch) -> None:
    from benchmark1d2d import setups

    (tmp_path / "m.inp").write_text("[TITLE]\nx\n\n[OPTIONS]\nFLOW_UNITS CMS\nHEAD_TOLERANCE 0.0005\n\n[JUNCTIONS]\nJ1 0\n", encoding="latin-1")
    monkeypatch.setenv("BENCH_SETUP", str(_setup(tmp_path, settings={"HEAD_TOLERANCE": "0.00001", "MAX_TRIALS": "30"})))
    done = setups.apply("swmm524", "A1F-001_x", tmp_path)
    text = (tmp_path / "m.inp").read_text(encoding="latin-1")
    assert "HEAD_TOLERANCE       0.00001" in text and "MAX_TRIALS           30" in text
    assert text.index("MAX_TRIALS") < text.index("[JUNCTIONS]")  # added inside [OPTIONS]
    assert {(c["setting"], c["was"]) for c in done} == {("HEAD_TOLERANCE", "0.0005"), ("MAX_TRIALS", None)}
    assert setups.apply("openswmm-dw", "A1F-001_x", tmp_path) == []  # another model: untouched
    card_solver = setups.decorate({"name": "EPA SWMM 5.2.4", "version": "5.2.4", "adapter": "swmm"}, "A1F-001_x")
    assert card_solver["name"].endswith("set-up “tight iteration”")
    assert card_solver["setup"]["proposed_by"] == "Jane Doe" and len(card_solver["setup"]["changes"]) == 2
    assert setups.decorate({"name": "x", "version": "1", "adapter": "a"}, "A2A-001_y")["name"] == "x"  # a test it did not touch


def test_apply_telemac_and_lisflood(tmp_path, monkeypatch) -> None:
    from benchmark1d2d import setups

    (tmp_path / "t2d.cas").write_text("FINITE VOLUME SCHEME = 1\nDESIRED COURANT NUMBER = 0.45\n", encoding="latin-1")
    monkeypatch.setenv("BENCH_SETUP", str(_setup(tmp_path, base="telemac", settings={"FINITE VOLUME SCHEME": "5"})))
    setups.apply("telemac", "A2A-001", tmp_path)
    assert "FINITE VOLUME SCHEME = 5" in (tmp_path / "t2d.cas").read_text()
    monkeypatch.setattr(setups, "_SETUP", None)
    (tmp_path / "c.par").write_text("DEMfile c.dem\nacceleration\n", encoding="ascii")
    monkeypatch.setenv("BENCH_SETUP", str(_setup(tmp_path, base="lisflood-acc", settings={"cfl": "0.5", "theta": "0.7"})))
    setups.apply("lisflood-acc", "A2A-001", tmp_path)
    par = (tmp_path / "c.par").read_text().split("\n")
    assert "cfl 0.5" in par and "theta 0.7" in par and "DEMfile c.dem" in par


def test_keep_outputs_skips_inputs_and_files_results(tmp_path, monkeypatch) -> None:
    import numpy as np

    from benchmark1d2d import keep
    from benchmark1d2d.io.results import write_results_parquet

    monkeypatch.setenv("BENCH_KEEP_INPUTS", str(tmp_path / "inputs"))
    monkeypatch.delenv("BENCH_KEEP_OUTPUTS", raising=False)
    w = tmp_path / "work"
    w.mkdir()
    (w / "m.inp").write_text("x")
    keep.inputs("swmm524", "A1D-001_v", w, 10.0, files=["m.inp"])
    (w / "m.out").write_bytes(b"\0" * 64)
    keep.outputs("swmm524", "A1D-001", w, 10.0)
    native = tmp_path / "outputs" / "swmm524" / "A1D-001" / "dx10" / "native"
    assert sorted(p.name for p in native.iterdir()) == ["m.out"]  # the input is not copied again
    write_results_parquet(tmp_path / "r" / "A1D-001_dx10.parquet", {k: np.zeros(2) for k in ("t", "x", "y", "h", "u", "v", "p")})
    assert (tmp_path / "outputs" / "swmm524" / "A1D-001" / "results" / "A1D-001_dx10.parquet").is_file()


def test_keep_does_nothing_without_the_variable(tmp_path, monkeypatch) -> None:
    from benchmark1d2d import keep

    monkeypatch.delenv("BENCH_KEEP_INPUTS", raising=False)
    monkeypatch.delenv("BENCH_KEEP_OUTPUTS", raising=False)
    assert keep.outputs("swmm524", "A1D-001", tmp_path) is None
    assert keep.result_file(tmp_path / "A1D-001.parquet") is None


def test_owner_run_scores_and_labels_the_card(tmp_path, monkeypatch) -> None:
    import run_owner

    monkeypatch.setattr(run_owner, "OUT", tmp_path / "owner")
    # the results sheets of A1F-011's download kit, as the site builds it (tests/data/owner_kit)
    kits = Path(__file__).parent / "data" / "owner_kit"
    monkeypatch.setattr(run_owner, "KITS", kits)
    cmd = f"{sys.executable} {{repo}}/scripts/owner_example.py {{test}} {{kit}} {{results}}"
    monkeypatch.setattr(sys, "argv", ["x", "--software", "Owner example", "--version", "1", "--organisation", "QA", "--command", cmd, "A1F-011"])
    assert run_owner.main() == 0
    card = json.loads(next((tmp_path / "owner" / "A1F-011").glob("*.scorecard.json")).read_text())
    assert card["solver"]["run_by"] == "owner" and card["solver"]["model_files"] is True
    assert list((tmp_path / "owner" / "A1F-011").glob("*.inputs.zip"))


def test_intake_setup_builds_and_rejects(tmp_path, monkeypatch) -> None:
    import intake_setup

    monkeypatch.setattr(intake_setup, "SETUPS", tmp_path)
    body = ("### Model\n\nswmm524 (EPA SWMM 5.2.4)\n\n### Short name\n\ntighter tolerance\n\n### Your name or organisation\n\nJane Doe\n\n"
            "### Settings\n\n```text\nHEAD_TOLERANCE 0.00001\nMAX_TRIALS = 30\n```\n\n### Tests\n\nA1F-010, A1F-011\n\n"
            "### Why these settings\n\nConverges the iteration on short conduits.\n\n### Kind of set-up\n\nAn expert's choice (T2)\n")
    (tmp_path / "b.md").write_text(body)
    monkeypatch.setattr(sys, "argv", ["x", "--issue-body", str(tmp_path / "b.md"), "--issue-number", "1", "--author", "jdoe", "--reply", str(tmp_path / "r.md")])
    assert intake_setup.main() == 0
    s = json.loads(next(tmp_path.glob("*/setup.json")).read_text())
    assert s["settings"] == {"HEAD_TOLERANCE": "0.00001", "MAX_TRIALS": "30"} and s["github_user"] == "jdoe" and s["tests"] == ["A1F-010", "A1F-011"]
    (tmp_path / "b.md").write_text(body.replace("HEAD_TOLERANCE 0.00001", "FLOW_ROUTING KINWAVE"))
    assert intake_setup.main() == 1
    assert "defined by the test" in (tmp_path / "r.md").read_text()


def test_collector_files_setup_and_owner_cards_apart() -> None:
    import collect_results

    assert collect_results.route({"solver": {"name": "EPA SWMM 5.2.4 · set-up “x”", "setup": {"slug": "jane-tight"}}}) == "setups/jane-tight"
    assert collect_results.route({"solver": {"name": "TUFLOW HPC 2025", "run_by": "owner"}}) == "owner/tuflow-hpc-2025"
    assert collect_results.route({"solver": {"name": "EPA SWMM 5.2.4"}}) == "swmm_track_a/swmm524"


def test_kwargs_setups_for_models_built_in_python(tmp_path, monkeypatch):
    """Landlab, OpenSWMM 1D/2D and HydroNet set-ups pass only the solver arguments the suite lists, with their types."""
    import json

    from benchmark1d2d import setups

    base = {"schema_version": "1.0.0", "title": "a set-up", "proposed_by": "someone", "reason": "a reason long enough"}
    assert setups.check({**base, "base": "landlab", "settings": {"h_init": "0.000001"}}) == []
    assert setups.check({**base, "base": "landlab", "settings": {"mannings_n": "0.01"}})  # the test defines roughness
    assert setups.check({**base, "base": "landlab", "settings": {"h_init": "thin"}})
    assert setups.check({**base, "base": "openswmm-2d", "settings": {"crest_at_vertex": "maybe"}})
    d = tmp_path / "landlab-x"
    d.mkdir()
    (d / "setup.json").write_text(json.dumps({**base, "base": "landlab", "tests": ["A1F-043"], "settings": {"h_init": "1e-6", "steep_slopes": "no"}}))
    monkeypatch.setenv("BENCH_SETUP", str(d / "setup.json"))
    monkeypatch.setattr(setups, "_SETUP", None, raising=False)
    monkeypatch.setattr(setups, "APPLIED", {}, raising=False)
    assert setups.kwargs("landlab", "A1F-043_lake") == {"h_init": 1e-6, "steep_slopes": False}
    assert setups.kwargs("landlab", "A1F-010_ritter") == {}
    assert setups.kwargs("hydronet-fvm", "A1F-043_lake") == {}
    card = setups.decorate({"name": "Landlab 2.11.0 OverlandFlow"}, "A1F-043_lake")
    assert card["setup"]["slug"] == "landlab-x" and {c["setting"] for c in card["setup"]["changes"]} == {"h_init", "steep_slopes"}
