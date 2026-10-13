"""EPANET 2.2 adapter stub (Track B pressurized / water-distribution parity)."""

from __future__ import annotations

from pathlib import Path


def adapt(input_path: str | Path, output_path: str | Path) -> Path:
    raise NotImplementedError(
        "epanet22 adapter is a Track B stub; pin EPANET 2.2 and implement "
        "report/binary → results Parquet conversion before use"
    )
