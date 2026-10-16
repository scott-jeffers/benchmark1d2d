"""Keep a copy of the model files a runner writes, so anyone can re-run them.

Every solver runner writes its model (a SWMM ``.inp``, a TELEMAC steering
file and mesh, a HEC-RAS project, a LISFLOOD-FP ``.par`` and rasters, ...)
from the test's own files, usually in a temporary folder. When the
environment variable ``BENCH_KEEP_INPUTS`` names a folder, ``inputs`` copies
those files, before the solver runs, to::

    $BENCH_KEEP_INPUTS/<model key>/<test id>/<level>/

The solver workflows set it, ``scripts/export_inputs.py`` zips the result per
test and model, and the site offers each zip on the test page ("Run it
yourself"). Without the variable, ``inputs`` does nothing. It never raises:
keeping a copy must not break a run.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

MAX_FILE_BYTES = 25 * 1024 * 1024  # skip anything this large (a stray output, a big restart file)
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
