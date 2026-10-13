"""Passthrough adapter for solvers that already emit the results Parquet."""

from __future__ import annotations

import shutil
from pathlib import Path

from benchmark1d2d.io.results import read_results_parquet, write_results_parquet


def adapt(input_path: str | Path, output_path: str | Path) -> Path:
    """Validate Parquet at ``input_path`` and write/copy to ``output_path``."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = read_results_parquet(input_path)
    if input_path.resolve() == output_path.resolve():
        return output_path

    # Prefer a byte-identical copy when already valid; fall back to rewrite.
    try:
        shutil.copy2(input_path, output_path)
        read_results_parquet(output_path)
        return output_path
    except OSError:
        cols = {c: df[c].to_numpy() for c in df.columns}
        return write_results_parquet(output_path, cols)
