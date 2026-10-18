"""Read/write the benchmark1d2d results Parquet contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("t", "x", "y", "h", "u", "v", "p")
OPTIONAL_COLUMNS = ("Q", "c", "z", "V")  # V: volume account [m³] (coupled 1D/2D cases)
STRING_COLUMNS = ("element_id", "element_type")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS + STRING_COLUMNS


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
        if col in STRING_COLUMNS:
            out[col] = out[col].astype(str)
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype(np.float64)
    return out


WALL_KEY = b"benchmark1d2d.wall_seconds"
ENGINE_KEY = b"benchmark1d2d.engine_report"


def write_results_parquet(path: str | Path, columns: Mapping[str, Any], wall_seconds: float | None = None,
                          engine_report: dict | None = None) -> Path:
    """Write results Parquet from a mapping of column name → array-like.

    ``wall_seconds``: how long the run that produced these results took (the
    runner writing the model, the engine running, its results read back). It is
    kept in the file's metadata and carried into the score card with the machine
    it ran on.

    ``engine_report``: what the engine said about its own run (``benchmark1d2d.engine_report``:
    unconverged steps, continuity errors), kept in the metadata and carried into the card.
    """
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
    for name in STRING_COLUMNS:
        if name in columns:
            arr = np.asarray(columns[name], dtype=object).astype(str)
            if len(arr) != n:
                raise ValueError(f"column {name!r} length {len(arr)} != {n}")
            df[name] = arr
    validate_results_columns(df)
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df, preserve_index=False)
    if wall_seconds is not None and wall_seconds == wall_seconds:
        meta = dict(table.schema.metadata or {})
        meta[WALL_KEY] = f"{float(wall_seconds):.3f}".encode()
        table = table.replace_schema_metadata(meta)
    if engine_report:
        import json as _json

        meta = dict(table.schema.metadata or {})
        meta[ENGINE_KEY] = _json.dumps(engine_report, sort_keys=True).encode()
        table = table.replace_schema_metadata(meta)
    pq.write_table(table, path)
    return path


def results_wall_seconds(path: str | Path) -> float | None:
    """The run time a results file carries (``write_results_parquet(..., wall_seconds=)``), if any."""
    try:
        import pyarrow.parquet as pq

        meta = pq.read_schema(path).metadata or {}
        v = meta.get(WALL_KEY)
        return float(v) if v is not None else None
    except Exception:  # noqa: BLE001
        return None


def results_engine_report(path: str | Path) -> dict | None:
    """The engine's own report on the run a results file carries, if any."""
    try:
        import json as _json

        import pyarrow.parquet as pq

        v = (pq.read_schema(path).metadata or {}).get(ENGINE_KEY)
        return _json.loads(v) if v else None
    except Exception:  # noqa: BLE001
        return None


# Column names people write in their own tools, mapped to the results contract (lower case, units stripped).
ALIASES = {
    "time": "t", "time_s": "t", "depth": "h", "water_depth": "h", "velocity": "u", "u_velocity": "u", "x_velocity": "u",
    "v_velocity": "v", "y_velocity": "v", "pressure": "p", "flow": "Q", "discharge": "Q", "q": "Q",
    "concentration": "c", "bed": "z", "bed_level": "z", "bed_elevation": "z", "invert": "z", "volume": "V",
    "id": "element_id", "element": "element_id", "name": "element_id", "node": "element_id", "type": "element_type",
}


def normalise_results_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Accept a results sheet as people fill it in: names in any case, with units in brackets
    ("Depth (m)"), common aliases ("depth", "velocity", "flow"), the contract's optional columns left out,
    and extra columns (notes, other variables) ignored."""
    import re as _re

    rename = {}
    for col in df.columns:
        raw = str(col).strip()
        if raw in ALL_COLUMNS:
            continue
        key = _re.sub(r"\s*[\(\[].*?[\)\]]\s*", "", raw).strip().lower().replace(" ", "_")
        target = key if key in ALL_COLUMNS else ("Q" if key == "q" else ("V" if key == "v_m3" else ALIASES.get(key)))
        if target and target not in df.columns and target not in rename.values():
            rename[col] = target
    out = df.rename(columns=rename)
    out = out[[c for c in out.columns if c in ALL_COLUMNS]].copy()
    for c in REQUIRED_COLUMNS:
        if c not in out.columns:
            out[c] = np.nan
    return out


def read_results_parquet(path: str | Path) -> pd.DataFrame:
    """Read and validate a results file: Parquet, or CSV with the same columns.

    CSV is accepted so a results template filled in by hand or by any tool can
    be scored directly; empty cells are read as missing values. Column names are
    matched loosely (``normalise_results_columns``).
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, sep=None, engine="python")
        for col in df.columns:  # decimal commas ("0,5") in a semicolon-separated sheet
            if not pd.api.types.is_numeric_dtype(df[col]) and df[col].astype(str).str.fullmatch(r"\s*-?\d+,\d+([eE][-+]?\d+)?\s*|\s*").all():
                df[col] = df[col].astype(str).str.replace(",", ".", regex=False)
        if "element_id" in df.columns:
            df["element_id"] = df["element_id"].astype(str)
    else:
        df = pd.read_parquet(path, engine="pyarrow")
    df = normalise_results_columns(df)
    if "element_id" in df.columns:
        df["element_id"] = df["element_id"].astype(str)
    return validate_results_columns(df)
