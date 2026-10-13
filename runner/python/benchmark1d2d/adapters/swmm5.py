"""Adapters for EPA SWMM 5.x → benchmark1d2d results Parquet.

Two paths:

- **Binary output (preferred).** ``run_swmm`` runs an ``.inp`` on the EPA SWMM
  5.2.4 engine bundled in ``swmm-toolkit`` and ``adapt_out_to_parquet`` reads the
  binary ``.out`` into full per-element time series (node depth ``h``, link
  flow ``Q`` and velocity ``u``) keyed by ``element_id``. This is what Track B
  parity scores.
- **Text report (legacy).** ``adapt_rpt_to_parquet`` reads only the Node Depth
  and Link Flow *summary* tables (one maximum per element); useful when only a
  ``.rpt`` is available.
"""

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


# ── Binary .out path ─────────────────────────────────────────────────────────


def engine_version() -> str:
    """Version of the SWMM engine bundled in swmm-toolkit (e.g. ``5.2.4``)."""
    from swmm.toolkit import solver

    return str(solver.swmm_version_info())


def run_swmm(inp: str | Path, workdir: str | Path) -> tuple[Path, Path]:
    """Run ``inp`` on the bundled SWMM engine; return ``(rpt, out)`` paths.

    Runs with the model's own directory as working directory so relative
    rainfall / time-series file references resolve.
    """
    import os

    from swmm.toolkit import solver

    inp = Path(inp).resolve()
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    rpt = workdir / (inp.stem + ".rpt")
    out = workdir / (inp.stem + ".out")
    cwd = os.getcwd()
    try:
        os.chdir(inp.parent)
        solver.swmm_run(str(inp), str(rpt), str(out))
    finally:
        os.chdir(cwd)
    return rpt, out


def _clean_name(name: str) -> str:
    """Element names are raw bytes in the .out file; Latin-1 bytes (e.g. "ó")
    reach Python as surrogate escapes, which cannot be written to Parquet."""
    try:
        name.encode("utf-8")
        return name
    except UnicodeEncodeError:
        return name.encode("utf-8", "surrogateescape").decode("latin-1")


def read_out(out_path: str | Path) -> dict[str, Any]:
    """Read node depth and link flow/velocity series from a SWMM binary .out."""
    from swmm.toolkit import output, shared_enum

    handle = output.init()
    output.open(handle, str(out_path))
    try:
        n_sub, n_node, n_link, _n_poll = output.get_proj_size(handle)[:4]
        n_per = output.get_times(handle, shared_enum.Time.NUM_PERIODS)
        step = output.get_times(handle, shared_enum.Time.REPORT_STEP)
        t = np.arange(1, n_per + 1, dtype=np.float64) * float(step)
        nodes, links = {}, {}
        for i in range(n_node):
            name = _clean_name(output.get_elem_name(handle, shared_enum.ElementType.NODE, i))
            nodes[name] = np.asarray(
                output.get_node_series(handle, i, shared_enum.NodeAttribute.INVERT_DEPTH, 0, n_per - 1), dtype=np.float64
            )
        for i in range(n_link):
            name = _clean_name(output.get_elem_name(handle, shared_enum.ElementType.LINK, i))
            q = output.get_link_series(handle, i, shared_enum.LinkAttribute.FLOW_RATE, 0, n_per - 1)
            v = output.get_link_series(handle, i, shared_enum.LinkAttribute.FLOW_VELOCITY, 0, n_per - 1)
            links[name] = (np.asarray(q, dtype=np.float64), np.asarray(v, dtype=np.float64))
        flow_units = output.get_units(handle)
    finally:
        output.close(handle)
    return {"t": t, "nodes": nodes, "links": links, "units": flow_units}


def adapt_out_to_parquet(out_path: str | Path, out_parquet: str | Path) -> Path:
    """Write per-element series from a SWMM ``.out`` to the results contract.

    Node rows carry ``h`` (depth above invert); link rows carry ``Q`` (flow) and
    ``u`` (velocity). Values stay in the model's own units, so a candidate and
    its reference are always compared in the same units.
    """
    data = read_out(out_path)
    t = data["t"]
    n_t = len(t)
    cols: dict[str, list] = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "Q", "element_id", "element_type")}
    ordinal = 0
    for name, depth in data["nodes"].items():
        cols["t"].append(t); cols["h"].append(depth); cols["Q"].append(np.full(n_t, np.nan))
        cols["u"].append(np.full(n_t, np.nan)); cols["element_id"].append([name] * n_t)
        cols["element_type"].append(["node"] * n_t); cols["x"].append(np.full(n_t, float(ordinal))); ordinal += 1
    for name, (q, vel) in data["links"].items():
        cols["t"].append(t); cols["h"].append(np.full(n_t, np.nan)); cols["Q"].append(q)
        cols["u"].append(vel); cols["element_id"].append([name] * n_t)
        cols["element_type"].append(["link"] * n_t); cols["x"].append(np.full(n_t, float(ordinal))); ordinal += 1
    flat = {k: np.concatenate(v) if k not in ("element_id", "element_type") else sum(v, []) for k, v in cols.items() if v}
    total = len(flat["t"])
    for k in ("y", "v", "p"):
        flat[k] = np.zeros(total) if k == "y" else np.full(total, np.nan)
    return write_results_parquet(out_parquet, flat)


def run_to_parquet(inp: str | Path, out_parquet: str | Path, workdir: str | Path | None = None) -> Path:
    """Run ``inp`` on SWMM 5.2.4 and write its full results Parquet."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        _rpt, out = run_swmm(inp, workdir or td)
        return adapt_out_to_parquet(out, out_parquet)
