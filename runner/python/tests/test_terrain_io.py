"""Tests for GeoTIFF/savez and UGRID-lite terrain readers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose

from benchmark1d2d.io.terrain import (
    read_terrain_savez,
    read_ugrid_lite,
    write_terrain_savez,
    write_ugrid_lite,
)


def test_savez_roundtrip(tmp_path: Path):
    elev = np.arange(12.0).reshape(3, 4)
    x = np.linspace(0.0, 3.0, 4)
    y = np.linspace(0.0, 2.0, 3)
    path = tmp_path / "terrain.npz"
    write_terrain_savez(path, elev, x=x, y=y, crs="EPSG:32632", nodata=-9999.0)
    out = read_terrain_savez(path)
    assert_allclose(out["elevation"], elev)
    assert_allclose(out["x"], x)
    assert_allclose(out["y"], y)
    assert out["crs"] == "EPSG:32632"
    assert out["nodata"] == -9999.0
    assert out["source"] == "savez"


def test_ugrid_lite_roundtrip(tmp_path: Path):
    x = [0.0, 1.0, 0.0, 1.0]
    y = [0.0, 0.0, 1.0, 1.0]
    z = [0.0, 0.1, 0.2, 0.15]
    faces = [[0, 1, 3], [0, 3, 2]]
    path = tmp_path / "mesh.json"
    write_ugrid_lite(
        path,
        x=x,
        y=y,
        z=z,
        faces=faces,
        crs="EPSG:4326",
        cell_type="triangle",
        boundaries=[{"id": "wall", "edge_nodes": [[0, 1], [1, 3]]}],
    )
    mesh = read_ugrid_lite(path)
    assert mesh["n_nodes"] == 4
    assert mesh["n_faces"] == 2
    assert_allclose(mesh["x"], x)
    assert_allclose(mesh["z"], z)
    assert mesh["cell_type"] == "triangle"
    assert mesh["boundaries"][0]["id"] == "wall"


def test_ugrid_rejects_bad_face(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(
        '{"nodes":{"x":[0,1],"y":[0,0]},"faces":[[0,1]]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="≥ 3"):
        read_ugrid_lite(path)


def test_read_geotiff_documents_dependency(tmp_path: Path):
    """Missing file raises FileNotFoundError before optional-dep logic."""
    from benchmark1d2d.io.terrain import read_geotiff

    with pytest.raises(FileNotFoundError):
        read_geotiff(tmp_path / "missing.tif")
