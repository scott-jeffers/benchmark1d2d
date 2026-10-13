"""OpenSWMM / HydroCouple corpus adapter stub (Track B federation)."""

from __future__ import annotations

from pathlib import Path


def adapt(input_path: str | Path, output_path: str | Path) -> Path:
    raise NotImplementedError(
        "openswmm adapter is a Track B stub; wire openswmm.engine.benchmarks "
        "result products to the benchmark1d2d Parquet contract before use"
    )
