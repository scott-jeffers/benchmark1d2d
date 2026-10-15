"""Charts for the drainage-network (A1D) and coupled 1D/2D (A12) tests.

Each test gets one or two charts, built from the exact answer and from every
model's results under ``out/`` and saved as ``site/fixtures/profiles/<id>.charts.json``
(the models are not re-run when the site is built):

* chains of pipes (A1D-001, 002, 005): the water along the line, exact
  against each model, and each manhole's and pipe's difference from the
  exact answer, with the pass limit shaded;
* a storage tank and a pumped wet well (A1D-003, 004): depth over time,
  exact against each model;
* coupled tests (A12-*): the water balance over time (every model's stored
  plus discharged water against what came in) and the exchange flow at the
  manhole or the water discharged.

``python site/netcharts.py`` refreshes the fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "runner" / "python"), str(ROOT)]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "profiles"

SOURCES = [("swmm524", "out/swmm_track_a/swmm524"), ("openswmm-dw", "out/swmm_track_a/openswmm-dw"),
           ("openswmm-fv", "out/swmm_track_a/openswmm-fv"), ("hydra-uds", "out/swmm_track_a/hydra-uds"),
           ("swmm-anuga", "out/coupled/swmm-anuga")]


def _r(v, n=6):
    return None if v is None or not np.isfinite(v) else round(float(v), n)


def _net(m):
    return json.loads((Path(m["_case_dir"]) / "inputs" / "network.json").read_text(encoding="utf-8"))


def _chains(net):
    """Positions along each chain: node -> (chain index, distance), link -> (chain index, midpoint distance)."""
    conduits = net["conduits"]
    to = {c["to"] for c in conduits}
    heads = [c["from"] for c in conduits if c["from"] not in to]
    nodes, links = {}, {}
    for k, head in enumerate(dict.fromkeys(heads)):
        d, n = 0.0, head
        nodes[n] = (k, d)
        while True:
            nxt = next((c for c in conduits if c["from"] == n), None)
            if nxt is None:
                break
            links[nxt["id"]] = (k, d + nxt["length"] / 2)
            d += nxt["length"]
            n = nxt["to"]
            nodes[n] = (k, d)
    return nodes, links


def _limit(m, var="h"):
    for c in m["scoring"]["criteria"]:
        if c.get("gating") and c.get("variable") == var and c["threshold"].get("units") == "m":
            return float(c["threshold"]["value"])
    return None


def _results(path):
    import pandas as pd

    df = pd.read_parquet(path)
    df = df[np.isclose(df["t"], df["t"].max())]
    return {(str(t), str(e)): (h, q) for t, e, h, q in zip(df["element_type"], df["element_id"], df["h"], df["Q"])}


def _models(test_id, suffix=".parquet"):
    out = {}
    for key, d in SOURCES:
        p = ROOT / d / f"{test_id}{suffix}"
        if p.is_file():
            out[key] = p
    return out


def chain_charts(m):
    from references import drainage

    fn = getattr(drainage, m["reference"]["generator"]["function"])
    net = _net(m)
    ref = fn(network_path=str(Path(m["_case_dir"]) / "inputs" / "network.json"), t=float(m["simulation"]["t_end"]))
    exact = {(t, e): (h, q) for t, e, h, q in zip(ref["element_type"], ref["element_id"], ref["h"], ref["Q"])}
    nodes, links = _chains(net)
    inv = {n["id"]: n["invert"] for k in ("junctions", "outfalls", "storages") for n in net.get(k, [])}
    level = m["test_id"].startswith(("A1D-002", "A1D-005"))  # show water level (head); A1D-001 shows depth
    sid = m["test_id"].split("_")[0]
    # several independent lines of pipes are laid end to end, with a gap, so their points do not overlap
    n_chain = 1 + max(k for k, _ in nodes.values())
    span = max(d for _, d in nodes.values())
    gap = span * 0.15
    off = lambda k: k * (span + gap)  # noqa: E731
    nodes = {e: (k, off(k) + d) for e, (k, d) in nodes.items()}
    links = {e: (k, off(k) + d) for e, (k, d) in links.items()}
    labels = ([{"x": off(k) + span / 2, "text": f"Line {chr(65 + k)}"} for k in range(n_chain)] if n_chain > 1 else None)

    def at(kind, eid, h):
        if h is None or not np.isfinite(h):
            return None
        if not level:
            return h
        if kind == "node":
            return inv[eid] + h
        c = next(c for c in net["conduits"] if c["id"] == eid)
        return 0.5 * (inv[c["from"]] + inv[c["to"]]) + h

    # exact line through the nodes (and pipe midpoints) of each chain, broken between chains
    pts = sorted([(nodes[e][0], nodes[e][1], "node", e) for (t, e) in exact if t == "node" and e in nodes]
                 + [(links[e][0], links[e][1], "link", e) for (t, e) in exact if t == "link" and e in links])
    ex, ey, floor = [], [], []
    prev = None
    for k, d, kind, e in pts:
        v = at(kind, e, exact[(kind, e)][0])
        if v is None:
            continue
        if prev is not None and k != prev:
            ex.append(d)
            ey.append(None)
            floor.append(None)
        ex.append(d)
        ey.append(_r(v))
        floor.append(_r(inv[e]) if kind == "node" else None)
        prev = k
    series, diff = {}, {}
    for key, p in _models(m["test_id"]).items():
        res = _results(p)
        sx, sy, dx, dy = [], [], [], []
        prev_k = None
        for k, d, kind, e in pts:
            if prev_k is not None and k != prev_k:  # break the line between independent chains
                sx.append(d); sy.append(None); dx.append(d); dy.append(None)  # noqa: E702
            prev_k = k
            got = res.get((kind, e))
            if got is None:
                continue
            v, x = at(kind, e, got[0]), at(kind, e, exact[(kind, e)][0])
            if v is None or x is None:  # only where the exact answer defines a value (no full-pipe "depths")
                continue
            sx.append(d)
            sy.append(_r(v))
            if x is not None:
                dx.append(d)
                dy.append(_r((v - x) * 1000, 3))
        series[key] = {"x": sx, "y": sy, "dots": True}
        diff[key] = {"x": dx, "y": dy, "dots": True}
    lim = _limit(m)
    xmax = max(ex) if ex else 1
    ylab = "Water level (m)" if level else "Depth (m)"
    title = {"A1D-001": "Depth along each line of pipes", "A1D-002": "Water level in the manholes (hydraulic grade line)",
             "A1D-005": "Water level along the sewer"}.get(sid, "Along the pipes")
    note = {"A1D-001": "Three separate lines of pipes, each carrying a different flow; the exact depth is the same in every pipe of a line.",
            "A1D-002": "Every pipe runs full: the water level falls by the same friction loss along each pipe.",
            "A1D-005": "The outfall holds the water high; it backs up through the manholes towards normal depth upstream."}.get(sid, "")
    xlab = "Distance along each line of pipes (m), lines laid end to end" if labels else "Distance along the pipes (m)"
    charts = [dict(id="profile", title=title, note=note, xlabel=xlab, ylabel=ylab, labels=labels,
                   exact=dict(x=ex, y=ey, line_only=True, floor=floor if level and sid == "A1D-005" else None, points=True),
                   series=series, snap=True, unit="m")]
    charts.append(dict(id="diff", title="Difference from the exact answer at every manhole and pipe",
                       note=(f"Shaded: the pass limit, ±{lim * 1000:g} mm." if lim else ""),
                       xlabel=xlab, ylabel="Model − exact (mm)", labels=labels,
                       exact=dict(x=[0, xmax], y=[0, 0], line_only=True, label="Exact (no difference)"),
                       band=[-lim * 1000, lim * 1000] if lim else None, series=diff, symmetric=True, rescale=True, snap=True,
                   unit="mm"))
    return charts


def time_charts(m):
    from references import drainage

    sid = m["test_id"].split("_")[0]
    net_path = str(Path(m["_case_dir"]) / "inputs" / "network.json")
    net = _net(m)
    t_end = float(m["simulation"]["t_end"])
    t = np.linspace(0, t_end, 241)
    if sid == "A1D-003":
        (s,) = net["storages"]
        (o,) = net["outlets"]
        ey = drainage.storage_depth(t, s["init_depth"], s["area"], o["C"], o["exponent"])
        node, title = s["id"], "Depth in the tank as it drains"
        note = "The exact depth follows h(t) = (√h₀ − C t / 2A)²; every engine steps through it."
    else:
        ey = drainage.pump_wet_well_depth(t, network_path=net_path)
        node, title = net["storages"][0]["id"], "Depth in the wet well as the pump settles"
        note = "The pump starts from 1 m and settles where it passes exactly the inflow (1.143 m)."
    series = {}
    for key, p in _models(m["test_id"], ".series.json").items():
        d = json.loads(p.read_text())
        ts = [0.0] + d["t"]
        hs = [float(net["storages"][0]["init_depth"])] + d["node_h"][node]
        series[key] = {"x": [round(v / 60, 4) for v in ts], "y": [_r(v) for v in hs]}
    return [dict(id="time", title=title, note=note, xlabel="Time (minutes)", ylabel="Depth (m)",
                 exact=dict(x=[round(v / 60, 4) for v in t], y=[_r(v) for v in ey], line_only=True), series=series)]


def coupled_charts(m):
    import pandas as pd

    sid = m["test_id"].split("_")[0]
    t_end = float(m["simulation"]["t_end"])
    spec = json.loads((Path(m["_case_dir"]) / "inputs" / "coupling.json").read_text(encoding="utf-8"))
    states = {s["id"]: s for s in m["reference"]["expected_states"]}
    bal, second = {}, {}
    scale = None
    for key, p in _models(m["test_id"]).items():
        df = pd.read_parquet(p)
        acc = df[df["element_type"] == "account"].pivot_table(index="t", columns="element_id", values="V").sort_index()
        stored = acc["surface"] + acc["network"]
        imb = stored - stored.iloc[0] - (acc["inflow"] - acc["inflow"].iloc[0]) + (acc["outflow"] - acc["outflow"].iloc[0])
        scale = max(float(acc["inflow"].iloc[-1]), float(stored.iloc[0]))
        tm = [round(v / 60, 3) for v in acc.index]
        bal[key] = {"x": tm, "y": [_r(v, 4) for v in imb]}
        if sid == "A12-010":
            ex = df[df["element_type"] == "exchange"].sort_values("t")
            second[key] = {"x": [round(v / 60, 3) for v in ex["t"]], "y": [_r(v, 5) for v in ex["Q"]]}
        else:
            second[key] = {"x": tm, "y": [_r(v, 3) for v in acc["outflow"]]}
    tmax = t_end / 60
    lim = 0.005 * scale if scale else None
    charts = [dict(id="balance", title="Water balance over time",
                   note=("Water stored on the surface and in the pipes, minus what came in, plus what went out: zero for a model "
                         f"that neither makes nor loses water. Shaded: the pass limit at the end of the run, ±{lim:.2g} m³ (0.5 %)."
                         if lim else ""),
                   xlabel="Time (minutes)", ylabel="Water made (+) or lost (−), m³",
                   exact=dict(x=[0, tmax], y=[0, 0], line_only=True, label="Exact (no water made or lost)"),
                   band=[-lim, lim] if lim else None, series=bal, symmetric=True, unit="m³")]
    if sid == "A12-010":
        q = states["steady_exchange"]["value"]
        charts.append(dict(id="exchange", title="Flow out of the manhole onto the street",
                           note=f"At steady state the manhole must release the whole pipe inflow, {q:g} m³/s.",
                           xlabel="Time (minutes)", ylabel="Exchange flow (m³/s)",
                           exact=dict(x=[0, tmax], y=[q, q], line_only=True, label="Exact steady flow"), series=second))
    else:
        v = states["discharged_volume"]["value"]
        charts.append(dict(id="discharged", title="Water discharged at the outfall",
                           note=f"By the end, exactly {v:g} m³ must have left through the pipe.",
                           xlabel="Time (minutes)", ylabel="Discharged volume (m³)",
                           exact=dict(x=[0, tmax], y=[v, v], line_only=True, label="Exact final volume", target=True), series=second))
    return charts


def build(m):
    sid = m["test_id"].split("_")[0]
    if sid in ("A1D-001", "A1D-002", "A1D-005"):
        return chain_charts(m)
    if sid in ("A1D-003", "A1D-004"):
        return time_charts(m)
    if sid in ("A12-010", "A12-011", "A12-012"):
        return coupled_charts(m)
    return None


def refresh_fixtures() -> None:
    sys.path.insert(0, str(ROOT / "site"))
    from build import load_manifests  # type: ignore

    FIXTURES.mkdir(parents=True, exist_ok=True)
    for m in load_manifests():
        charts = build(m)
        if not charts:
            continue
        sid = m["test_id"].split("_")[0]
        (FIXTURES / f"{sid}.charts.json").write_text(json.dumps(charts, separators=(",", ":")) + "\n", encoding="utf-8")
        print(sid, [c["id"] for c in charts], sorted(charts[0]["series"]))


if __name__ == "__main__":
    refresh_fixtures()
