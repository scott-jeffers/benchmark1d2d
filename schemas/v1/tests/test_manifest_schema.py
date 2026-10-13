"""Validate hydrobench test manifests against test_manifest.schema.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMA_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = SCHEMA_DIR / "test_manifest.schema.json"
INVALID_DIR = Path(__file__).resolve().parent / "invalid"

CATALOG_MANIFESTS = [
    REPO_ROOT
    / "test_catalog/track_a/1d_free_surface/A1F-010_ritter_dry_bed_dambreak/manifest.json",
    REPO_ROOT
    / "test_catalog/track_a/1d_free_surface/A1F-011_stoker_wet_bed_dambreak/manifest.json",
    REPO_ROOT
    / "test_catalog/track_a/1d_free_surface/A1F-001_macdonald_m1_backwater/manifest.json",
    REPO_ROOT
    / "test_catalog/track_a/1d_pressurized/A1P-020_joukowsky_instant_closure/manifest.json",
    REPO_ROOT
    / "test_catalog/track_b/tier_pr/B-EXTRAN-001_extran_parity/manifest.json",
]

PRIMARY_MANIFESTS = [
    CATALOG_MANIFESTS[0],  # Ritter
    CATALOG_MANIFESTS[4],  # EXTRAN
]

INVALID_FIXTURES = [
    "no_mesh_refinement.json",
    "track_b_analytic.json",
    "citation_no_id.json",
    "weighted_no_minimum.json",
]


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("path", PRIMARY_MANIFESTS, ids=["ritter", "extran"])
def test_primary_manifests_validate(validator: Draft202012Validator, path: Path) -> None:
    assert path.is_file(), f"missing primary manifest: {path}"
    validator.validate(_load(path))


@pytest.mark.parametrize(
    "path",
    CATALOG_MANIFESTS,
    ids=["ritter", "stoker", "macdonald", "joukowsky", "extran"],
)
def test_catalog_manifests_validate(validator: Draft202012Validator, path: Path) -> None:
    assert path.is_file(), f"missing catalog manifest: {path}"
    validator.validate(_load(path))


@pytest.mark.parametrize("name", INVALID_FIXTURES)
def test_invalid_fixtures_raise(validator: Draft202012Validator, name: str) -> None:
    path = INVALID_DIR / name
    assert path.is_file(), f"missing invalid fixture: {path}"
    with pytest.raises(ValidationError):
        validator.validate(_load(path))
