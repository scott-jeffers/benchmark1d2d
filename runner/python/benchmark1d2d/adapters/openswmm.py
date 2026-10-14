"""OpenSWMM Engine (HydroCouple's SWMM 6) adapter.

`openswmm <https://github.com/HydroCouple/openswmm.engine>`_ is a community
continuation of EPA SWMM with a rewritten C++20 engine (v6). Its Python wheel
ships two engines: ``openswmm.legacy`` (EPA SWMM 5.x, unmodified) and
``openswmm.engine`` (the new v6 engine). This adapter runs the **new** engine.

The v6 engine writes the standard SWMM binary output file (same magic number
and layout, version field 60000), so results are read with the SWMM 5 adapter.
The engine runs in a separate interpreter (``python``) so it can live in its
own environment, exactly as the SWMM 5.1.15 candidate does.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from benchmark1d2d.adapters import swmm5

# Runs one model with the v6 engine and prints "openswmm <version>".
RUN = (
    "import os, sys\n"
    "import openswmm\n"
    "from openswmm.engine import Solver\n"
    "inp = os.path.abspath(sys.argv[1])\n"
    "os.chdir(os.path.dirname(inp))\n"
    "with Solver(inp, sys.argv[2], sys.argv[3]) as s:\n"
    "    while s.step():\n"
    "        pass\n"
    "print('openswmm', openswmm.__version__)\n"
)


def run(python: str, inp: Path, rpt: Path, out: Path, timeout: float | None = None) -> str:
    """Run ``inp`` with the v6 engine in ``python``; return the engine version."""
    proc = subprocess.run([python, "-c", RUN, str(Path(inp).resolve()), str(Path(rpt).resolve()), str(Path(out).resolve())],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0 or not Path(out).is_file() or Path(out).stat().st_size == 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        raise RuntimeError(tail[-1][:300] if tail else f"exit {proc.returncode}")
    return proc.stdout.strip().split()[-1]


def adapt(input_path: str | Path, output_path: str | Path, python: str = "python") -> Path:
    """Run a SWMM input with the v6 engine and write the Parquet results."""
    with tempfile.TemporaryDirectory() as td:
        rpt, out = Path(td) / "m.rpt", Path(td) / "m.out"
        run(python, Path(input_path), rpt, out)
        return swmm5.adapt_out_to_parquet(out, Path(output_path))
