"""Hydra (NEER AI) adapter: run the ``hydra`` CLI and read its results.

`Hydra <https://github.com/neeraip/hydra>`_ is a Rust water-infrastructure
engine (AGPL-3.0 or commercial) with a water-distribution engine (``wds``) on
the EPANET data model and an urban-drainage engine (``uds``) on the SWMM data
model. It is run here as a black box through its CLI::

    hydra run model.inp --engine wds|uds --results model.out --summary model.rpt --quiet

Its results files are EPANET- and SWMM-compatible binaries, so they are read
with the same readers as the reference engines: WNTR's EPANET binary reader
(converted to SI) for ``wds``, the suite's SWMM ``.out`` reader for ``uds``.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def version(exe: str | Path) -> str:
    """``"<library>/<cli>"``, e.g. ``"17.0.0/4.1.1"``."""
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True).stdout
    lib = cli = "?"
    for line in out.splitlines():
        if line.lower().startswith("hydra version"):
            lib = line.split(":")[-1].strip()
        if line.lower().startswith("cli version"):
            cli = line.split(":")[-1].strip()
    return f"{lib}/{cli}"


def run(exe: str | Path, inp: Path, rpt: Path, out: Path, engine: str, timeout: float | None = None,
        extra: list[str] | None = None) -> None:
    """Run ``inp`` with Hydra's ``engine`` (``wds`` or ``uds``); raise on failure.

    ``extra`` are further CLI options, e.g. ``["--tank-tolerance", "0"]`` for
    EPANET's first-order tank stepping.
    """
    inp = Path(inp).resolve()
    proc = subprocess.run([str(exe), "run", str(inp), "--engine", engine, "--results", str(Path(out).resolve()),
                           "--summary", str(Path(rpt).resolve()), "--quiet", *(extra or [])],
                          capture_output=True, text=True, timeout=timeout, cwd=str(inp.parent))
    if proc.returncode != 0 or not Path(out).is_file() or Path(out).stat().st_size == 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        raise RuntimeError(tail[-1][:300] if tail else f"hydra exit {proc.returncode}")


def epanet_results(out: Path):
    """WNTR results object (SI units) from an EPANET-format binary written by Hydra."""
    from wntr.epanet.io import BinFile

    return BinFile().read(str(out))


def adapt(input_path: str | Path, output_path: str | Path, exe: str = "hydra", engine: str = "uds") -> Path:
    """Run a model with Hydra and write the results Parquet (same layout as the reference adapters)."""
    from benchmark1d2d.adapters import epanet22, swmm5

    with tempfile.TemporaryDirectory() as td:
        rpt, out = Path(td) / "m.rpt", Path(td) / "m.out"
        run(exe, Path(input_path), rpt, out, engine)
        if engine == "wds":
            return epanet22.results_to_parquet(epanet_results(out), Path(output_path))
        return swmm5.adapt_out_to_parquet(out, Path(output_path))
