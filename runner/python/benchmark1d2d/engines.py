"""Pinned reference-engine metadata (SWMM, etc.)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark1d2d.catalog import find_repo_root


def _parse_sha256sums(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1].lower()
    return out


def load_swmm_pin(repo: Path | None = None) -> dict[str, Any]:
    """Load ``reference_engines/swmm-5.2.4/pin.json``."""
    root = repo or find_repo_root()
    pin_path = root / "reference_engines" / "swmm-5.2.4" / "pin.json"
    data = json.loads(pin_path.read_text(encoding="utf-8"))
    data["_pin_path"] = str(pin_path)
    data["_engine_dir"] = str(pin_path.parent)
    return data


def assert_pin_matches_sha256sums(repo: Path | None = None) -> None:
    """Raise ``ValueError`` if pin.json binaries disagree with SHA256SUMS."""
    root = repo or find_repo_root()
    engine_dir = root / "reference_engines" / "swmm-5.2.4"
    pin = json.loads((engine_dir / "pin.json").read_text(encoding="utf-8"))
    sums = _parse_sha256sums(engine_dir / "SHA256SUMS")
    binaries = pin.get("binaries") or {}
    for name, digest in binaries.items():
        expected = sums.get(name)
        if expected is None:
            raise ValueError(f"{name} in pin.json but missing from SHA256SUMS")
        if digest.lower() != expected:
            raise ValueError(f"PIN MISMATCH {name}: pin={digest} sums={expected}")
    for name in sums:
        if name not in binaries:
            raise ValueError(f"{name} in SHA256SUMS but missing from pin.json")


def list_pinned_engines(repo: Path | None = None) -> list[dict[str, Any]]:
    """Return machine-readable pin records for CLI / site."""
    root = repo or find_repo_root()
    engines: list[dict[str, Any]] = []
    swmm_dir = root / "reference_engines" / "swmm-5.2.4"
    if (swmm_dir / "pin.json").is_file():
        pin = load_swmm_pin(root)
        engines.append(pin)
    return engines
