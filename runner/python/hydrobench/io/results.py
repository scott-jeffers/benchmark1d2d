"""Read/write the hydrobench results Parquet contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("t", "x", "y", "h", "u", "v", "p")
OPTIONAL_COLUMNS = ("Q", "c")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def validate_results_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure required columns exist; return a copy with float64 dtypes."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"results missing required columns: {missing}")
    unknown = [c for c in df.columns if c not in ALL_COLUMNS]
    if unknown:
        raise ValueError(f"results has unknown columns: {unknown}")
    out = df.copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(np.float64)
    return out


def write_results_parquet(path: str | Path, columns: Mapping[str, Any]) -> Path:
    """Write results Parquet from a mapping of column name → array-like."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, np.ndarray] = {}
    for name in REQUIRED_COLUMNS:
        if name not in columns:
            raise ValueError(f"write_results_parquet requires column {name!r}")
        data[name] = np.asarray(columns[name], dtype=np.float64)
    n = len(data["t"])
    for name, arr in data.items():
        if len(arr) != n:
            raise ValueError(f"column {name!r} length {len(arr)} != {n}")

    for name in OPTIONAL_COLUMNS:
        if name in columns:
            arr = np.asarray(columns[name], dtype=np.float64)
            if len(arr) != n:
                raise ValueError(f"column {name!r} length {len(arr)} != {n}")
            data[name] = arr

    df = pd.DataFrame(data)
    validate_results_columns(df)
    df.to_parquet(path, index=False, engine="pyarrow")
    return path


def read_results_parquet(path: str | Path) -> pd.DataFrame:
    """Read and validate a results Parquet file."""
    path = Path(path)
    df = pd.read_parquet(path, engine="pyarrow")
    return validate_results_columns(df)
