#!/usr/bin/env python3
"""Build Track B ``corpus_index.parquet`` from synthetic / CSV rows.

Tag vocabulary and provenance format: HydroCouple-compatible best-effort.
# TODO(verify against openswmm.engine.benchmarks)

HydroCouple / openswmm.engine.benchmarks uses free-form string tags on models
(e.g. phenomenon and facility labels). hydrobench records the same spirit as a
list of lowercase tokens. Provenance is a source URI or repo slug plus license
id from ``DATA_LICENSES.md`` — not a fork of the upstream schema.

Best-effort tag vocabulary (extend as corpus grows):
  extran, surcharge, backwater, rtc, pump, weir, orifice, storage,
  combined_sewer, sanitary, storm, pressurized, free_surface, quality

Provenance format (best-effort):
  provenance_source := "<org>/<repo>" | "<url>" | "synthetic://hydrobench/<id>"
  license           := license id registered in DATA_LICENSES.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

# Columns required in corpus_index.parquet
COLUMNS = (
    "hash",
    "tags",
    "license",
    "provenance_source",
    "model_id",
    "tier",
    "path",
)

# Synthetic tier_pr seed rows (no large .inp files committed).
SYNTHETIC_ROWS: list[dict[str, Any]] = [
    {
        "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tags": ["extran", "surcharge", "backwater", "combined_sewer"],
        "license": "Unlicense",
        "provenance_source": "synthetic://hydrobench/B-EXTRAN-001",
        "model_id": "B-EXTRAN-001",
        "tier": "tier_pr",
        "path": "test_catalog/track_b/tier_pr/B-EXTRAN-001_extran_parity",
    },
    {
        "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tags": ["rtc", "pump", "storage"],
        "license": "synthetic-internal",
        "provenance_source": "synthetic://hydrobench/B-RTC-001",
        "model_id": "B-RTC-001",
        "tier": "tier_pr",
        "path": "test_catalog/track_b/tier_pr/B-RTC-001_rtc_rules",
    },
    {
        "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tags": ["weir", "orifice", "free_surface"],
        "license": "synthetic-internal",
        "provenance_source": "synthetic://hydrobench/B-CONTROL-001",
        "model_id": "B-CONTROL-001",
        "tier": "tier_pr",
        "path": "test_catalog/track_b/tier_pr/B-CONTROL-001_weir_orifice",
    },
    {
        "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tags": ["pressurized", "sanitary"],
        "license": "synthetic-internal",
        "provenance_source": "synthetic://hydrobench/B-FORCEMAIN-001",
        "model_id": "B-FORCEMAIN-001",
        "tier": "tier_pr",
        "path": "test_catalog/track_b/tier_pr/B-FORCEMAIN-001_forcemain",
    },
    {
        "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tags": ["storm", "quality"],
        "license": "synthetic-internal",
        "provenance_source": "synthetic://hydrobench/B-QUALITY-001",
        "model_id": "B-QUALITY-001",
        "tier": "tier_pr",
        "path": "test_catalog/track_b/tier_pr/B-QUALITY-001_washoff",
    },
]

SCHEMA_DOC = {
    "title": "hydrobench Track B corpus_index",
    "description": (
        "Index of Track B models. Tag vocabulary and provenance format are "
        "HydroCouple-compatible best-effort. "
        "TODO(verify against openswmm.engine.benchmarks)"
    ),
    "columns": {
        "hash": {"type": "string", "description": "SHA-256 of primary .inp (or placeholder)"},
        "tags": {
            "type": "list[string]|string",
            "description": "HydroCouple-style phenomenon / facility tags",
        },
        "license": {"type": "string", "description": "DATA_LICENSES.md license id"},
        "provenance_source": {
            "type": "string",
            "description": "org/repo, URL, or synthetic://hydrobench/<id>",
        },
        "model_id": {"type": "string", "description": "Stable model / case id"},
        "tier": {
            "type": "string",
            "enum": ["tier_pr", "tier_nightly", "tier_release"],
        },
        "path": {"type": "string", "description": "Repo-relative case or corpus path"},
    },
}


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        # Allow comma- or semicolon-separated strings from CSV.
        parts = [p.strip() for p in tags.replace(";", ",").split(",")]
        return [p for p in parts if p]
    if isinstance(tags, (list, tuple)):
        return [str(t).strip() for t in tags if str(t).strip()]
    return [str(tags)]


def rows_to_frame(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    records = []
    for row in rows:
        rec = {c: row.get(c) for c in COLUMNS}
        rec["tags"] = _normalize_tags(rec.get("tags"))
        records.append(rec)
    df = pd.DataFrame.from_records(records, columns=list(COLUMNS))
    return df


def load_rows_from_csv(csv_path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(csv_path)
    return df.to_dict(orient="records")


def build_corpus_index(
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    out_dir: Path | None = None,
) -> Path:
    """Write ``corpus_index.parquet`` (+ schema JSON) under ``out_dir``."""
    out_dir = Path(out_dir) if out_dir is not None else Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    source_rows: Sequence[Mapping[str, Any]] = list(rows) if rows is not None else SYNTHETIC_ROWS
    df = rows_to_frame(source_rows)

    parquet_path = out_dir / "corpus_index.parquet"
    # Store tags as JSON strings for portable Parquet (list support varies).
    store = df.copy()
    store["tags"] = store["tags"].map(lambda t: json.dumps(list(t)))
    store.to_parquet(parquet_path, index=False, engine="pyarrow")

    schema_path = out_dir / "corpus_index.schema.json"
    schema_path.write_text(json.dumps(SCHEMA_DOC, indent=2) + "\n", encoding="utf-8")
    return parquet_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Optional CSV with columns: hash,tags,license,provenance_source,model_id,tier,path",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory for corpus_index.parquet (default: this folder)",
    )
    args = parser.parse_args(argv)

    rows = load_rows_from_csv(args.csv) if args.csv else None
    path = build_corpus_index(rows, out_dir=args.out_dir)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
