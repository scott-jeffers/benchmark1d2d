"""Pinned SWMM metadata stays in sync with SHA256SUMS."""

from __future__ import annotations

from benchmark1d2d.catalog import find_repo_root
from benchmark1d2d.engines import assert_pin_matches_sha256sums, list_pinned_engines, load_swmm_pin


def test_pin_matches_sha256sums() -> None:
    assert_pin_matches_sha256sums(find_repo_root())


def test_load_swmm_pin_fields() -> None:
    pin = load_swmm_pin(find_repo_root())
    assert pin["engine"] == "SWMM"
    assert pin["version"] == "5.2.4"
    assert len(pin["binaries"]["swmm5.dll"]) == 64


def test_list_pinned_engines() -> None:
    engines = list_pinned_engines(find_repo_root())
    assert any(e.get("engine") == "SWMM" for e in engines)
