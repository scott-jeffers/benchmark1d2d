"""Steady looped pipe network by the Todini–Pilati global gradient algorithm.

References
----------
Todini, E., and Pilati, S. (1988). "A gradient algorithm for the analysis of
pipe networks." *Computer Applications in Water Supply, Vol. 1*, Research
Studies Press, 1–20.
Alperovits, E., and Shamir, U. (1977). "Design of optimal water distribution
systems." *Water Resour. Res.*, 13(6), 885–900. https://doi.org/10.1029/WR013i006p00885

The network (nodes, pipes, demands, Hazen–Williams C) is read from the case's
``inputs/network.json``. Head loss uses the SI Hazen–Williams form EPANET 2.2
applies, ``h_f = 10.667 C^-1.852 D^-4.871 L Q^1.852``. The system is solved to
``|ΔH| < 1e-12`` m, which is the reference; tests cross-check it against
EPANET 2.2 (WNTR's bundled ``libepanet22``).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HW_SI = 10.667


def _resistance(pipe: dict) -> float:
    return HW_SI * pipe["C"] ** -1.852 * pipe["D"] ** -4.871 * pipe["L"]


def solve_network(network: dict, tol: float = 1e-12, max_iter: int = 200) -> dict:
    """Return converged nodal heads [m] and pipe flows [m³/s]."""
    nodes = [n["id"] for n in network["junctions"]]
    fixed = {r["id"]: float(r["head"]) for r in network["reservoirs"]}
    idx = {nid: i for i, nid in enumerate(nodes)}
    demand = np.array([n["demand_m3s"] for n in network["junctions"]], dtype=float)
    pipes = network["pipes"]
    n_p, n_n = len(pipes), len(nodes)
    A12 = np.zeros((n_p, n_n))
    A10h = np.zeros(n_p)
    for k, p in enumerate(pipes):
        for end, sign in ((p["from"], -1.0), (p["to"], 1.0)):
            if end in idx:
                A12[k, idx[end]] = sign
            else:
                A10h[k] += sign * fixed[end]
    R = np.array([_resistance(p) for p in pipes])
    Q = np.full(n_p, 0.1)
    H = np.zeros(n_n)
    for _ in range(max_iter):
        aq = np.maximum(np.abs(Q), 1e-10)
        a11 = R * aq**0.852  # head loss = a11 * Q
        d = 1.0 / (1.852 * a11)  # inverse Jacobian of the head-loss term
        # Energy residual per pipe: H_from - H_to - h_f = 0, written as a11 Q + A12 H + A10h
        F1 = a11 * Q + A12 @ H + A10h
        # Continuity residual per junction: inflow - outflow - demand
        F2 = A12.T @ Q - demand
        M = A12.T @ (d[:, None] * A12)
        dH = np.linalg.solve(M, F2 - A12.T @ (d * F1))
        Q = Q - d * (F1 + A12 @ dH)
        H = H + dH
        if np.max(np.abs(dH)) < tol:
            break
    return {"nodes": nodes, "head": H, "pipes": [p["id"] for p in pipes], "flow": Q}


def steady_network(x=None, t: float = 0.0, network_path: str | None = None, network: dict | None = None, demand_scale: float = 1.0) -> dict:
    """Generator entry point: returns heads/flows keyed by element id."""
    if network is None:
        if network_path is None:
            raise ValueError("pass network_path or network")
        network = json.loads(Path(network_path).read_text(encoding="utf-8"))
    net = json.loads(json.dumps(network))
    for j in net["junctions"]:
        j["demand_m3s"] *= demand_scale
    sol = solve_network(net)
    return {
        "element_id": sol["nodes"] + sol["pipes"],
        "H": np.concatenate([sol["head"], np.full(len(sol["pipes"]), np.nan)]),
        "Q": np.concatenate([np.full(len(sol["nodes"]), np.nan), sol["flow"]]),
    }
