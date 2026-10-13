"""Adapter: EPANET 2.2 → benchmark1d2d results Parquet.

Runs an EPANET ``.inp`` on the EPANET 2.2 library bundled with WNTR
(``wntr.epanet``, ``libepanet22``) and writes per-element extended-period
series keyed by ``element_id``:

- node rows: ``p`` = pressure [Pa] (pressure head × ρg, ρ = 1000 kg/m³), and
  hydraulic head in ``h`` [m] (the network analogue of a free-surface level)
- link rows: ``Q`` = flow [m³/s], ``u`` = velocity [m/s]

Track B pressurized parity compares a candidate's Parquet with this output.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from benchmark1d2d.io.results import write_results_parquet

RHO_G = 1000.0 * 9.81


def engine_version() -> str:
    return "2.2"


def run_to_parquet(inp: str | Path, out_parquet: str | Path) -> Path:
    import wntr

    import tempfile

    wn = wntr.network.WaterNetworkModel(str(inp))
    with tempfile.TemporaryDirectory() as td:  # WNTR writes scratch files next to file_prefix
        results = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(Path(td) / "run"), version=2.2)
    head = results.node["head"]
    pressure = results.node["pressure"]
    flow = results.link["flowrate"]
    vel = results.link["velocity"]
    t = head.index.to_numpy(dtype=np.float64)
    n_t = len(t)
    cols: dict[str, list] = {k: [] for k in ("t", "x", "h", "u", "p", "Q", "element_id", "element_type")}
    ordinal = 0
    for name in head.columns:
        cols["t"].append(t); cols["h"].append(head[name].to_numpy(float)); cols["p"].append(pressure[name].to_numpy(float) * RHO_G)
        cols["u"].append(np.full(n_t, np.nan)); cols["Q"].append(np.full(n_t, np.nan))
        cols["element_id"].append([str(name)] * n_t); cols["element_type"].append(["node"] * n_t)
        cols["x"].append(np.full(n_t, float(ordinal))); ordinal += 1
    for name in flow.columns:
        cols["t"].append(t); cols["h"].append(np.full(n_t, np.nan)); cols["p"].append(np.full(n_t, np.nan))
        cols["u"].append(vel[name].to_numpy(float)); cols["Q"].append(flow[name].to_numpy(float))
        cols["element_id"].append([str(name)] * n_t); cols["element_type"].append(["link"] * n_t)
        cols["x"].append(np.full(n_t, float(ordinal))); ordinal += 1
    flat = {k: (np.concatenate(v) if k not in ("element_id", "element_type") else sum(v, [])) for k, v in cols.items()}
    total = len(flat["t"])
    flat["y"] = np.zeros(total)
    flat["v"] = np.full(total, np.nan)
    return write_results_parquet(out_parquet, flat)


def adapt(input_path: str | Path, output_path: str | Path) -> Path:
    """Registry entry point: ``input_path`` is an EPANET ``.inp`` to run."""
    return run_to_parquet(input_path, output_path)
