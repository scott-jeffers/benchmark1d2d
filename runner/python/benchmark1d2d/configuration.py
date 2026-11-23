"""Model configurations (protocol 4.0).

Each published model has one record under ``configurations/<key>.json``
(schema: ``schemas/v1/configuration.schema.json``): the engine build, the
configuration tier and every setting that differs from the engine's default.
Results are always shown with their configuration, and results of different
tiers are never compared as if alike.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO / "configurations"
SCHEMA = REPO / "schemas" / "v1" / "configuration.schema.json"

TIERS = {
    "T0": ("Out of the box", "The engine's defaults, plus only what the case defines: geometry, boundaries, friction, grid."),
    "T1": ("Documented guidance", "Only changes the developer's own published guidance recommends for this kind of flow, each with its source."),
    "T2": ("Expert", "Any setting the engine exposes, chosen by a named person or group."),
}

AUDIT = {
    "automatic": "Settings changed from default are found by comparing the model files with the engine's defaults on every run.",
    "manual": "Settings changed from default were checked by hand against the engine's documentation.",
    "pending": "Only the changes the runner makes on purpose are listed; a full comparison with the engine's defaults is still to do.",
}


def load(config_dir: Path = CONFIG_DIR) -> dict[str, dict]:
    """Every configuration record, by model key."""
    out = {}
    for p in sorted(config_dir.glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        out[rec["key"]] = rec
    return out


def for_submission(sub: dict, key: str) -> dict:
    """The configuration of a submitted result: tier T2, set by its submitter."""
    solver = sub.get("solver") or {}
    return {
        "schema_version": "1.0.0",
        "key": key,
        "engine": {"name": str(solver.get("name", key)), "version": str(solver.get("version", ""))},
        "tier": sub.get("tier") or "T2",
        "set_by": str(sub.get("submitted_by", "submitter")),
        "changed_from_default": list(sub.get("changed_from_default") or []),
        "defaults_audit": "manual" if sub.get("changed_from_default") else "pending",
        "notes": str(solver.get("options", "")),
    }
