"""Keeping the model files a runner writes, and zipping them reproducibly."""

import importlib.util
import zipfile
from pathlib import Path

from benchmark1d2d import keep

REPO = Path(__file__).resolve().parents[3]


def test_inputs_is_a_no_op_without_the_variable(tmp_path, monkeypatch):
    monkeypatch.delenv("BENCH_KEEP_INPUTS", raising=False)
    (tmp_path / "m.inp").write_text("[TITLE]\n")
    assert keep.inputs("swmm524", "A1D-001_x", tmp_path, 1.0) is None


def test_inputs_copies_model_files_but_not_outputs(tmp_path, monkeypatch):
    src, root = tmp_path / "work", tmp_path / "kept"
    src.mkdir()
    (src / "c.par").write_text("sim_time 60\n")
    (src / "c.dem").write_text("ncols 2\n")
    (src / "old.rpt").write_text("report\n")
    (src / "fort.q0001").write_text("output\n")
    monkeypatch.setenv("BENCH_KEEP_INPUTS", str(root))
    dest = keep.inputs("lisflood-fv1", "A1F-010_ritter_dry_bed_dambreak", src, 1.25)
    assert dest == root / "lisflood-fv1" / "A1F-010" / "dx1.25"
    assert sorted(p.name for p in dest.iterdir()) == ["c.dem", "c.par"]


def test_inputs_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCH_KEEP_INPUTS", str(tmp_path / "kept"))
    assert keep.inputs("x", "A1F-001", tmp_path / "missing", files=["nope.inp"]) is not None


def test_export_zips_are_byte_identical(tmp_path):
    spec = importlib.util.spec_from_file_location("export_inputs", REPO / "scripts" / "export_inputs.py")
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)
    folder = tmp_path / "swmm524" / "A1D-001" / "model"
    folder.mkdir(parents=True)
    (folder / "m.inp").write_text("[OPTIONS]\nFLOW_UNITS CMS\n")
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    ex.zip_folder(tmp_path / "swmm524" / "A1D-001", a)
    ex.zip_folder(tmp_path / "swmm524" / "A1D-001", b)
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as z:
        assert sorted(z.namelist()) == ["SHA256SUMS", "model/m.inp"]
