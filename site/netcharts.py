"""Charts for the drainage-network (A1D) and coupled 1D/2D (A12) tests.

Each test gets one or two charts, built when the site is built from the exact
answer and from each model's *extract* (``extract(m, folder)``: the few numbers
the charts need, cut from the model's results). Extracts are written next to
the score cards by ``scripts/export_curves.py`` in every solver workflow, filed
by the result collector under ``site/fixtures/curves/<test>/<model>.json``,
and so stay in step with the scores:

* chains of pipes (A1D-001, 002, 005): the water along the line, exact
  against each model, and each manhole's and pipe's difference from the
  exact answer, with the pass limit shaded;
* a storage tank and a pumped wet well (A1D-003, 004): depth over time,
  exact against each model;
* coupled tests (A12-*): the water balance over time (every model's stored
  plus discharged water against what came in) and the exchange flow at the
  manhole or the water discharged.

``python site/netcharts.py`` refreshes the extracts from local results under ``out/``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "runner" / "python"), str(ROOT)]

SOURCES = [("swmm524", "out/swmm_track_a/swmm524"), ("openswmm-dw", "out/swmm_track_a/openswmm-dw"),
           ("openswmm-fv", "out/swmm_track_a/openswmm-fv"), ("hydra-uds", "out/swmm_track_a/hydra-uds"),
           ("swmm-anuga", "out/coupled/swmm-anuga"), ("openswmm-2d", "out/coupled/openswmm-2d"),
           ("openswmm-2d-x", "out/coupled/openswmm-2d-x")]


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


CHAIN = ("A1D-001", "A1D-002", "A1D-005")
TIME = ("A1D-003", "A1D-004")
COUPLED = ("A12-010", "A12-011", "A12-012")
GAUGE = ("A2C-EA1", "A2C-EA2", "A2C-EA4", "A2C-EA5")
SIDS = CHAIN + TIME + COUPLED + GAUGE
MAX_POINTS = 360


def extract(m, folder: Path) -> dict | None:
    """The numbers a model's charts need, from its results in ``folder`` (None if it has none)."""
    import pandas as pd

    sid = m["test_id"].split("_")[0]
    tid = m["test_id"]
    if sid in CHAIN:
        p = folder / f"{tid}.parquet"
        if not p.is_file():
            return None
        df = pd.read_parquet(p)
        df = df[np.isclose(df["t"], df["t"].max())]
        return {"final": [[str(t), str(e), _r(h)] for t, e, h in zip(df["element_type"], df["element_id"], df["h"])]}
    if sid in TIME:
        p = folder / f"{tid}.series.json"
        if not p.is_file():
            return None
        d = json.loads(p.read_text())
        node = _net(m)["storages"][0]["id"]
        return {"t": d["t"], "h": [_r(v) for v in d["node_h"][node]]}
    if sid in GAUGE:
        p = folder / f"{tid}.parquet"
        if not p.is_file():
            return None
        from benchmark1d2d.scoring.scorer import _series_at

        df = pd.read_parquet(p)
        out = {}
        for pr in m["simulation"].get("probes") or []:
            t, h = _series_at(df, pr["x"], pr.get("y", 0.0), "h")
            if len(t) < 2:
                continue
            z = float(np.nanmean(_series_at(df, pr["x"], pr.get("y", 0.0), "z")[1])) if "z" in df.columns and df["z"].notna().any() else None
            step = max(1, int(np.ceil(len(t) / MAX_POINTS)))
            wl = [(_r(hh + z, 4) if (z is not None and hh > 1e-3) else None) for hh in h[::step]]
            out[pr["id"]] = {"t": [round(float(v), 1) for v in t[::step]], "wl": wl, "h": [_r(v, 4) for v in h[::step]]}
        return {"probes": out} if out else None
    if sid in COUPLED:
        p = folder / f"{tid}.parquet"
        if not p.is_file():
            return None
        df = pd.read_parquet(p)
        acc = df[df["element_type"] == "account"].pivot_table(index="t", columns="element_id", values="V").sort_index()
        ex = df[df["element_type"] == "exchange"].sort_values("t")
        return {"t": [float(v) for v in acc.index], **{k: [_r(v, 4) for v in acc[k]] for k in ("surface", "network", "inflow", "outflow")},
                "xt": [float(v) for v in ex["t"]], "xq": [_r(v, 5) for v in ex["Q"]]}
    return None


