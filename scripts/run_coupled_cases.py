#!/usr/bin/env python3
"""Score a coupled sewer/surface model on the exact 1D/2D coupling cases (A12-01x).

The candidate is EPA SWMM 5.2.4 (``swmm-toolkit`` 0.17.0, its stepping API)
coupled to ANUGA 4.0.1 by a small explicit coupler in this script, the way
most research and several commercial couplings work:

* every second SWMM takes one fixed 1 s routing step and ANUGA evolves 1 s;
* the exchange at each manhole follows the surface level ``η`` (mean over the
  cells within 0.75 m) and the manhole head ``H``, with ``η′ = max(η, crest)``
  (Chen et al. 2007; Rubinato et al. 2017):

  - **surface → network** when ``η > crest`` and ``η > H``: the smaller of a
    weir rate ``c_w P √(2g) (η − crest)^1.5`` and an orifice rate
    ``c_o A √(2g (η − max(H, crest)))``;
  - **network → surface** when ``H > η′``: an orifice rate
    ``c_o A √(2g (H − η′))``;

  each limited to the volume that would level the two water surfaces in one
  step (the manhole's surcharged plan area is SWMM's 1.167 m² minimum), so
  the explicit exchange cannot overshoot;
* the manholes are given a deep surcharge allowance so SWMM never floods; the
  exchange is the only way water leaves or enters them, as SWMM lateral
  inflow (negative when going up), and it is moved on the surface at once;
* SWMM surcharges with its Preissmann slot (``SURCHARGE_METHOD SLOT``): with
  the default EXTRAN iteration a manhole's head jumps by tens of metres in a
  step when a full pipe is fed laterally, and the explicit exchange goes
  unstable.

The coupling itself neither makes nor loses water; what remains is each
engine's own continuity. The surface is
ANUGA with its defaults on a ``rectangular_cross`` mesh.

Results carry, besides the surface at the case's probes, the exchange flow at
each manhole (``element_type`` ``exchange``) and the volume accounts
(``account``: surface, network, inflow, outflow) the coupled cases score.

Run in a Python with ANUGA and swmm-toolkit::

    python scripts/run_coupled_cases.py [A12-010 ...]

Score cards go to ``out/coupled/swmm-anuga/``.
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

OUT = REPO / "out" / "coupled" / "swmm-anuga"
TS = "2024-01-01T00:00:00Z"
G = 9.81
CASES = ["A12-010", "A12-011", "A12-012"]
import os  # noqa: E402

VERBOSE = bool(os.environ.get("COUPLER_VERBOSE"))
T_END = os.environ.get("COUPLER_T_END")  # shorten a run while debugging
# SWMM's Preissmann-slot surcharge: with its default EXTRAN iteration the head of a
# manhole fed laterally into a full pipe jumps by tens of metres in one step, and an
# explicit exchange driven by that head goes unstable.
SURCHARGE = "SLOT"
SWMM_NODE_AREA = 12.566 * 0.3048**2  # SWMM's default MIN_SURFAREA, the plan area of a surcharged manhole


# ── surface ─────────────────────────────────────────────────────────────────


def bed_function(bed: dict):
    kind = bed["type"]
    if kind == "flat":
        return lambda x, y: np.full_like(np.asarray(x, float), bed["z"])
    if kind == "plane":
        return lambda x, y: bed["z0"] - bed["slope_x"] * np.asarray(x, float)
    if kind == "cone":
        ax, ay = bed["apex"]
        return lambda x, y: bed["z_apex"] + bed["slope"] * np.hypot(np.asarray(x, float) - ax, np.asarray(y, float) - ay)
    raise ValueError(kind)


def build_surface(spec: dict):
    import anuga

    s = spec["surface"]
    dx = s["cell_size"]
    lx, ly = s["x1"] - s["x0"], s["y1"] - s["y0"]
    d = anuga.rectangular_cross_domain(int(round(lx / dx)), int(round(ly / dx)), len1=lx, len2=ly, origin=(s["x0"], s["y0"]))
    d.set_store(False)
    d.set_name("surface")
    z = bed_function(s["bed"])
    d.set_quantity("elevation", z, location="centroids")
    d.set_quantity("friction", s["manning_n"], location="centroids")
    if "initial_level" in s:
        d.set_quantity("stage", lambda x, y: np.maximum(z(x, y), s["initial_level"]), location="centroids")
    else:
        d.set_quantity("stage", z, location="centroids")
    tags = {}
    for side, kind in s["boundaries"].items():
        if kind == "wall":
            tags[side] = anuga.Reflective_boundary(d)
        elif kind == "normal_depth":
            # outflow held at the exact normal depth of the steady sheet flow
            n_, q, S = s["manning_n"], spec["normal_depth_q"], s["bed"]["slope_x"]
            hn = (n_ * q / math.sqrt(S)) ** 0.6
            zb = float(z(np.array([s["x1"]]), np.array([0.0]))[0])
            tags[side] = anuga.Dirichlet_boundary([zb + hn, q, 0.0])
        else:
            raise ValueError(kind)
    d.set_boundary(tags)
    return d


class Manhole:
    """Surface cells within ``radius`` of a manhole, and the exchange there."""

    def __init__(self, domain, mh: dict, radius: float):
        cen = domain.centroid_coordinates + np.array([domain.geo_reference.xllcorner, domain.geo_reference.yllcorner])
        r = np.hypot(cen[:, 0] - mh["x"], cen[:, 1] - mh["y"])
        self.idx = np.flatnonzero(r <= radius)
        if self.idx.size == 0:
            self.idx = np.array([int(np.argmin(r))])
        self.area = domain.areas[self.idx]
        self.d = domain
        self.mh = mh

    def level(self) -> float:
        st = self.d.quantities["stage"].centroid_values[self.idx]
        return float(np.sum(st * self.area) / np.sum(self.area))

    def _set_stage(self, st):
        self.d.quantities["stage"].centroid_values[self.idx] = st

    def add(self, vol: float) -> None:
        st = self.d.quantities["stage"].centroid_values[self.idx]
        self._set_stage(st + vol / np.sum(self.area))

    def removable(self) -> np.ndarray:
        q = self.d.quantities
        st, z = q["stage"].centroid_values[self.idx], q["elevation"].centroid_values[self.idx]
        return np.maximum(st - np.maximum(z, self.mh["crest"]), 0.0) * self.area

    def take(self, vol: float) -> float:
        avail = self.removable()
        tot = float(avail.sum())
        vol = min(vol, 0.999 * tot)
        if vol <= 0.0:
            return 0.0
        st = self.d.quantities["stage"].centroid_values[self.idx]
        self._set_stage(st - vol * (avail / tot) / self.area)
        # keep momentum consistent with the smaller depth
        return vol

    def exchange_rate(self, head: float, dt: float) -> float:
        """Exchange for surface level η and manhole head ``head``: > 0 from the network onto the surface."""
        mh, eta = self.mh, self.level()
        level_with = 1.0 / (1.0 / SWMM_NODE_AREA + 1.0 / float(np.sum(self.area)))  # m³ per m of head difference
        crest = mh["crest"]
        if eta > crest and eta > head:  # surface → network
            dh = eta - max(head, crest)
            weir = mh["cw"] * mh["perimeter"] * math.sqrt(2 * G) * (eta - crest) ** 1.5
            orifice = mh["co"] * mh["area"] * math.sqrt(2 * G * dh)
            return -min(weir, orifice, level_with * dh / dt)
        top = max(eta, crest)
        if head > top:  # network → surface
            dh = head - top
            return min(mh["co"] * mh["area"] * math.sqrt(2 * G * dh), level_with * dh / dt)
        return 0.0


# ── network (SWMM 5.2.4, stepped) ───────────────────────────────────────────


class Network:
    def __init__(self, net: dict, td: Path, manholes: list[str]):
        from run_drainage_cases import write_inp
        from swmm.toolkit import shared_enum as se, solver

        self.se, self.s = se, solver
        net = json.loads(json.dumps(net))
        for j in net.get("junctions", []):
            if j["id"] in manholes:
                j["surcharge_depth"] = 1000.0  # the coupler, not SWMM, moves water out of a full manhole
        inp = td / "net.inp"
        write_inp(net, inp, "DYNWAVE", variable_step=0.0, extra_options=(f"SURCHARGE_METHOD {SURCHARGE}",))
        solver.swmm_open(str(inp), str(td / "net.rpt"), str(td / "net.out"))
        solver.swmm_start(0)
        self.nodes = [solver.project_get_id(se.ObjectType.NODE, i) for i in range(solver.project_get_count(se.ObjectType.NODE))]
        self.links = [solver.project_get_id(se.ObjectType.LINK, i) for i in range(solver.project_get_count(se.ObjectType.LINK))]
        self.ix = {n: i for i, n in enumerate(self.nodes)}
        self.outfalls = [self.ix[o["id"]] for o in net.get("outfalls", [])]
        self.sources = [self.ix[i["node"]] for i in net.get("inflows", [])]
        self.t = 0.0
        self.inflow = 0.0
        self.outflow = 0.0

    def head(self, node: str) -> float:
        return float(self.s.node_get_result(self.ix[node], self.se.NodeResult.HEAD))

    def flood(self, node: str) -> float:
        return float(self.s.node_get_result(self.ix[node], self.se.NodeResult.FLOOD))

    def set_inflow(self, node: str, q: float) -> None:
        self.s.node_set_total_inflow(self.ix[node], q)

    def step(self) -> bool:
        """One 1 s routing step; accumulates system inflow and outfall discharge."""
        elapsed = self.s.swmm_step()
        if elapsed == 0:
            return False
        t_new = elapsed * 86400.0
        dt = t_new - self.t
        self.t = t_new
        nr = self.se.NodeResult
        self.inflow += dt * sum(float(self.s.node_get_result(i, nr.LATERAL_INFLOW)) for i in self.sources)
        self.outflow += dt * sum(float(self.s.node_get_result(i, nr.TOTAL_INFLOW)) for i in self.outfalls)
        return True

    def volume(self) -> float:
        nv = sum(float(self.s.node_get_result(i, self.se.NodeResult.VOLUME)) for i in range(len(self.nodes)))
        lv = sum(float(self.s.link_get_result(i, self.se.LinkResult.VOLUME)) for i in range(len(self.links)))
        return nv + lv

    def close(self) -> str:
        rt = self.s.system_get_routing_totals()
        err = float(getattr(rt, "pctError", float("nan")))
        self.s.swmm_end()
        self.s.swmm_close()
        return err


# ── a run ───────────────────────────────────────────────────────────────────


def run_case(m: dict) -> tuple[dict, dict]:
    spec = json.loads((Path(m["_case_dir"]) / "inputs" / "coupling.json").read_text(encoding="utf-8"))
    dom = build_surface(spec)
    t_end, t_out = float(T_END or spec["duration_s"]), float(spec["output_interval_s"])
    manholes = [Manhole(dom, mh, spec["surface"].get("manhole_radius", 0.75)) for mh in spec["manholes"]]
    probes = m["simulation"].get("probes") or []
    pidx = []
    cen = dom.centroid_coordinates + np.array([dom.geo_reference.xllcorner, dom.geo_reference.yllcorner])
    for p in probes:
        pidx.append(np.argsort(np.hypot(cen[:, 0] - p["x"], cen[:, 1] - p["y"]))[:4])
    rows: dict[str, list] = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "Q", "z", "V", "element_id", "element_type")}

    def emit(t, x=np.nan, y=np.nan, h=np.nan, Q=np.nan, z=np.nan, V=np.nan, eid="", etype="cell", u=np.nan, v=np.nan):
        for k, val in (("t", t), ("x", x), ("y", y), ("h", h), ("u", u), ("v", v), ("p", np.nan), ("Q", Q), ("z", z), ("V", V),
                       ("element_id", eid), ("element_type", etype)):
            rows[k].append(val)

    exch = {mh.mh["id"]: 0.0 for mh in manholes}
    boundary_out = [0.0]

    def record(t, net):
        q = dom.quantities
        for p, ix in zip(probes, pidx):
            st, el = q["stage"].centroid_values[ix], q["elevation"].centroid_values[ix]
            h = float(np.maximum(st - el, 0.0).mean())
            hu, hv = float(q["xmomentum"].centroid_values[ix].mean()), float(q["ymomentum"].centroid_values[ix].mean())
            emit(t, p["x"], p["y"], h, z=float(el.mean()), u=hu / h if h > 1e-6 else 0.0, v=hv / h if h > 1e-6 else 0.0, eid=p["id"], etype="cell")
        for k, qx in exch.items():
            emit(t, Q=qx, eid=k, etype="exchange")
        emit(t, V=float(dom.get_water_volume()), eid="surface", etype="account")
        emit(t, V=net.volume(), eid="network", etype="account")
        emit(t, V=net.inflow, eid="inflow", etype="account")
        emit(t, V=net.outflow + boundary_out[0], eid="outflow", etype="account")

    with tempfile.TemporaryDirectory() as tdn:
        net = Network(spec["network"], Path(tdn), [mh.mh["id"] for mh in manholes])
        from benchmark1d2d import keep

        keep.inputs("swmm-anuga", m["test_id"], Path(tdn), files=["net.inp"])
        record(0.0, net)
        next_out = t_out
        for t in dom.evolve(yieldstep=1.0, finaltime=t_end):
            if t <= 0.0:
                continue
            # the surface's own outflow over open boundaries (the street case)
            boundary_out[0] = -float(dom.get_boundary_flux_integral()) if spec["surface"].get("open_boundary") else 0.0
            for mh in manholes:
                k = mh.mh["id"]
                q = mh.exchange_rate(net.head(k), 1.0)
                if q > 0.0:
                    mh.add(q * 1.0)
                elif q < 0.0:
                    q = -mh.take(-q * 1.0)
                exch[k] = q
                net.set_inflow(k, -q)  # SWMM lateral inflow over this step
            if not net.step():
                break
            if t + 1e-9 >= next_out:
                record(t, net)
                next_out += t_out
            if VERBOSE and (int(t) % 300 == 0 or t <= 30):
                print(f"  t={t:g} eta={manholes[0].level():.4f} H={net.head(manholes[0].mh['id']):.4f} q={exch[manholes[0].mh['id']]:+.4f} "
                      f"surface={dom.get_water_volume():.2f} network={net.volume():.2f} out={net.outflow:.2f} dt={dom.timestep:.3g}", file=sys.stderr, flush=True)
        totals = net.close()
    cols = {k: (np.asarray(v, dtype=float) if k not in ("element_id", "element_type") else v) for k, v in rows.items()}
    return cols, {"swmm_continuity_pct": totals}


def main() -> int:
    import argparse

    import anuga
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from swmm.toolkit import solver

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=CASES)
    args = ap.parse_args()
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    ver = f"SWMM {solver.swmm_version_info()} + ANUGA {anuga.__version__}"
    sol = {"name": f"SWMM–ANUGA coupled ({ver})", "version": ver,
           "adapter": "suite coupler: explicit 1 s weir/orifice exchange (Chen et al. 2007), levelling-limited"}
    OUT.mkdir(parents=True, exist_ok=True)
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        t0 = time.perf_counter()
        cols, info = run_case(m)
        res = write_results_parquet(OUT / f"{m['test_id']}.parquet", cols)
        card = score_case(m, res, timestamp=TS, private_key=key, solver=sol)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({time.perf_counter() - t0:.0f} s; SWMM's own routing continuity {info['swmm_continuity_pct']:.3f} %)")
        for c in card["criteria_results"]:
            print(f"    [{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['observed']} {c['threshold']['units']} — {c.get('detail', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
