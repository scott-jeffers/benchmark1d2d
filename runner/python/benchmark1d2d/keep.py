"""Keep a copy of the model files a runner writes, so anyone can re-run them.

Every solver runner writes its model (a SWMM ``.inp``, a TELEMAC steering
file and mesh, a HEC-RAS project, a LISFLOOD-FP ``.par`` and rasters, ...)
from the test's own files, usually in a temporary folder. When the
environment variable ``BENCH_KEEP_INPUTS`` names a folder, ``inputs`` copies
those files, before the solver runs, to::

    $BENCH_KEEP_INPUTS/<model key>/<test id>/<level>/

The solver workflows set it, ``scripts/export_inputs.py`` zips the result per
test and model, and the site offers each zip on the test page ("Check this
result"). Without the variable, ``inputs`` does nothing. It never raises:
keeping a copy must not break a run.

The other half of a result is what the solver wrote back. After a run,
``outputs`` copies the files in the same folder that were not there as inputs
(a SWMM ``.out``/``.rpt``, a TELEMAC ``res.slf``, HEC-RAS plan HDF, LISFLOOD-FP
rasters, GeoClaw ``fort.*``) to::

    <outputs root>/<model key>/<test id>/<level>/native/

and ``result_file`` (called by ``write_results_parquet``) copies the results
file the scorer reads to ``.../<level>/results/``. The outputs root is
``BENCH_KEEP_OUTPUTS``, or ``outputs`` beside ``BENCH_KEEP_INPUTS``. Together
with the inputs, anyone with the software can check a result end to end.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

MAX_FILE_BYTES = 25 * 1024 * 1024  # skip anything this large (a stray output, a big restart file)
MAX_OUTPUT_FILE_BYTES = 150 * 1024 * 1024  # outputs go to release files, not the website, so they may be larger
_CURRENT: dict[str, tuple[str, str]] = {}  # test id -> (model key, level) of the last kept inputs in this process
SKIP_SUFFIXES = {".out", ".rpt", ".log", ".pyc"}  # inputs are kept before the solver runs, so outputs are not there yet


def _level(level) -> str:
    if level is None or level == "":
        return "model"
    if isinstance(level, (int, float)):
        return f"dx{level:g}"
    return str(level)


def inputs(model_key: str, test_id: str, src, level=None, files=None) -> Path | None:
    """Copy the model files in ``src`` (a folder, or the given ``files`` in it) for this model, test and level."""
    root = os.environ.get("BENCH_KEEP_INPUTS")
    if not root:
        return None
    try:
        src = Path(src)
        dest = Path(root) / model_key / test_id.split("_")[0] / _level(level)
        dest.mkdir(parents=True, exist_ok=True)
        _CURRENT[test_id.split("_")[0]] = (model_key, _level(level))
        paths = [src / f for f in files] if files else [p for p in src.rglob("*") if p.is_file()]
        for p in paths:
            if (not p.is_file() or p.suffix.lower() in SKIP_SUFFIXES or p.name.startswith("fort.")
                    or p.stat().st_size > MAX_FILE_BYTES):
                continue
            rel = p.relative_to(src) if p.is_relative_to(src) else Path(p.name)
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest / rel)
        return dest
    except Exception as exc:  # noqa: BLE001 - keeping a copy must never break a run
        print(f"keep.inputs: {model_key} {test_id} {level}: {exc}", file=sys.stderr)
        return None


def _outputs_root() -> Path | None:
    out = os.environ.get("BENCH_KEEP_OUTPUTS")
    if out:
        return Path(out)
    inp = os.environ.get("BENCH_KEEP_INPUTS")
    return Path(inp).parent / "outputs" if inp else None


def _same(a: Path, b: Path) -> bool:
    try:
        return a.is_file() and b.is_file() and a.stat().st_size == b.stat().st_size and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def outputs(model_key: str, test_id: str, src, level=None, files=None) -> Path | None:
    """After the solver ran: copy what it wrote in ``src`` (everything that was not a kept input) for this model, test and level."""
    root = _outputs_root()
    if root is None:
        return None
    try:
        src = Path(src)
        sid = test_id.split("_")[0]
        kept_in = Path(os.environ.get("BENCH_KEEP_INPUTS", "")) / model_key / sid / _level(level)
        dest = root / model_key / sid / _level(level) / "native"
        dest.mkdir(parents=True, exist_ok=True)
        skipped = []
        paths = [src / f for f in files] if files else [p for p in src.rglob("*") if p.is_file()]
        for p in paths:
            if not p.is_file() or p.suffix.lower() == ".pyc":
                continue
            rel = p.relative_to(src) if p.is_relative_to(src) else Path(p.name)
            if _same(p, kept_in / rel):
                continue  # an input, already in the inputs zip
            size = p.stat().st_size
            if size > MAX_OUTPUT_FILE_BYTES:
                skipped.append(f"{rel.as_posix()}  {size / 1e6:.0f} MB")
                continue
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest / rel)
        if skipped:
            (dest / "NOT_INCLUDED.txt").write_text("Files the solver wrote that are too large to publish:\n" + "\n".join(skipped) + "\n", encoding="utf-8")
        return dest
    except Exception as exc:  # noqa: BLE001 - keeping a copy must never break a run
        print(f"keep.outputs: {model_key} {test_id} {level}: {exc}", file=sys.stderr)
        return None


def result_file(path) -> Path | None:
    """Copy a results file the scorer will read, filed under the model whose inputs were last kept for its test."""
    root = _outputs_root()
    if root is None:
        return None
    try:
        path = Path(path)
        sid = path.name.split("_")[0].split(".")[0]
        if sid not in _CURRENT:
            return None
        model_key, _lvl = _CURRENT[sid]
        dest = root / model_key / sid / "results"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest / path.name)
        return dest / path.name
    except Exception as exc:  # noqa: BLE001
        print(f"keep.result_file: {path}: {exc}", file=sys.stderr)
        return None


def script_model(model_key: str, test_id: str, level, builder, settings: dict | None = None) -> Path | None:
    """For a model built in Python (ANUGA, Landlab, HydroNet): keep the code that builds it, which is its input file.

    Writes ``model.py`` (the function that builds and runs this test's model), the whole runner script it
    comes from, and ``settings.json`` (the solver's own settings for the run), then registers the model like
    ``inputs`` does.
    """
    root = os.environ.get("BENCH_KEEP_INPUTS")
    if not root:
        return None
    try:
        import inspect
        import json

        sid = test_id.split("_")[0]
        dest = Path(root) / model_key / sid / _level(level)
        dest.mkdir(parents=True, exist_ok=True)
        _CURRENT[sid] = (model_key, _level(level))
        src_file = Path(inspect.getsourcefile(builder) or "")
        header = (f"# The function that builds and runs {sid} for {model_key} at grid level {_level(level)}.\n"
                  f"# It comes from {src_file.name} (copied beside this file), which is run with the test's manifest;\n"
                  "# see README in the test's download for the exact command.\n\n")
        (dest / "model.py").write_text(header + inspect.getsource(builder), encoding="utf-8")
        if src_file.is_file():
            shutil.copy2(src_file, dest / src_file.name)
        if settings:
            (dest / "settings.json").write_text(json.dumps(settings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return dest
    except Exception as exc:  # noqa: BLE001 - keeping a copy must never break a run
        print(f"keep.script_model: {model_key} {test_id} {level}: {exc}", file=sys.stderr)
        return None