def chain_charts(m, data):
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
    for key, dat in data.items():
        res = {(t, e): (h, None) for t, e, h in dat["final"]}
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


def time_charts(m, data):
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
    for key, d in data.items():
        ts = [0.0] + d["t"]
        hs = [float(net["storages"][0]["init_depth"])] + d["h"]
        series[key] = {"x": [round(v / 60, 4) for v in ts], "y": [_r(v) for v in hs]}
    return [dict(id="time", title=title, note=note, xlabel="Time (minutes)", ylabel="Depth (m)",
                 exact=dict(x=[round(v / 60, 4) for v in t], y=[_r(v) for v in ey], line_only=True), series=series)]


def coupled_charts(m, data):
    sid = m["test_id"].split("_")[0]
    t_end = float(m["simulation"]["t_end"])
    spec = json.loads((Path(m["_case_dir"]) / "inputs" / "coupling.json").read_text(encoding="utf-8"))
    states = {s["id"]: s for s in m["reference"]["expected_states"]}
    bal, second = {}, {}
    scale = None
    for key, d in data.items():
        a = {k: np.asarray([np.nan if v is None else v for v in d[k]], float) for k in ("surface", "network", "inflow", "outflow")}
        stored = a["surface"] + a["network"]
        imb = stored - stored[0] - (a["inflow"] - a["inflow"][0]) + (a["outflow"] - a["outflow"][0])
        scale = max(float(a["inflow"][-1]), float(stored[0]))
        tm = [round(v / 60, 3) for v in d["t"]]
        bal[key] = {"x": tm, "y": [_r(v, 4) for v in imb]}
        if sid == "A12-010":
            second[key] = {"x": [round(v / 60, 3) for v in d["xt"]], "y": d["xq"]}
        else:
            second[key] = {"x": tm, "y": [_r(v, 3) for v in a["outflow"]]}
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


GAUGE_PICK = {"A2C-EA1": ["P1"], "A2C-EA2": ["P1", "P8"], "A2C-EA4": ["P1", "P6"], "A2C-EA5": ["P1", "P7"]}


def gauge_charts(m, data):
    sid = m["test_id"].split("_")[0]
    states = {s["id"]: s for s in m["reference"]["expected_states"]}
    probes = {p["id"]: p for p in m["simulation"].get("probes") or []}
    t_end_h = float(m["simulation"]["t_end"]) / 3600
    charts = []
    for pid in GAUGE_PICK.get(sid, []):
        series = {}
        for key, d in data.items():
            g = (d.get("probes") or {}).get(pid)
            if g:
                series[key] = {"x": [round(v / 3600, 4) for v in g["t"]], "y": g["wl"]}
        if not series:
            continue
        target = next((s for s in states.values() if s.get("variable") in ("h+z",) and pid in str(s.get("where", "")).split(",")
                       and s.get("time") is not None), None)
        exact = (dict(x=[0, t_end_h], y=[target["value"], target["value"]], line_only=True, target=True,
                      label=f"Expected final level, {target['value']:g} m") if target else None)
        pr = probes[pid]
        charts.append(dict(id=f"gauge-{pid}", title=f"Water level at gauge {pid} ({pr['x']:g} m, {pr.get('y', 0):g} m)",
                           note=("The pond must settle at the level of the sill once the boundary falls (dashed)." if target else
                                 "There is no exact water level here; the test is scored on stored volume. Levels are shown so the "
                                 "models can be compared with each other."),
                           xlabel="Time (hours)", ylabel="Water level (m)", exact=exact, series=series, free=True, snap=False, unit="m"))
    return charts


def build(m, data: dict) -> list | None:
    """Charts for test ``m`` from each model's extract (``{model key: extract}``)."""
    sid = m["test_id"].split("_")[0]
    data = {k: v for k, v in (data or {}).items() if v}
    if sid in CHAIN:
        return chain_charts(m, data)
    if sid in TIME:
        return time_charts(m, data)
    if sid in COUPLED:
        return coupled_charts(m, data)
    if sid in GAUGE:
        return gauge_charts(m, data)
    return None


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call([sys.executable, str(ROOT / "scripts" / "export_curves.py"), "--local"]))
