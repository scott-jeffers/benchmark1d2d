"""2D terrain I/O: GeoTIFF, numpy.savez interim rasters, and UGRID-lite JSON.

GeoTIFF reading prefers ``rasterio`` when installed. Without it, a limited
fallback attempts Pillow + numpy for single-band GeoTIFF-like files, and the
preferred interim interchange format is ``numpy.savez`` (``.npz`` / ``.npz.npz``).

UGRID-lite is a minimal JSON mesh description sufficient for catalog cases
(nodes + faces + optional boundary edge groups). It is not a full UGRID/NetCDF
implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

HAS_RASTERIO = False
try:
    import rasterio  # type: ignore

    HAS_RASTERIO = True
except ImportError:  # pragma: no cover - optional dependency
    rasterio = None  # type: ignore


def _as_path(path: str | Path) -> Path:
    return Path(path)


def read_geotiff(path: str | Path, *, band: int = 1) -> dict[str, Any]:
    """Read a single-band elevation raster from GeoTIFF (or compatible).

    Returns
    -------
    dict
        ``elevation`` (2D float64 ndarray, row-major), ``transform`` (affine
        coefficients as a 6-tuple when available), ``crs`` (string or None),
        ``nodata``, ``source`` (``\"rasterio\"`` | ``\"pillow\"`` | ``\"stub\"``).

    Notes
    -----
    Install ``rasterio`` (and GDAL) for production GeoTIFF support. Without it
    this function tries Pillow; if that also fails it raises with install
    guidance. Prefer :func:`read_terrain_npz` for dependency-light tests.
    """
    path = _as_path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    if HAS_RASTERIO:
        with rasterio.open(path) as ds:  # type: ignore[union-attr]
            elevation = ds.read(band).astype(np.float64)
            transform = tuple(ds.transform)[:6]
            crs = ds.crs.to_string() if ds.crs else None
            nodata = ds.nodata
        return {
            "elevation": elevation,
            "transform": transform,
            "crs": crs,
            "nodata": nodata,
            "source": "rasterio",
            "path": str(path),
        }

    # Pillow fallback: reads pixel values only (no georeferencing).
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "GeoTIFF reading requires 'rasterio' (preferred) or 'Pillow'. "
            "Install rasterio for CRS/transform support, or use "
            "read_terrain_savez / write_terrain_savez for interim numpy terrain."
        ) from exc

    with Image.open(path) as img:
        elevation = np.asarray(img, dtype=np.float64)
        if elevation.ndim == 3:
            elevation = elevation[:, :, min(band - 1, elevation.shape[2] - 1)]
    return {
        "elevation": elevation,
        "transform": None,
        "crs": None,
        "nodata": None,
        "source": "pillow",
        "path": str(path),
        "warning": (
            "rasterio not installed; Pillow fallback has no CRS/geotransform. "
            "Install rasterio or use the numpy.savez terrain format."
        ),
    }


def write_terrain_savez(
    path: str | Path,
    elevation: np.ndarray,
    *,
    x: np.ndarray | None = None,
    y: np.ndarray | None = None,
    crs: str | None = None,
    nodata: float | None = None,
    transform: Sequence[float] | None = None,
) -> Path:
    """Write an interim raster terrain as ``numpy.savez`` (``.npz``).

    Arrays stored: ``elevation``; optional ``x``, ``y`` (cell centres or edges),
    ``transform`` (length-6), ``crs`` (unicode), ``nodata``.
    """
    path = _as_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"elevation": np.asarray(elevation, dtype=np.float64)}
    if x is not None:
        payload["x"] = np.asarray(x, dtype=np.float64)
    if y is not None:
        payload["y"] = np.asarray(y, dtype=np.float64)
    if transform is not None:
        payload["transform"] = np.asarray(list(transform)[:6], dtype=np.float64)
    if crs is not None:
        payload["crs"] = np.asarray(crs)
    if nodata is not None:
        payload["nodata"] = np.asarray(float(nodata))
    np.savez(path, **payload)
    return path


def read_terrain_savez(path: str | Path) -> dict[str, Any]:
    """Read interim terrain written by :func:`write_terrain_savez`."""
    path = _as_path(path)
    with np.load(path, allow_pickle=False) as data:
        if "elevation" not in data:
            raise KeyError(f"{path}: missing 'elevation' array")
        out: dict[str, Any] = {
            "elevation": np.asarray(data["elevation"], dtype=np.float64),
            "source": "savez",
            "path": str(path),
        }
        if "x" in data:
            out["x"] = np.asarray(data["x"], dtype=np.float64)
        if "y" in data:
            out["y"] = np.asarray(data["y"], dtype=np.float64)
        if "transform" in data:
            out["transform"] = tuple(float(v) for v in np.asarray(data["transform"]).ravel()[:6])
        if "crs" in data:
            crs_arr = data["crs"]
            out["crs"] = str(crs_arr.item() if hasattr(crs_arr, "item") else crs_arr)
        if "nodata" in data:
            out["nodata"] = float(np.asarray(data["nodata"]).ravel()[0])
        else:
            out["nodata"] = None
    return out


def read_ugrid_lite(path: str | Path) -> dict[str, Any]:
    """Read a UGRID-lite JSON mesh description.

    Expected keys
    -------------
    ``nodes.x``, ``nodes.y`` (required); ``nodes.z`` (optional elevation);
    ``faces`` — list of node-index polygons (triangles or quads);
    ``boundaries`` — optional list of ``{id, edge_nodes}`` groups;
    ``crs``, ``schema_version``, ``cell_type`` optional metadata.
    """
    path = _as_path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("UGRID-lite root must be a JSON object")

    nodes = data.get("nodes") or {}
    if "x" not in nodes or "y" not in nodes:
        raise KeyError("UGRID-lite requires nodes.x and nodes.y")
    x = np.asarray(nodes["x"], dtype=np.float64)
    y = np.asarray(nodes["y"], dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("nodes.x and nodes.y must have the same shape")
    z = np.asarray(nodes["z"], dtype=np.float64) if "z" in nodes else None
    if z is not None and z.shape != x.shape:
        raise ValueError("nodes.z must match nodes.x shape")

    faces_raw = data.get("faces") or []
    faces = [np.asarray(f, dtype=np.int64) for f in faces_raw]
    for f in faces:
        if f.ndim != 1 or f.size < 3:
            raise ValueError("each face must be a 1D index list with ≥ 3 nodes")
        if np.any(f < 0) or np.any(f >= x.size):
            raise ValueError("face node index out of range")

    return {
        "schema_version": data.get("schema_version", "1.0.0"),
        "format": data.get("format", "ugrid-lite"),
        "crs": data.get("crs"),
        "cell_type": data.get("cell_type"),
        "x": x,
        "y": y,
        "z": z,
        "faces": faces,
        "boundaries": list(data.get("boundaries") or []),
        "attributes": dict(data.get("attributes") or {}),
        "path": str(path),
        "n_nodes": int(x.size),
        "n_faces": len(faces),
    }


def write_ugrid_lite(
    path: str | Path,
    *,
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
    faces: Sequence[Sequence[int]],
    z: Sequence[float] | np.ndarray | None = None,
    crs: str | None = None,
    cell_type: str | None = None,
    boundaries: Sequence[Mapping[str, Any]] | None = None,
    schema_version: str = "1.0.0",
    attributes: Mapping[str, Any] | None = None,
) -> Path:
    """Write a UGRID-lite JSON mesh (pretty-printed, UTF-8)."""
    path = _as_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    if x_arr.shape != y_arr.shape:
        raise ValueError("x and y must have the same length")
    nodes: dict[str, Any] = {
        "x": x_arr.tolist(),
        "y": y_arr.tolist(),
    }
    if z is not None:
        z_arr = np.asarray(z, dtype=float).ravel()
        if z_arr.shape != x_arr.shape:
            raise ValueError("z must match x length")
        nodes["z"] = z_arr.tolist()

    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "format": "ugrid-lite",
        "nodes": nodes,
        "faces": [list(map(int, f)) for f in faces],
    }
    if crs is not None:
        payload["crs"] = crs
    if cell_type is not None:
        payload["cell_type"] = cell_type
    if boundaries:
        payload["boundaries"] = list(boundaries)
    if attributes:
        payload["attributes"] = dict(attributes)

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
