"""Adapter: EPA SWMM 5.x text report (.rpt) → benchmark1d2d results Parquet."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from benchmark1d2d.io.results import write_results_parquet

_NODE_DEPTH_HEADER = re.compile(r"^\s*Node\s+Depth\s+Summary\s*$", re.I)
_LINK_FLOW_HEADER = re.compile(r"^\s*Link\s+Flow\s+Summary\s*$", re.I)
_DASH_RULE = re.compile(r"^\s*-{5,}\s*$")
_STAR_RULE = re.compile(r"^\s*\*{5,}\s*$")


def _parse_float_token(tok: str) -> float | None:
    try:
        return float(tok)
    except ValueError:
        return None


def _looks_like_data_row(parts: list[str]) -> bool:
    """True when first token is an ID and a later token is numeric."""
    if len(parts) < 3:
        return False
    if _parse_float_token(parts[0]) is not None:
        return False
    return any(_parse_float_token(p) is not None for p in parts[2:])


def _consume_summary_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    """After a Summary title, skip banners/headers; collect data rows."""
    i = start
    rows: list[list[str]] = []
    seen_data = False

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            if seen_data:
                break
            i += 1
            continue

        if _STAR_RULE.match(raw):
            if seen_data:
                break
            i += 1
            continue

        # A new titled section after we already collected rows ends the table.
        if seen_data and (
            _NODE_DEPTH_HEADER.match(raw)
            or _LINK_FLOW_HEADER.match(raw)
            or (stripped.endswith("Summary") and " " in stripped)
        ):
            break

        if _DASH_RULE.match(raw):
            i += 1
            continue

        parts = stripped.split()
        if _looks_like_data_row(parts):
            rows.append(parts)
            seen_data = True
            i += 1
            continue

        # Column-header text before the first data row.
        if not seen_data:
            i += 1
            continue

        break

    return rows, i


def parse_rpt(path: str | Path) -> dict[str, Any]:
    """Parse a simplified SWMM5-like ``.rpt`` text report.

    Returns a dict with:

    - ``nodes``: list of ``{id, type, max_depth, avg_depth, ...}``
    - ``links``: list of ``{id, type, max_flow, ...}`` (may be empty)

    Extracts **Node Depth Summary** and **Link Flow Summary** tables.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if _NODE_DEPTH_HEADER.match(line):
            rows, i = _consume_summary_table(lines, i + 1)
            for parts in rows:
                if len(parts) < 4:
                    continue
                max_d = _parse_float_token(parts[2])
                avg_d = _parse_float_token(parts[3])
                if max_d is None or avg_d is None:
                    continue
                entry: dict[str, Any] = {
                    "id": parts[0],
                    "type": parts[1],
                    "max_depth": max_d,
                    "avg_depth": avg_d,
                }
                if len(parts) >= 5:
                    hgl = _parse_float_token(parts[4])
                    if hgl is not None:
                        entry["max_hgl"] = hgl
                nodes.append(entry)
            continue

        if _LINK_FLOW_HEADER.match(line):
            rows, i = _consume_summary_table(lines, i + 1)
            for parts in rows:
                if len(parts) < 3:
                    continue
                max_q = _parse_float_token(parts[2])
                if max_q is None:
                    continue
                links.append(
                    {
                        "id": parts[0],
                        "type": parts[1],
                        "max_flow": max_q,
                    }
                )
            continue

        i += 1

    return {"nodes": nodes, "links": links, "source": str(path)}


def _rpt_to_columns(parsed: dict[str, Any]) -> dict[str, np.ndarray]:
    """Map node/link summary rows onto the results column contract.

    Summary tables are not full time series. Emit one row per node (then link
    rows) at ``t=0`` with ``h`` = max depth and ``Q`` = max flow (0 on
    node-only rows). Spatial index ``x`` is the row ordinal.
    """
    nodes = parsed.get("nodes") or []
    links = parsed.get("links") or []
    n = len(nodes) + len(links)
    if n == 0:
        raise ValueError("parse_rpt found no node/link summary rows")

    t = np.zeros(n, dtype=np.float64)
    x = np.arange(n, dtype=np.float64)
    y = np.zeros(n, dtype=np.float64)
    h = np.zeros(n, dtype=np.float64)
    u = np.zeros(n, dtype=np.float64)
    v = np.zeros(n, dtype=np.float64)
    p = np.zeros(n, dtype=np.float64)
    Q = np.zeros(n, dtype=np.float64)

    for i, node in enumerate(nodes):
        h[i] = float(node["max_depth"])
    for j, link in enumerate(links):
        idx = len(nodes) + j
        Q[idx] = float(link["max_flow"])

    return {"t": t, "x": x, "y": y, "h": h, "u": u, "v": v, "p": p, "Q": Q}


def adapt_rpt_to_parquet(rpt_path: str | Path, out_parquet: str | Path) -> Path:
    """Parse ``rpt_path`` and write results Parquet via ``write_results_parquet``."""
    parsed = parse_rpt(rpt_path)
    cols = _rpt_to_columns(parsed)
    return write_results_parquet(out_parquet, cols)


def adapt(input_path: str | Path, output_path: str | Path) -> Path:
    """Registry entry point: treat ``input_path`` as a ``.rpt`` file."""
    return adapt_rpt_to_parquet(input_path, output_path)
