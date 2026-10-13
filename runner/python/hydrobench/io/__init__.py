"""Results Parquet and 2D terrain I/O for the hydrobench output contract."""

from hydrobench.io.results import (
    read_results_parquet,
    validate_results_columns,
    write_results_parquet,
)
from hydrobench.io.terrain import (
    HAS_RASTERIO,
    read_geotiff,
    read_terrain_savez,
    read_ugrid_lite,
    write_terrain_savez,
    write_ugrid_lite,
)

__all__ = [
    "write_results_parquet",
    "read_results_parquet",
    "validate_results_columns",
    "HAS_RASTERIO",
    "read_geotiff",
    "read_terrain_savez",
    "write_terrain_savez",
    "read_ugrid_lite",
    "write_ugrid_lite",
]
