"""Output adapters that normalize solver products to the results contract."""

from benchmark1d2d.adapters import epanet22, generic_parquet, openswmm, swmm5

REGISTRY = {
    "generic_parquet": generic_parquet,
    "swmm5": swmm5,
    "epanet22": epanet22,
    "openswmm": openswmm,
}

__all__ = ["REGISTRY", "generic_parquet", "swmm5", "epanet22", "openswmm"]
