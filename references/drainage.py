"""Exact answers for drainage networks (link–node models such as SWMM).

Each case's network (nodes, conduits, outlets, pumps, inflows) is read from
its ``inputs/network.json``; every generator returns values keyed by element
id, so any link–node engine can be scored node by node and link by link.

Variables returned
------------------
``h``  depth above the element's invert [m] (node depth; for a conduit, its
       flow depth, NaN where a depth is not defined)
``Q``  link flow [m³/s] (NaN on nodes)

Geometry of a circular pipe of diameter ``D`` flowing at depth ``y``, with
``θ = 2 arccos(1 − 2y/D)``::

    A = D²(θ − sin θ)/8,  P = Dθ/2,  T = D sin(θ/2)

Friction is Manning's (SI): ``Q = A R^(2/3) S^(1/2) / n``.

Generators
----------
``uniform_flow``     normal depth in circular pipes on a constant grade
``surcharged_pipe``  full pipes between an inflow and a fixed outfall stage
                     above the crown: the hydraulic grade line falls by
                     ``n² Q² L / (A² R^(4/3))`` along each pipe
``storage_drain``    a prismatic storage emptying through a power-law outlet
                     ``Q = C h^b``: ``h^(1−b) = h0^(1−b) − (1−b) C t / A``
``pump_curve``       a wet well pumped against a fixed outfall stage on a
                     piecewise-linear head–flow curve: at steady state the pump
                     passes the inflow, so the head rise is read off the curve
``backwater``        gradually varied flow (M1 curve) in a chain of circular
                     pipes, integrated upstream from a fixed outfall stage with
                     an adaptive 8th-order Runge–Kutta to 1e-11
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

G = 9.80665


# ── circular section ────────────────────────────────────────────────────────


def theta(y, D):
    return 2.0 * np.arccos(np.clip(1.0 - 2.0 * np.asarray(y, float) / D, -1.0, 1.0))


def area(y, D):
    th = theta(y, D)
    return D * D * (th - np.sin(th)) / 8.0


def perimeter(y, D):
    return D * theta(y, D) / 2.0


def top_width(y, D):
    return D * np.sin(theta(y, D) / 2.0)


def manning_flow(y, D, n, S):
    a, p = area(y, D), perimeter(y, D)
    return a * (a / p) ** (2.0 / 3.0) * np.sqrt(S) / n


def normal_depth(Q, D, n, S, tol=1e-13):
    """Normal depth (below the 0.938 D flow maximum) by bisection."""
    lo, hi = 1e-9 * D, 0.9381 * D
    if manning_flow(hi, D, n, S) < Q:
        raise ValueError(f"Q = {Q} exceeds the pipe's open-channel capacity")
    while hi - lo > tol * D:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if manning_flow(mid, D, n, S) < Q else (lo, mid)
    return 0.5 * (lo + hi)


def critical_depth(Q, D, tol=1e-13):
    lo, hi = 1e-9 * D, 0.999 * D
    f = lambda y: Q * Q * top_width(y, D) / (G * area(y, D) ** 3) - 1.0  # Froude² − 1
    while hi - lo > tol * D:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


# ── network helpers ─────────────────────────────────────────────────────────


def _load(network_path=None, network=None) -> dict:
    if network is None:
        if network_path is None:
            raise ValueError("pass network_path or network")
        network = json.loads(Path(network_path).read_text(encoding="utf-8"))
    return network


def _nodes(net: dict) -> dict[str, dict]:
    out = {}
    for kind in ("junctions", "storages", "outfalls"):
        for n in net.get(kind, []):
            out[n["id"]] = {**n, "kind": kind}
    return out


def _links(net: dict) -> list[dict]:
    return [{**c, "kind": k} for k in ("conduits", "outlets", "pumps") for c in net.get(k, [])]


def link_flows(net: dict) -> dict[str, float]:
    """Steady flow in each link of a tree network: the sum of inflows upstream."""
    links = _links(net)
    inflow = {i["node"]: float(i["Q"]) for i in net.get("inflows", [])}
    down = {}
    for l in links:
        if l["from"] in down:
            raise ValueError(f"node {l['from']} has two outgoing links; the drainage references assume a tree")
        down[l["from"]] = l
    q_node: dict[str, float] = {}

    def through(node: str) -> float:  # flow leaving `node`
        if node not in q_node:
            q_node[node] = inflow.get(node, 0.0) + sum(through(l["from"]) for l in links if l["to"] == node)
        return q_node[node]

    return {l["id"]: through(l["from"]) for l in links}


def _result(nodes: list[str], node_h, links: list[str], link_h, link_q) -> dict:
    nn, nl = len(nodes), len(links)
    return {
        "element_id": list(nodes) + list(links),
        "element_type": ["node"] * nn + ["link"] * nl,
        "h": np.concatenate([np.asarray(node_h, float), np.asarray(link_h, float)]),
        "Q": np.concatenate([np.full(nn, np.nan), np.asarray(link_q, float)]),
    }


def _slope(c: dict, nodes: dict) -> float:
    z0 = nodes[c["from"]]["invert"] + c.get("in_offset", 0.0)
    z1 = nodes[c["to"]]["invert"] + c.get("out_offset", 0.0)
    return (z0 - z1) / c["length"]


# ── generators ──────────────────────────────────────────────────────────────


def uniform_flow(x=None, t: float = 0.0, network_path=None, network=None) -> dict:
    """Normal depth in every conduit and at the nodes between equal conduits.

    Nodes are scored where their depth is defined by uniform flow: the
    junctions between two conduits of the same diameter, slope, roughness and
    flow. The inflow and outfall nodes are listed with NaN depth (their depth
    depends on how an engine treats a chain's ends).
    """
    net = _load(network_path, network)
    nodes, q = _nodes(net), link_flows(net)
    conduits = net["conduits"]
    yn = {c["id"]: normal_depth(q[c["id"]], c["D"], c["n"], _slope(c, nodes)) for c in conduits}
    node_h = []
    for nid in nodes:
        ins = [c for c in conduits if c["to"] == nid]
        outs = [c for c in conduits if c["from"] == nid]
        same = len(ins) == 1 and len(outs) == 1 and abs(yn[ins[0]["id"]] - yn[outs[0]["id"]]) < 1e-9
        node_h.append(yn[outs[0]["id"]] if same else np.nan)
    ids = [c["id"] for c in conduits]
    return _result(list(nodes), node_h, ids, [yn[i] for i in ids], [q[i] for i in ids])


def surcharged_pipe(x=None, t: float = 0.0, network_path=None, network=None) -> dict:
    """Hydraulic grade line of full circular pipes discharging to a fixed stage."""
    net = _load(network_path, network)
    nodes, q = _nodes(net), link_flows(net)
    head: dict[str, float] = {}
    for o in net["outfalls"]:
        if o.get("type") != "FIXED":
            raise ValueError("surcharged_pipe needs FIXED outfalls")
        head[o["id"]] = float(o["stage"])
    conduits = net["conduits"]
    for _ in range(len(conduits)):
        for c in conduits:
            if c["to"] in head and c["from"] not in head:
                D = c["D"]
                A, R = np.pi * D * D / 4.0, D / 4.0
                head[c["from"]] = head[c["to"]] + c["n"] ** 2 * q[c["id"]] ** 2 * c["length"] / (A * A * R ** (4.0 / 3.0))
    for nid, n in nodes.items():
        crowns = [n["invert"] + c.get("in_offset" if c["from"] == nid else "out_offset", 0.0) + c["D"]
                  for c in conduits if nid in (c["from"], c["to"])]
        if head[nid] < max(crowns):
            raise ValueError(f"node {nid}: head {head[nid]:.3f} is below a pipe crown; the pipes would not all run full")
    ids = [c["id"] for c in conduits]
    return _result(list(nodes), [head[k] - nodes[k]["invert"] for k in nodes], ids, [np.nan] * len(ids), [q[i] for i in ids])


def storage_depth(t, h0, A, C, b):
    """Depth of a prismatic storage (area A) draining through Q = C h^b, 0 ≤ b < 1."""
    rem = h0 ** (1.0 - b) - (1.0 - b) * C * np.asarray(t, float) / A
    return np.maximum(rem, 0.0) ** (1.0 / (1.0 - b))


def storage_drain(x=None, t: float = 0.0, network_path=None, network=None) -> dict:
    """Storage depth and outlet flow at time ``t`` (the scored final time)."""
    net = _load(network_path, network)
    (s,) = net["storages"]
    (o,) = net["outlets"]
    if net.get("inflows"):
        raise ValueError("storage_drain has no inflow")
    h0 = float(s["init_depth"]) - o.get("offset", 0.0)
    h = float(storage_depth(t, h0, s["area"], o["C"], o["exponent"]))
    nodes = [s["id"]] + [n["id"] for n in net["outfalls"]]
    return _result(nodes, [h + o.get("offset", 0.0)] + [np.nan] * len(net["outfalls"]), [o["id"]], [np.nan],
                   [o["C"] * h ** o["exponent"]])


def pump_head_rise(curve, Q: float) -> float:
    """Inverse of a decreasing head–flow curve [[head, flow], …] (linear between points)."""
    hd = np.array([p[0] for p in curve], float)
    qq = np.array([p[1] for p in curve], float)
    order = np.argsort(qq)
    if not (qq.min() <= Q <= qq.max()):
        raise ValueError("inflow outside the pump curve")
    return float(np.interp(Q, qq[order], hd[order]))


def pump_curve(x=None, t: float = 0.0, network_path=None, network=None) -> dict:
    """Steady wet-well depth and pump flow for a TYPE3 (head–flow) pump."""
    net = _load(network_path, network)
    nodes = _nodes(net)
    (p,) = net["pumps"]
    q = link_flows(net)[p["id"]]
    out = nodes[p["to"]]
    if out.get("type") != "FIXED":
        raise ValueError("pump_curve needs the pump to discharge to a FIXED outfall")
    h_ww = float(out["stage"]) - pump_head_rise(p["curve"], q) - nodes[p["from"]]["invert"]
    ids = list(nodes)
    return _result(ids, [h_ww if k == p["from"] else np.nan for k in ids], [p["id"]], [np.nan], [q])


def _gvf_rhs(Q, D, n, S0):
    def f(_x, y):
        A, P, T = area(y[0], D), perimeter(y[0], D), top_width(y[0], D)
        Sf = n * n * Q * Q / (A * A * (A / P) ** (4.0 / 3.0))
        Fr2 = Q * Q * T / (G * A ** 3)
        return [(S0 - Sf) / (1.0 - Fr2)]

    return f


def backwater(x=None, t: float = 0.0, network_path=None, network=None) -> dict:
    """Water-surface profile through a chain of circular pipes (subcritical, M1/M2).

    The outfall stage fixes the depth at the downstream end; the profile is
    integrated upstream pipe by pipe, with depth continuous through each
    junction (no junction losses, inverts continuous). A conduit's depth is the
    profile's depth at its midpoint.
    """
    from scipy.integrate import solve_ivp

    net = _load(network_path, network)
    nodes, q = _nodes(net), link_flows(net)
    (o,) = net["outfalls"]
    depth = {o["id"]: float(o["stage"]) - o["invert"]}
    mid: dict[str, float] = {}
    conduits = net["conduits"]
    for _ in range(len(conduits)):
        for c in conduits:
            if c["to"] in depth and c["from"] not in depth:
                y1 = depth[c["to"]] - c.get("out_offset", 0.0)
                Q, D, L = q[c["id"]], c["D"], c["length"]
                if y1 <= critical_depth(Q, D):
                    raise ValueError(f"conduit {c['id']}: downstream depth is not subcritical")
                if y1 >= 0.999 * D:
                    raise ValueError(f"conduit {c['id']}: the profile reaches the crown")
                sol = solve_ivp(_gvf_rhs(Q, D, c["n"], _slope(c, nodes)), (L, 0.0), [y1], method="DOP853",
                                rtol=1e-11, atol=1e-13, dense_output=True)
                mid[c["id"]] = float(sol.sol(L / 2.0)[0])
                depth[c["from"]] = float(sol.y[0, -1]) + c.get("in_offset", 0.0)
    ids = [c["id"] for c in conduits]
    return _result(list(nodes), [depth[k] for k in nodes], ids, [mid[i] for i in ids], [q[i] for i in ids])
