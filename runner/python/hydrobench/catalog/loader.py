"""Locate the hydrobench repo root and load test manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` (or this file) until ``test_catalog`` is found."""
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in [cur, *cur.parents]:
        if (candidate / "test_catalog").is_dir() and (candidate / "schemas").is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not locate hydrobench repo root (expected test_catalog/ and schemas/)."
    )


def _catalog_root(repo: Path | None = None) -> Path:
    return (repo or find_repo_root()) / "test_catalog"


def _iter_manifest_paths(repo: Path | None = None) -> list[Path]:
    root = _catalog_root(repo)
    return sorted(root.rglob("manifest.json"))


def load_manifest(test_id_or_path: str | Path, repo: Path | None = None) -> dict[str, Any]:
    """Load a case manifest by test id prefix/full id or by filesystem path."""
    path = Path(test_id_or_path)
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        data["_manifest_path"] = str(path.resolve())
        data["_case_dir"] = str(path.resolve().parent)
        return data

    repo_root = repo or find_repo_root()
    needle = str(test_id_or_path)
    matches: list[Path] = []
    for manifest_path in _iter_manifest_paths(repo_root):
        try:
            with manifest_path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        tid = str(data.get("test_id", ""))
        if tid == needle or tid.startswith(needle) or needle in tid:
            matches.append(manifest_path)

    # Prefer exact test_id match when several prefixes collide.
    exact = []
    for mp in matches:
        with mp.open(encoding="utf-8") as fh:
            tid = json.load(fh).get("test_id", "")
        if tid == needle or tid.startswith(needle + "_") or tid == needle:
            exact.append(mp)
    if len(exact) == 1:
        matches = exact
    elif len(exact) > 1:
        # Shortest id wins for prefix queries like "A1F-010".
        matches = exact

    if not matches:
        raise FileNotFoundError(f"No catalog case matching {needle!r}")
    if len(matches) > 1:
        # Disambiguate: prefer id that starts with needle + "_" or equals needle.
        preferred = [
            m
            for m in matches
            if json.loads(m.read_text(encoding="utf-8"))["test_id"].startswith(needle)
        ]
        if len(preferred) == 1:
            matches = preferred
        else:
            ids = [json.loads(m.read_text(encoding="utf-8"))["test_id"] for m in matches]
            raise ValueError(f"Ambiguous test id {needle!r}; matches: {ids}")

    manifest_path = matches[0]
    with manifest_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    data["_manifest_path"] = str(manifest_path.resolve())
    data["_case_dir"] = str(manifest_path.resolve().parent)
    return data


def list_catalog(track: str | None = None, repo: Path | None = None) -> list[dict[str, Any]]:
    """Return summary dicts for each catalog case, optionally filtered by track."""
    repo_root = repo or find_repo_root()
    track_filter = track.upper() if track else None
    summaries: list[dict[str, Any]] = []
    for manifest_path in _iter_manifest_paths(repo_root):
        with manifest_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        case_track = str(data.get("track", ""))
        if track_filter and case_track != track_filter:
            continue
        summaries.append(
            {
                "test_id": data.get("test_id"),
                "track": case_track,
                "title": data.get("title"),
                "status": data.get("status"),
                "test_class": data.get("test_class"),
                "path": str(manifest_path.resolve()),
            }
        )
    summaries.sort(key=lambda s: str(s.get("test_id", "")))
    return summaries
