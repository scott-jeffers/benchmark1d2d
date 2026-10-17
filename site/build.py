#!/usr/bin/env python3
"""Static site generator for benchmark1d2d (GitHub Pages).

Builds ``site/dist/`` from the catalog, score cards, Track B corpus census,
engine pins and docs. Every chart is inline SVG (``site/charts.py``); terrain
maps are PNGs drawn with matplotlib when the case's terrain has been fetched.

Usage::

    python site/build.py
    python site/build.py --scorecards out/vertical_slice --scorecards out/demo_2d
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "runner" / "python"), str(ROOT), str(SITE)]

from charts import Axis, Chart, Series, esc, fmt, hbars, legend  # noqa: E402
from benchmark1d2d.scoring import method_v2  # noqa: E402

DIST = SITE / "dist"
REPO_URL = "https://github.com/scott-jeffers/benchmark1d2d"
BLOB = REPO_URL + "/blob/master/"
TREE = REPO_URL + "/tree/master/"

COMPONENTS = [
    ("A1P", "1D pressurized", "Pipe networks, water hammer and transport, checked against exact solutions."),
    ("A1D", "1D drainage networks", "Sewer pipes part full and surcharged, storage, pumps and backwater, against exact answers."),
    ("A1F", "1D free surface", "Saint-Venant channels and real drainage networks: dam breaks, backwater, jumps."),
    ("A2A", "2D analytical", "Shallow-water problems with exact solutions, including moving shorelines."),
    ("A2C", "2D code inter-comparison", "Environment Agency tests with no exact answer, scored on conservation and settled states."),
    ("A2L", "2D laboratory", "Flume experiments with gauge measurements."),
    ("A2F", "2D field", "Historical floods with surveyed high-water marks."),
    ("A12", "Coupled 1D/2D", "Sewer–surface exchange through manholes."),
    ("B", "Track B parity", "Element-by-element comparison with pinned EPA SWMM 5.2.4 and EPANET 2.2."),
]
CLASS_NAMES = {
    "verification_analytic": "Verification — exact solution",
    "verification_manufactured": "Verification — manufactured solution",
    "intercomparison": "Code inter-comparison",
    "validation_lab": "Validation — laboratory",
    "validation_field": "Validation — field",
    "validation_coupled": "Validation — coupled",
    "parity": "Parity",
    "regression": "Regression",
    "stress": "Stress",
}
STATUS_ORDER = ["frozen", "candidate", "draft", "deprecated"]
STATUS_TEXT = {
    "frozen": "Frozen: counts toward certification",
    "candidate": "Candidate: complete and under review",
    "draft": "Draft: inputs or reference still missing",
    "deprecated": "Deprecated",
}


# ── data ────────────────────────────────────────────────────────────────────


def component_of(test_id: str) -> str:
    return "B" if test_id.startswith("B-") else test_id.split("-", 1)[0]


def load_manifests() -> list[dict[str, Any]]:
    out = []
    for p in sorted((ROOT / "test_catalog").rglob("manifest.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        m["_case_dir"] = p.parent
        m["_rel"] = p.parent.relative_to(ROOT).as_posix()
        m["_component"] = component_of(m["test_id"])
        out.append(m)
    order = {c[0]: i for i, c in enumerate(COMPONENTS)}
    out.sort(key=lambda m: (order.get(m["_component"], 99), m["test_id"]))
    return out


def card_verdict(c: dict) -> str:
    """pass, fail or inconclusive (scoring method 2)."""
    return c.get("verdict") or ("pass" if c.get("passed") else "fail")


def load_scorecards(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.scorecard.json")):
            try:
                c = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            c["_path"] = p
            method_v2.apply(c)
            cards[c["test_id"]] = c
    return cards


def short_id(test_id: str) -> str:
    parts = test_id.split("_", 1)
    return parts[0]


def page_name(test_id: str) -> str:
    return f"tests/{short_id(test_id)}.html"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def size_text(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return str(n)


# ── layout ──────────────────────────────────────────────────────────────────

def layout(title: str, body: str, active: str, depth: int = 0, description: str = "") -> str:
    """Every page uses the site chrome from pages.py (nav, footer, fonts)."""
    import pages

    return pages.layout(title, f'<div class="wrap legacy">{body}</div>', active, depth=depth, description=description, math=True)


def chip(status: str) -> str:
    return f'<span class="chip st-{esc(status)}" title="{esc(STATUS_TEXT.get(status, status))}">{esc(status)}</span>'


def verdict(card: dict | None) -> str:
    if card is None:
        return '<span class="verdict v-none">Not scored</span>'
    v = card.get("verdict") or ("pass" if card.get("passed") else "fail")
    return {"pass": '<span class="verdict v-pass">Pass</span>', "fail": '<span class="verdict v-fail">Fail</span>',
            "inconclusive": '<span class="verdict v-unsure">Inconclusive</span>'}[v]


def md(text: str, drop_h1: bool = True) -> str:
    """Markdown to HTML with LaTeX kept intact for KaTeX.

    Python-Markdown treats ``\\(`` as an escaped parenthesis and drops the
    backslash, so math spans are swapped for placeholders first.
    """
    import re

    import markdown

    keep: list[str] = []

    def stash(mt: "re.Match[str]") -> str:
        keep.append(mt.group(0))
        return f"\u0000M{len(keep) - 1}\u0000"

    protected = re.sub(r"\$\$.+?\$\$|\\\[.+?\\\]|\\\(.+?\\\)", stash, text, flags=re.S)
    html_text = markdown.markdown(protected, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    html_text = re.sub("\u0000M(\\d+)\u0000", lambda mt: esc(keep[int(mt.group(1))]), html_text)
    if drop_h1 and html_text.startswith("<h1"):
        html_text = html_text.split("</h1>", 1)[1]
    return html_text


# ── figures ─────────────────────────────────────────────────────────────────


def _results_for(test_id: str, result_dirs: list[Path]) -> Path | None:
    """The run a case's score card was made from: the named file, else the finest grid level."""
    sid = short_id(test_id)
    for d in result_dirs:
        for cand in (d / f"{test_id}.parquet", d / f"{sid}.parquet", *sorted(d.glob(f"{test_id}.*.parquet"))):
            if cand.is_file():
                return cand
        levels = sorted(d.glob(f"{sid}_*dx*.parquet"), key=lambda p: float(p.stem.rsplit("dx", 1)[1]))
        if levels:
            return levels[0]
    return None


def _demo_profile(test_id: str, result_dirs: list[Path]) -> pd.DataFrame | None:
    p = _results_for(test_id, result_dirs)
    if p is None:
        return None
    df = pd.read_parquet(p)
    return df[np.isclose(df["t"], df["t"].max())].sort_values("x")


def fig_analytic_1d(m: dict, result_dirs: list[Path]) -> str:
    import importlib

    gen = m["reference"]["generator"]
    mod = importlib.import_module(gen["module"])
    fn = getattr(mod, gen["function"])
    prm = dict(gen.get("parameters") or {})
    t_end = float(m["simulation"]["t_end"])
    tid = m["test_id"]
    demo = _demo_profile(tid, result_dirs)
    if tid.startswith("A1F-010") or tid.startswith("A1F-011"):
        lo, hi = (0.0, 2000.0) if tid.startswith("A1F-010") else (-1000.0, 1000.0)
        x = np.linspace(lo, hi, 1601)
        series = []
        times = np.linspace(0, t_end, 5)
        for k, t in enumerate(times):
            r = fn(x, float(t), **prm)
            series.append(Series(x, r["h"], f"Exact, t = {t:g} s", css=f"s-time s-t{k}", width=1.6 if t < t_end else 2.4))
        if demo is not None:
            step = max(1, len(demo) // 120)
            series.append(Series(demo["x"].to_numpy()[::step], demo["h"].to_numpy()[::step], f"Demo solver, t = {t_end:g} s", css="s-solver", kind="dots"))
        return Chart(f"Water depth along the channel — {m['title']}", Axis("Distance x (m)"), Axis("Depth h (m)", lo=0), series,
                     note="Exact solution at five instants; dots are the demo solver on its finest grid at the final time.").render()
    if tid.startswith("A1F-001"):
        from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

        x = np.linspace(0, M1_PARAMS["L"], 801)
        zb = bed_elevation(x)
        h = depth_profile(x)
        series = [Series(x, zb + h, "Exact water surface", css="s-water", width=2.4)]
        if demo is not None:
            zbd = bed_elevation(np.sort(demo["x"].to_numpy()))
            series.append(Series(demo["x"], zbd + demo["h"].to_numpy(), "Demo solver (Heun GVF)", css="s-solver", kind="dots"))
        return Chart("Steady water surface over the manufactured bed", Axis("Distance x (m)"), Axis("Elevation (m)"), series,
                     floor=[(x, zb)], note="Ochre: MacDonald bed built so that the profile is exact.").render()
    if tid.startswith("A1P-020"):
        x = np.linspace(0, prm["L"], 801)
        series = [Series(x, fn(x, t, **prm)["p"] / 1e3, f"Exact, t = {t:g} s", css=f"s-time s-t{k}") for k, t in enumerate([0.1, 0.25, 0.4, 0.5])]
        if demo is not None:
            step = max(1, len(demo) // 120)
            series.append(Series(demo["x"].to_numpy()[::step], demo["p"].to_numpy()[::step] / 1e3, "Demo solver (MOC), t = 0.5 s", css="s-solver", kind="dots"))
        return Chart("Pressure wave travelling upstream from the closed valve", Axis("Distance from reservoir x (m)"), Axis("Pressure rise (kPa)"), series,
                     note="Joukowsky rise ρaV₀ = 1 MPa behind a sharp front; the fixed-grid solver smears the front.").render()
    if tid.startswith("A1P-030"):
        x = np.linspace(0, 1000, 1601)
        series = [Series(x, fn(x, t, **prm)["c"], f"Exact, t = {t / 3600:g} h", css=f"s-time s-t{k}") for k, t in enumerate([900, 1800, 2700, 3600])]
        if demo is not None:
            near = demo[(demo["x"] > 250) & (demo["x"] < 480)]
            step = max(1, len(near) // 60)
            series.append(Series(near["x"].to_numpy()[::step], near["c"].to_numpy()[::step], "Demo solver, t = 1 h", css="s-solver", kind="dots"))
        return Chart("Tracer concentration, Ogata–Banks", Axis("Distance x (m)", lo=0, hi=600), Axis("c / c₀", lo=0, hi=1.05), series,
                     note="Exact profile every 15 min; dots are the demo solver (MUSCL advection, central diffusion) on its finest grid, around the front at 1 h.").render()
    if tid.startswith("A1P-001"):
        x = np.linspace(0, prm.get("L", 1000.0), 101)
        r = fn(x, **prm)
        series = [Series(x, r["H"], "Exact hydraulic grade line", css="s-water", width=2.4)]
        if demo is not None:
            series.append(Series(demo["x"], demo["h"], "EPA EPANET 2.2 nodal heads", css="s-solver", kind="dots"))
        return Chart("Hydraulic grade line along the pipe", Axis("Distance x (m)"), Axis("Head (m)"), series,
                     note=f"Colebrook–White gives f = {r['friction_factor']:.5f} and a total loss of {r['head_loss_total']:.3f} m. EPANET uses the Swamee–Jain approximation, which is expected to sit about 0.6 % high here.").render()
    if tid.startswith("A1F-020"):
        x = np.linspace(0, 100, 801)
        r = fn(x, **prm)
        series = [Series(x, r["h"], "Exact (stationary Bélanger jump)", css="s-water", kind="step", width=2.2)]
        if demo is not None:
            near = demo[(demo["x"] > 40) & (demo["x"] < 60)]
            series.append(Series(near["x"], near["h"], "Demo solver after 200 s", css="s-solver", kind="dots"))
        return Chart("Depth across the jump", Axis("Distance x (m)", lo=40, hi=60), Axis("Depth h (m)", lo=0), series,
                     note=f"h₁ = {r['h1']:.3f} m, h₂ = {r['h2']:.3f} m, energy loss {r['energy_loss']:.3f} m. The jump must stay at x = 50 m; the first-order scheme spreads it over about two cells.").render()
    if tid.startswith("A1P-010"):
        from references.todini import solve_network

        net = json.loads((m["_case_dir"] / "inputs/network.json").read_text())
        sol = solve_network(net)
        got_h: dict[str, float] = {}
        got_q: dict[str, float] = {}
        p = _results_for(tid, result_dirs)
        if p is not None:
            d = pd.read_parquet(p)
            got_h = {str(r.element_id): float(r.h) for r in d[d["element_type"] == "node"].itertuples()}
            got_q = {str(r.element_id): float(r.Q) for r in d[d["element_type"] == "link"].itertuples()}
        rows = "".join(f"<tr><td>{esc(n)}</td><td class=num>{h:.3f}</td><td class=num>{(f'{got_h[n]:.3f}' if n in got_h else '–')}</td>"
                       f"<td class=num>{(f'{(got_h[n] - h) * 1000:+.1f}' if n in got_h else '–')}</td></tr>" for n, h in zip(sol["nodes"], sol["head"]))
        rows2 = "".join(f"<tr><td>{esc(p_)}</td><td class=num>{q * 3600:.2f}</td><td class=num>{(f'{got_q[p_] * 3600:.2f}' if p_ in got_q else '–')}</td></tr>" for p_, q in zip(sol["pipes"], sol["flow"]))
        return (f'<div class="split"><div class="table-scroll"><table class="data"><caption>Junction heads</caption><thead><tr><th>Node</th><th class=num>Exact (m)</th><th class=num>EPANET 2.2 (m)</th><th class=num>Diff (mm)</th></tr></thead><tbody>{rows}</tbody></table></div>'
                f'<div class="table-scroll"><table class="data"><caption>Pipe flows</caption><thead><tr><th>Pipe</th><th class=num>Exact (m³/h)</th><th class=num>EPANET 2.2 (m³/h)</th></tr></thead><tbody>{rows2}</tbody></table></div></div>')
    return ""


def fig_macdonald_2d(m: dict, result_dirs: list[Path]) -> str:
    from references.macdonald_2d import bed_elevation, depth_profile

    prm = m["reference"]["generator"]["parameters"]
    x = np.linspace(0, prm["L"], 801)
    zb = bed_elevation(x, L=prm["L"], q=prm["q"], n_manning=prm["n_manning"])
    series = [Series(x, zb + depth_profile(x), "Exact water surface", css="s-water", width=2.4)]
    p = _results_for(m["test_id"], result_dirs)
    if p is not None:
        df = pd.read_parquet(p)
        df = df[np.isclose(df["t"], df["t"].max())]
        ymid = np.unique(df["y"])[len(np.unique(df["y"])) // 2]
        row = df[np.isclose(df["y"], ymid)].sort_values("x")
        series.append(Series(row["x"], row["h"] + row["z"], f"Demo solver, centreline, t = {row['t'].iloc[0] / 3600:g} h", css="s-solver", kind="dots"))
    return Chart("Steady water surface along the channel", Axis("Distance x (m)"), Axis("Elevation (m)"), series, floor=[(x, zb)],
                 note="Ochre: the bed built so that this surface is exact. The solver starts from a uniform depth and must settle onto it.").render()


def fig_oblique_jump(m: dict, result_dirs: list[Path], assets: Path) -> str:
    from references.oblique_jump import depth_velocity, states

    prm = m["reference"]["generator"]["parameters"]
    st = states(prm["Fr1"], prm["theta_deg"], prm["h1"], prm.get("g", 9.81))
    p = _results_for(m["test_id"], result_dirs)
    parts = []
    if p is not None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = pd.read_parquet(p)
        df = df[np.isclose(df["t"], df["t"].max())]
        xs, ys = np.unique(df["x"]), np.unique(df["y"])
        grid = df.pivot_table(index="y", columns="x", values="h").to_numpy()
        fig, ax = plt.subplots(figsize=(7.6, 5.0), dpi=150)
        im = ax.imshow(grid, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]], cmap="Blues", vmin=0.8, vmax=2.0, interpolation="nearest")
        xl = np.array([0, xs[-1]])
        ax.plot(xl, xl * np.tan(np.deg2rad(st["jump_to_wall_deg"])), color="#b23a2c", lw=1.6, ls="--", label=f"exact jump, {st['jump_to_wall_deg']:.2f}° to the wall")
        ax.axhline(0, color="#12263a", lw=3)
        cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
        cb.set_label("Depth (m)", fontsize=8)
        cb.ax.tick_params(labelsize=7)
        ax.legend(loc="upper left", fontsize=8, frameon=False)
        ax.set_title("Depth from the demo solver (finest grid); flow enters from the west and north", fontsize=9, loc="left")
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
        fig.tight_layout()
        out = assets / f"{short_id(m['test_id'])}-map.png"
        fig.savefig(out, facecolor="white")
        plt.close(fig)
        parts.append(f'<figure class="figure map"><img src="../assets/{out.name}" alt="Depth map of the oblique jump with the exact jump line" loading="lazy"></figure>')
        xc = float(xs[np.argmin(np.abs(xs - 30.0))])
        sec = df[np.isclose(df["x"], xc)].sort_values("y")
        yy = np.linspace(0, ys[-1], 600)
        ex = depth_velocity(np.full_like(yy, xc), yy, **{k: prm[k] for k in ("Fr1", "theta_deg", "h1")})["h"]
        parts.append(Chart(f"Cross-section at x = {xc:g} m", Axis("Distance from the wall y (m)", lo=0), Axis("Depth h (m)", lo=0), [
            Series(yy, ex, "Exact", css="s-water", kind="step", width=2.2),
            Series(sec["y"], sec["h"], "Demo solver", css="s-solver", kind="dots")],
            note=f"Upstream depth {st['h1']:g} m, downstream {st['h2']:.3f} m (Fr₂ = {st['Fr2']:.2f}); the jump angle is {st['beta_deg']:.2f}° to the incoming flow.").render())
    return "".join(parts)


def fig_thacker(m: dict, result_dirs: list[Path]) -> str:
    from references.thacker import bed_elevation, depth_velocity

    prm = m["reference"]["generator"]["parameters"]
    x = np.linspace(-1.1, 1.1, 881)
    zb = bed_elevation(x, 0 * x, prm["h0"], prm["L"])
    series = []
    period = 2 * np.pi / (np.sqrt(2 * 9.81 * prm["h0"]) / prm["L"])
    for k, frac in enumerate([0, 0.25, 0.5]):
        r = depth_velocity(x, 0 * x, frac * period, **{k2: v for k2, v in prm.items()})
        zs = np.where(r["h"] > 0, r["h"] + zb, np.nan)
        series.append(Series(x, zs, f"Exact, t = {frac:g} T", css=f"s-time s-t{k}"))
    best = None
    for d in result_dirs:
        cands = sorted(d.glob("A2A-001_thacker_dx*.parquet"), key=lambda p: float(p.stem.split("dx")[1]))
        if cands:
            best = cands[0]
    if best is not None:
        df = pd.read_parquet(best)
        df = df[np.isclose(df["t"], df["t"].max())]
        ymid = df["y"].to_numpy()[np.argmin(np.abs(df["y"].to_numpy()))]
        row = df[np.isclose(df["y"], ymid) & (df["h"] > 1e-4)].sort_values("x")
        series.append(Series(row["x"], row["h"] + row["z"], f"Demo solver, t = {m['simulation']['t_end']:g} s", css="s-solver", kind="dots"))
        r = depth_velocity(x, 0 * x, float(m["simulation"]["t_end"]), **prm)
        series.append(Series(x, np.where(r["h"] > 0, r["h"] + zb, np.nan), f"Exact, t = {m['simulation']['t_end']:g} s", css="s-water", dash=True))
    return Chart("Water surface across the bowl (y = 0)", Axis("x (m)"), Axis("Elevation (m)", lo=-0.11, hi=0.04), series, floor=[(x, zb)],
                 note=f"Period T = {period:.2f} s. The plane tilts and the shoreline moves; the demo solver is first-order finite volume.").render()


def _read_table(path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    rows = [r for r in csv.reader(path.open(encoding="utf-8-sig")) if r]
    data = np.array([[float(v) for v in r[:2]] for r in rows[1:]])
    return data[:, 0], data[:, 1], rows[0]


def fig_ea(m: dict, result_dirs: list[Path], assets: Path) -> str:
    d = m["_case_dir"]
    parts = []
    bc = d / "inputs/inflow.csv"
    if bc.is_file():
        t, q, hdr = _read_table(bc)
        t_end_h = float(m["simulation"]["t_end"]) / 3600
        t_h = np.append(t / 60, t_end_h) if t[-1] / 60 < t_end_h else t / 60
        q2 = np.append(q, q[-1]) if len(t_h) > len(q) else q
        parts.append(Chart("Inflow hydrograph (boundary condition)", Axis("Time (h)", lo=0), Axis("Inflow (m³/s)", lo=0),
                           [Series(t_h, q2, "Inflow", css="s-water", kind="area")]).render())
    lv = d / "inputs/boundary_level.csv"
    if lv.is_file():
        t, z, _ = _read_table(lv)
        parts.append(Chart("Water level imposed on the west boundary", Axis("Time (h)", lo=0, hi=20), Axis("Level (m)"),
                           [Series(np.append(t / 60, 20.0), np.append(z, z[-1]), "Boundary level", css="s-water")], hlines=[(10.25, "Sill crest 10.25 m")]).render())
    res = _results_for(m["test_id"], result_dirs)
    if res is not None:
        df = pd.read_parquet(res)
        cell = None
        fields = df.groupby("t").size()
        full_t = fields[fields == fields.max()].index.to_numpy()
        xs = np.unique(df["x"]); ys = np.unique(df["y"])
        cell = float(np.median(np.diff(xs))) * float(np.median(np.diff(ys))) if len(ys) > 1 else float(np.median(np.diff(xs)))
        vol = [float(df[df["t"] == t]["h"].sum() * cell) for t in full_t]
        exp_states = {s["id"]: s for s in m["reference"]["expected_states"]}
        series = [Series(full_t / 3600, vol, "Stored volume, demo solver", css="s-solver", kind="dots")]
        if bc.is_file():
            pass
        if bc.is_file():
            t, q, _ = _read_table(bc)
            tt = np.linspace(0, float(m["simulation"]["t_end"]), 400)
            qq = np.interp(tt, t * 60, q)
            cum = np.concatenate([[0], np.cumsum(0.5 * (qq[1:] + qq[:-1]) * np.diff(tt))])
            series.insert(0, Series(tt / 3600, cum, "Cumulative inflow (exact)", css="s-water"))
        if bc.is_file():
            parts.append(Chart("Mass balance: water stored vs water let in", Axis("Time (h)", lo=0), Axis("Volume (m³)", lo=0), series,
                               note="In a closed domain the two must coincide at every instant; the gating check is the final value.").render())
        probes = [p for p in m["simulation"].get("probes") or []]
        if probes:
            ser = []
            for k, p in enumerate(probes[:7]):
                xs_ = df["x"].to_numpy(); ys_ = df["y"].to_numpy()
                d2 = (xs_ - p["x"]) ** 2 + (ys_ - p.get("y", 0)) ** 2
                sub = df[d2 == d2.min()].sort_values("t").drop_duplicates("t")
                level = np.where(sub["h"].to_numpy() > 1e-3, (sub["h"] + sub["z"]).to_numpy(), np.nan)
                ser.append(Series(sub["t"] / 3600, level, p["id"], css=f"s-cat s-c{k % 7}", width=1.6))
            hl = [(s["value"], f"Expected {s['value']:g} m") for s in m["reference"]["expected_states"] if s["variable"] == "h+z" and "time" in s]
            parts.append(Chart("Water level at the output points, demo solver", Axis("Time (h)", lo=0), Axis("Water level (m)"), ser, hlines=hl[:1], note="Gaps are times when the cell at that point is dry.").render())
        png = _terrain_map(m, df, assets)
        if png:
            parts.insert(0, png)
    elif (d / "inputs/terrain.asc").is_file():
        png = _terrain_map(m, None, assets)
        if png:
            parts.insert(0, png)
    return "".join(parts)


def _terrain_map(m: dict, df: pd.DataFrame | None, assets: Path) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource

    sid = short_id(m["test_id"])
    out = assets / f"{sid}-map.png"
    terrain = m["_case_dir"] / "inputs/terrain.asc"
    prm_all = json.loads((m["_case_dir"] / "inputs/case.json").read_text())
    if terrain.is_file():
        with terrain.open() as fh:
            hdr = {}
            for _ in range(6):
                k, v = fh.readline().split()
                hdr[k.lower()] = float(v)
            z = np.loadtxt(fh)
        z[z <= hdr.get("nodata_value", -9999) + 1] = np.nan
        step = max(1, int(max(z.shape) / 900))
        z = z[::step, ::step]
        cs = hdr["cellsize"] * step
        ext = [hdr["xllcorner"], hdr["xllcorner"] + cs * z.shape[1], hdr["yllcorner"], hdr["yllcorner"] + cs * z.shape[0]]
    else:
        dom = prm_all["domain"]
        ext = [0, dom["xmax"], 0, dom["ymax"]]
        z = None
    aspect = (ext[3] - ext[2]) / (ext[1] - ext[0])
    fig_w = 7.6
    fig, ax = plt.subplots(figsize=(fig_w, max(1.8, min(6.5, fig_w * aspect + 0.9))), dpi=150)
    if z is not None:
        ls = LightSource(azdeg=315, altdeg=40)
        zf = np.where(np.isfinite(z), z, np.nanmin(z))
        shade = ls.hillshade(zf, vert_exag=6 if np.nanmax(z) - np.nanmin(z) < 5 else 1.5, dx=cs, dy=cs)
        ax.imshow(zf, extent=ext, cmap="YlOrBr_r", alpha=0.55)
        ax.imshow(shade, extent=ext, cmap="gray", alpha=0.45)
        title = "Terrain"
    else:
        ax.add_patch(plt.Rectangle((0, 0), ext[1], ext[3], color="#e8dcc6", zorder=0))
        title = "Flat floodplain"
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    if df is not None:
        last = df[df["t"] == df["t"].max()]
        xs = np.unique(last["x"]); ys = np.unique(last["y"])
        if len(xs) > 1 and len(ys) > 1:
            dx_, dy_ = np.median(np.diff(xs)), np.median(np.diff(ys))
            gx = np.arange(xs.min(), xs.max() + dx_ / 2, dx_); gy = np.arange(ys.min(), ys.max() + dy_ / 2, dy_)
            grid = np.full((len(gy), len(gx)), np.nan)
            ii = np.rint((last["x"].to_numpy() - gx[0]) / dx_).astype(int); jj = np.rint((last["y"].to_numpy() - gy[0]) / dy_).astype(int)
            grid[jj, ii] = np.where(last["h"].to_numpy() > 0.005, last["h"].to_numpy(), np.nan)
            im = ax.imshow(grid, origin="lower", extent=[gx[0] - dx_ / 2, gx[-1] + dx_ / 2, gy[0] - dy_ / 2, gy[-1] + dy_ / 2], cmap="Blues", vmin=0, alpha=0.9, interpolation="nearest", zorder=2)
            cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
            cb.set_label("Depth at end of run (m)", fontsize=7)
            cb.ax.tick_params(labelsize=7)
            title += "\nwater depth at the end of the run (demo solver)"
    for p in m["simulation"].get("probes") or []:
        ax.plot(p["x"], p.get("y", 0), marker="o", ms=5, mfc="white", mec="#12263a", zorder=3)
        ax.annotate(p["id"], (p["x"], p.get("y", 0)), xytext=(4, 4), textcoords="offset points", fontsize=7, color="#12263a")
    bnd = prm_all.get("boundaries")
    line = ((bnd.get("inflow") or {}).get("line")) if isinstance(bnd, dict) else None
    if line:
        (x0, y0), (x1, y1) = line
        ax.plot([x0, x1], [y0, y1], color="#b23a2c", lw=3, solid_capstyle="round")
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9, loc="left")
    ax.tick_params(labelsize=7)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(out, transparent=False, facecolor="white")
    plt.close(fig)
    return f'<figure class="figure map"><img src="../assets/{out.name}" alt="{esc(title)} for {esc(m["title"])}, with output points and the inflow line in red" loading="lazy"></figure>'


def fig_track_b(m: dict) -> str:
    ref = m["reference"]
    if not ref.get("results_path"):
        return ""
    df = pd.read_parquet(m["_case_dir"] / ref["results_path"])
    parts = []
    links = df[df["element_type"] == "link"]
    nodes = df[df["element_type"] == "node"]
    if m["test_id"].startswith("B-RTC"):
        win = 12 * 3600.0
        h = nodes[(nodes["element_id"] == "PP_U433") & (nodes["t"] <= win)].sort_values("t")
        parts.append(Chart("Wet well PP_U433 against the rule thresholds (first 12 h, SWMM 5.2.4)",
                           Axis("Time (h)", lo=0, hi=12), Axis("Wet-well depth (m)", lo=0),
                           [Series(h["t"] / 3600, h["h"], "Depth at PP_U433", css="s-water", kind="area")],
                           hlines=[(0.3048, "all pumps OFF ≤ 0.30 m"), (1.778, "pump 1 ON ≥ 1.78 m"), (2.032, "pump 2 ≥ 2.03 m")]).render())
        ser = []
        for k, (pid, lab) in enumerate([("U433_Psan_1_ou_2", "Pump 1 (U433_Psan_1_ou_2)"), ("U433_Psan_1_et_2", "Pump 2 (U433_Psan_1_et_2)"), ("U433_Psan_1_et_2_et_3", "Pump 3 (U433_Psan_1_et_2_et_3)")]):
            q = links[(links["element_id"] == pid) & (links["t"] <= win)].sort_values("t")
            if len(q):
                ser.append(Series(q["t"] / 3600, q["Q"] * 1000, lab, css=f"s-cat s-c{k}", kind="step", width=1.4))
        parts.append(Chart("Pump flows as the rules switch them", Axis("Time (h)", lo=0, hi=12), Axis("Flow (L/s)", lo=0), ser,
                           note="Each step is a rule firing. A candidate that evaluates the rules at different moments moves these steps, which shows up in pumped volume and peak timing.").render())
        return "".join(parts)
    var, label, scale, units = ("Q", "Flow", 1.0, "cfs") if m["test_id"].startswith("B-EXTRAN") else ("Q", "Flow", 1000.0, "L/s")
    peaks = links.groupby("element_id")["Q"].apply(lambda s: s.abs().max()).sort_values(ascending=False)
    ser = []
    for k, eid in enumerate(peaks.index[:5]):
        s = links[links["element_id"] == eid].sort_values("t")
        ser.append(Series(s["t"] / 3600, s["Q"] * scale, f"Link {eid}", css=f"s-cat s-c{k}", width=1.6))
    parts.append(Chart(f"Reference flows in the five busiest links ({ref['engine']} {ref['version']})", Axis("Time (h)", lo=0), Axis(f"{label} ({units})"), ser).render())
    if m["test_id"].startswith("B-EPANET"):
        ser = []
        nd = nodes.copy()
        for k, eid in enumerate(sorted(nd["element_id"].unique())[:6]):
            s = nd[nd["element_id"] == eid].sort_values("t")
            ser.append(Series(s["t"] / 3600, s["p"] / 9810.0, f"Node {eid}", css=f"s-cat s-c{k}", width=1.6))
        parts.append(Chart("Reference pressure head at junctions (EPANET 2.2)", Axis("Time (h)", lo=0), Axis("Pressure head (m)"), ser).render())
    return "".join(parts)


def fig_convergence(card: dict) -> str:
    c = card.get("convergence_result") or {}
    if not c.get("spacings") or not c.get("errors"):
        return ""
    h = np.array(c["spacings"], float)
    e = np.array(c["errors"], float)
    if np.any(e <= 0):
        return ""
    series = [Series(h, e, f"Observed L1 error ({c['variable']})", css="s-solver", kind="dots"),
              Series(h, e, "", css="s-solver", width=1.2)]
    p_exp = float(c["expected_order"])
    ref = e[0] * (h / h[0]) ** p_exp
    series.append(Series(h, ref, f"Slope {p_exp:g} (expected order)", css="s-muted", dash=True, width=1.4))
    p_obs = c.get("observed_order")
    title = f"Grid convergence: observed order {p_obs:.2f}" if p_obs is not None else "Grid convergence"
    ch = Chart(title, Axis("Grid spacing", log=True), Axis(f"L1 error in {c['variable']}", log=True), series, width=560, height=300)
    ch.series[1].label = "Observed L1 error"
    ch.legend = False
    return '<div class="conv">' + ch.render() + legend([("Observed L1 error", "s-solver"), (f"Reference slope {p_exp:g}", "s-muted key-dash")]) + "</div>"


# ── pages ───────────────────────────────────────────────────────────────────


def criteria_table(m: dict, card: dict | None) -> str:
    res = {r["id"]: r for r in (card or {}).get("criteria_results", [])}
    rows = []
    for c in m["scoring"]["criteria"]:
        thr = c["threshold"]
        r = res.get(c["id"])
        if r is None:
            got = '<td class="num muted">–</td><td></td>'
        else:
            obs = r.get("observed")
            got = f'<td class="num">{fmt(obs) if obs is not None else "n/a"} {esc(thr.get("units", ""))}</td><td>{verdict({"passed": r["passed"]})}</td>'
        rows.append(
            f"<tr><td><b>{esc(c['id'])}</b><div class=muted>{esc(c['metric'])} of {esc(c.get('variable', ''))}"
            f"{' · gating' if c.get('gating') else ' · informational'}</div></td>"
            f'<td class="num">{esc(thr["op"].replace("abs<=", "|x| ≤").replace("<=", "≤").replace(">=", "≥"))} {fmt(thr["value"])} {esc(thr.get("units", ""))}</td>'
            f"{got}<td class=rationale>{esc(c.get('rationale', ''))}</td></tr>"
        )
    conv = m["scoring"].get("convergence")
    if conv and conv.get("not_applicable"):
        rows.append(f'<tr><td><b>convergence</b><div class=muted>not applicable</div></td><td class="num muted">–</td><td class="num muted">–</td><td></td>'
                    f"<td class=rationale>{esc(conv['not_applicable'])}</td></tr>")
        conv = None
    if conv:
        cr = (card or {}).get("convergence_result") or {}
        if cr:
            o = cr.get("observed_order")
            got = f'<td class="num">{fmt(o) if o is not None else "n/a"}</td><td>{verdict({"passed": cr.get("passed")})}</td>'
        else:
            got = '<td class="num muted">–</td><td></td>'
        note = esc(cr.get("note", "")) if cr else ""
        rows.append(
            f"<tr><td><b>convergence</b><div class=muted>observed order of {esc(conv['norm'])} error in {esc(conv['variable'])} · gating</div></td>"
            f'<td class="num">≥ {fmt(conv["min_observed_order"])} <span class=muted>(design {fmt(conv["expected_order"])})</span></td>{got}'
            f"<td class=rationale>Measured from the error on every refinement level, as in ASME V&V 20. {note}</td></tr>"
        )
    return (
        '<div class="table-scroll"><table class="data criteria"><thead><tr><th>Criterion</th><th class=num>Pass when</th>'
        "<th class=num>Latest</th><th>Result</th><th>Why this tolerance</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def inputs_table(m: dict) -> str:
    rows = []
    for e in m["inputs"]:
        if e.get("pending"):
            state = f'<span class="chip st-draft">pending</span><div class=muted>{esc(e["pending"]["reason"])}</div>'
            h = ""
        elif e.get("committed", True) is False:
            src = e.get("source", {})
            state = f'Fetched by hash from <a href="{esc(src.get("url", "#"))}">source</a>'
            h = f'<code title="{esc(e["sha256"])}">{esc(e["sha256"][:12])}…</code>'
        else:
            state = f'<a href="../data/cases/{esc(short_id(m["test_id"]))}/{esc(e["path"])}" download>Download</a>'
            h = f'<code title="{esc(e["sha256"])}">{esc(e["sha256"][:12])}…</code>'
        rows.append(f"<tr><td><code>{esc(e['path'])}</code></td><td>{esc(e['role'])}</td><td>{esc(e['format'])}</td><td>{h}</td><td>{state}</td></tr>")
    return ('<div class="table-scroll"><table class="data"><thead><tr><th>File</th><th>Role</th><th>Format</th><th>SHA-256</th><th>Get it</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def run_length(t: float, steady: bool = False) -> str:
    if steady:
        return "steady state"
    if t >= 3600:
        return f"{t / 3600:g} h"
    if t >= 60:
        return f"{t / 60:g} min"
    return f"{t:g} s"


def citation_text(c: dict) -> str:
    authors = ", ".join(c.get("authors") or [])
    year = c.get("year", "n.d.")
    link = ""
    if c.get("doi"):
        link = f' <a href="https://doi.org/{esc(c["doi"])}">doi:{esc(c["doi"])}</a>'
    elif c.get("url"):
        link = f' <a href="{esc(c["url"])}">{esc(c["url"].split("//")[-1][:60])}</a>'
    extra = f" {esc(c['report_number'])}." if c.get("report_number") else ""
    return f"{esc(authors)} ({esc(year)}). <i>{esc(c['title'])}</i>.{extra}{link}"


REF_SHORT = {
    "analytic": "Exact solution",
    "intercomparison": "Objective expected states",
    "exact_states": "Exact states (conservation)",
    "measured": "Measurements",
    "pinned_engine": "Pinned engine output",
}


def _dedupe_paragraphs(html_text: str, known: list[str]) -> str:
    """Drop README paragraphs that repeat the manifest description or notes word for word."""
    import re

    norm = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip().lower()  # noqa: E731
    seen = {norm(k) for k in known if k}
    return re.sub(r"<p>(.*?)</p>", lambda mt: "" if norm(mt.group(1)) in seen else mt.group(0), html_text, flags=re.S)


def checklist_html(items: list[dict]) -> str:
    li = []
    for it in items:
        cls, mark = ("met", "✓") if it["met"] else ("unmet", "✗")
        li.append(f'<li class="{cls}"><span class="mark" aria-label="{"met" if it["met"] else "not met"}">{mark}</span>'
                  f'<span><b>{esc(it["label"])}</b><span class="stage">for {esc(it["stage"])}</span><span class="detail">{esc(it["detail"])}</span></span></li>')
    return '<ul class="checklist">' + "".join(li) + "</ul>"


def legacy_figures(m: dict, result_dirs: list[Path], assets: Path) -> str:
    """Server-drawn figures for a case (boundary conditions, maps, Track B traces, …)."""
    tid = m["test_id"]
    kind = m["reference"]["kind"]
    try:
        if kind == "analytic" and tid.startswith("A2A-001"):
            return fig_thacker(m, result_dirs)
        if kind == "analytic" and tid.startswith("A2A-010"):
            return fig_macdonald_2d(m, result_dirs)
        if kind == "analytic" and tid.startswith("A2A-020"):
            return fig_oblique_jump(m, result_dirs, assets)
        if kind == "analytic" and m["physics"]["dimensionality"] == "1D":
            return fig_analytic_1d(m, result_dirs)
        if kind == "intercomparison" or tid.startswith("A2L-EA6A"):
            return fig_ea(m, result_dirs, assets)
        if kind == "pinned_engine":
            return fig_track_b(m)
    except Exception as exc:  # a missing optional input must not break the build
        print(f"WARN figures for {tid}: {exc}", file=sys.stderr)
    return ""


PARITY_DIR = ROOT / "test_catalog" / "track_b" / "parity"


CANDIDATE_NAMES = {"swmm-5.1.15": "EPA SWMM 5.1.15", "openswmm-6": "OpenSWMM Engine v6", "openswmm-6-fv": "OpenSWMM Engine v6, finite-volume routing",
                   "hydra": "Hydra 17 (urban drainage)"}
ERR_WHY = {
    "swmm-5.1.15": "Most use input syntax added after 5.1 (inlets, newer options), which an older engine rejects with ERROR 200.",
    "openswmm-6": "The v6 pre-release stops at initialisation with an unexplained parse error; see docs/openswmm.md.",
    "hydra": "Hydra refuses these with an explicit validation message (for example incomplete subcatchment data or ground below the initial water table), or took longer than 600 s; see docs/hydra.md.",
}


def load_parity() -> list[tuple[dict, pd.DataFrame]]:
    out = []
    for tier in ("pr", "nightly", "release", "bellinge"):
        for summ in sorted(PARITY_DIR.glob(f"{tier}_*.summary.json")):
            df_path = summ.with_name(summ.name.replace(".summary.json", ".parquet"))
            if df_path.is_file():
                out.append((json.loads(summ.read_text(encoding="utf-8")), pd.read_parquet(df_path)))
    return out


PARITY_FINDINGS: dict[str, str] = {
    "hydra": ('<div class="finding"><b>Hydra is a different drainage engine, by design.</b> '
              "Hydra states that it follows conservation laws, not SWMM's numbers. On the nightly tier 125 of 476 scored models are within 5 % of SWMM 5.2.4 "
              "(median worst element 29 %). Hydrology-only models agree (16 of 17 LID models); routed flows differ, even on the classic EXTRAN examples "
              "(median 7.5 %), so the difference is its Preissmann-slot routing rather than units or input reading. "
              'Details: <a href="https://github.com/scott-jeffers/benchmark1d2d/blob/master/docs/hydra.md">docs/hydra.md</a>.</div>'),
    "openswmm-6": ('<div class="finding"><b>OpenSWMM v6 runs almost everything, and changes more.</b> '
                   "It runs 499 of 500 nightly models (SWMM 5.1.15: 479), and 425 of the 496 it scores are within 5 % of 5.2.4. "
                   "In 20 of the 71 over 5 % the worst node is an outfall, where v6 reports a depth and 5.2.4 almost none. "
                   "One model, <code>weir-overtopping</code>, shows water created at an outfall (routing continuity −48 %), and long continuous runs are up to 57 times slower. "
                   'Details for the developers: <a href="https://github.com/scott-jeffers/benchmark1d2d/blob/master/docs/openswmm.md">docs/openswmm.md</a>.</div>'),
}


def parity_section(parity: list[tuple[dict, pd.DataFrame]]) -> str:
    if not parity:
        return ""
    names = {"pr": "PR tier", "nightly": "Nightly tier", "release": "Release tier", "bellinge": "Bellinge network (1 real system)"}
    rows, tables = [], []
    for summ, df in parity:
        sc = df[df["status"] == "scored"]
        w = sc["worst_pct"].abs()
        buckets = [
            (int((w == 0).sum()), "st-frozen", "Identical"),
            (int(((w > 0) & (w <= 1)).sum()), "st-candidate", "Within 1 %"),
            (int(((w > 1) & (w <= 5)).sum()), "st-release", "1–5 %"),
            (int((w > 5).sum()), "st-fail", "Over 5 %"),
            (int(df["status"].isin(["candidate_error", "candidate_timeout"]).sum()), "st-draft", "Candidate could not run it"),
        ]
        cand = CANDIDATE_NAMES.get(summ["candidate"], summ["candidate"])
        rows.append((f"{cand}, {names.get(summ['tier'], summ['tier']).lower()} ({summ['models']})", buckets))
        top = sc.assign(a=w).sort_values("a", ascending=False).head(12)
        trs = "".join(
            f"<tr><td><code>{esc(r.model_id)}</code></td><td class=num>{fmt(r.worst_pct)} %</td>"
            f"<td class=small>{esc(str(r.peak_depth_detail) if isinstance(r.peak_depth_detail, str) else '–')}</td>"
            f"<td class=small>{esc(str(r.volume_detail) if isinstance(r.volume_detail, str) else '–')}</td></tr>"
            for r in top.itertuples() if r.a > 0)
        errs = df[df["status"].isin(["candidate_error", "candidate_timeout"])]
        err_txt = (f"<p class=small>{len(errs)} model(s) the candidate could not run: "
                   + ", ".join(f"<code>{esc(x)}</code>" for x in errs["model_id"].head(8)) + (" …" if len(errs) > 8 else "")
                   + ". " + ERR_WHY.get(summ["candidate"], "") + "</p>") if len(errs) else ""
        tables.append(f"""<h3>{esc(cand)}, {esc(names.get(summ['tier'], summ['tier']).lower())}: largest differences</h3>
<div class="table-scroll"><table class="data"><thead><tr><th>Model</th><th class=num>Worst</th><th>Peak depth (worst node)</th><th>Volume (worst link)</th></tr></thead><tbody>{trs or '<tr><td colspan=4>No differences.</td></tr>'}</tbody></table></div>{err_txt}""")
    bars = hbars("Each candidate against EPA SWMM 5.2.4: worst element per model", rows, unit=" models")
    cands = sorted({summ["candidate"] for summ, _ in parity})
    v6 = "".join(PARITY_FINDINGS.get(c, "") for c in ("openswmm-6", "hydra") if c in cands)
    return f"""<section id="parity"><h2>Does another engine match SWMM 5.2.4?</h2>
<p>Any SWMM-compatible engine can be scored against the reference across a whole tier with <code>scripts/corpus_parity.py</code>: both engines run every model, and each model gets the worst node (relative peak depth) and worst link (relative volume of |Q|) — the same metrics as the catalog's Track B cases. Two candidates are scored here: the previous release, <b>EPA SWMM 5.1.15</b> (OWA build in <code>swmm-toolkit</code> 0.10.0), HydroCouple's rewritten <b>OpenSWMM Engine v6</b> (pre-release <code>openswmm</code> 6.0.0a4 on PyPI, run with its new engine, both with each model's own routing and with its new finite-volume routing, <code>FLOW_ROUTING FV</code>, which changes the numerical method and so is expected to differ), and NEER AI's <b>Hydra 17</b> urban-drainage engine (CLI 4.1.1). Each week the same comparison runs on <b>Bellinge</b> (Odense, Denmark; Pedersen et al. 2021, CC BY 4.0), a real combined sewer system of about 1,000 nodes and 1,000 links with pumps, weirs and control rules, on a two-day storm.</p>
{bars}
{legend([("Identical", "st-frozen"), ("Within 1 %", "st-candidate"), ("1–5 %", "st-release"), ("Over 5 %", "st-fail"), ("Candidate could not run it", "st-draft")])}
<div class="findings" style="margin-top:18px">
  <div class="finding"><b>Most legacy models are bit-identical.</b> On the EXTRAN examples 5.1.15 and 5.2.4 produce the same numbers to every stored digit, so a tier made only of them cannot detect most engine changes. The PR tier is therefore picked for feature coverage.</div>
  <div class="finding"><b>Differences cluster in features that changed.</b> Low-impact development, groundwater, seepage and some hydrology models differ by tens to hundreds of percent at their worst element: these are real behaviour changes between releases, not noise.</div>
  {v6}<div class="finding"><b>A difference is not a defect.</b> Track B says how far a candidate is from the reference engine, not which one is right. Whether 5.2.4 is physically better is a Track A question.</div>
</div>
{''.join(tables)}
<p class="small">The self-check (5.2.4 scored against itself) must give exactly 0 on every PR-tier model; CI runs it on every pull request.</p>
</section>"""


EPANET_PARITY_NAMES = {"hydra": "Hydra 17 water distribution, its defaults",
                       "hydra-tank0": "Hydra 17 water distribution, EPANET tank stepping (--tank-tolerance 0)",
                       "epanet20": "EPANET 2.0 (2.00.12), for scale"}


def epanet_parity_section() -> str:
    """Six EPANET networks scored against EPANET 2.2 (scripts/epanet_parity.py)."""
    files = [PARITY_DIR / f"epanet_{k}.parquet" for k in EPANET_PARITY_NAMES]
    files = [f for f in files if f.is_file()]
    if not files:
        return ""
    head = "".join(f"<th class=num>{esc(EPANET_PARITY_NAMES[f.stem[len('epanet_'):]])}</th>" for f in files)
    frames = {f.stem[len("epanet_"):]: pd.read_parquet(f).set_index("network") for f in files}
    nets = list(next(iter(frames.values())).index)
    trs = ""
    for net in nets:
        cells = ""
        for k, df in frames.items():
            r = df.loc[net] if net in df.index else None
            if r is None or r["status"] != "scored":
                cells += "<td class=num>–</td>"
                continue
            cells += (f"<td class=num>{fmt(r['peak_pressure_pct'])} % / {fmt(r['volume_pct'])} %</td>")
        trs += f"<tr><td><code>{esc(net)}</code></td>{cells}</tr>"
    return f"""<section id="epanet-parity"><h2>Does another engine match EPANET 2.2?</h2>
<p>The same comparison for water-distribution engines, on the six example networks bundled with WNTR 1.5.0 (EPANET's Net1, Net2, Net3 and Net6 and two Kentucky utility networks), so the set is independent of any candidate's own test fixtures. Each cell gives the worst node's relative peak pressure and the worst pipe's relative volume of |Q| against EPANET 2.2, from <code>scripts/epanet_parity.py</code>.</p>
<div class="table-scroll"><table class="data"><thead><tr><th>Network</th>{head}</tr></thead><tbody>{trs}</tbody></table></div>
<div class="findings" style="margin-top:18px">
  <div class="finding"><b>Hydra's tanks are deliberately different.</b> With its default second-order tank integration Hydra matches EPANET 2.2 within 1 % on four networks and differs by up to 27 % in pipe volume on Net6. With EPANET's first-order tank stepping (<code>--tank-tolerance 0</code>) five of six match within 1 % and Net6 within 3.4 %; pressures agree within 0.7 % either way.</div>
</div>
</section>"""


def parity_history_section() -> str:
    """Each nightly SWMM parity run, appended by the result collector (parity/history.csv)."""
    f = PARITY_DIR / "history.csv"
    if not f.is_file():
        return ""
    h = pd.read_csv(f, dtype=str).fillna("")
    if h.empty:
        return ""
    trs = "".join(
        f"<tr><td>{esc(r.date)}</td><td>{esc(CANDIDATE_NAMES.get(r.candidate, r.candidate))}</td><td><code>{esc(r.candidate_version)}</code></td>"
        f"<td class=num>{esc(r.models)}</td><td class=num>{esc(r.within_1pct)}</td><td class=num>{esc(r.within_5pct)}</td>"
        f"<td class=num>{esc(r.candidate_error)}</td></tr>"
        for r in h.iloc[::-1].head(30).itertuples())
    return f"""<section id="history"><h2>Parity over time</h2>
<p>One row per nightly run of each candidate (newest first). The result collector appends a row after every nightly run and opens an issue when five or more models move in or out of "within 1 %", when the number of models a candidate cannot run changes, or when its version changes.</p>
<div class="table-scroll"><table class="data"><thead><tr><th>Date</th><th>Candidate</th><th>Version</th><th class=num>Models</th><th class=num>Within 1 %</th><th class=num>Within 5 %</th><th class=num>Cannot run</th></tr></thead><tbody>{trs}</tbody></table></div>
<p class="small"><a href="data/track_b/history.csv" download>history.csv</a></p></section>"""


def corpus_page(index: pd.DataFrame | None, census: pd.DataFrame | None, parity: list | None = None) -> str:
    if index is None or census is None:
        return layout("Track B corpus", "<header class=page-head><h1>Track B corpus</h1><p class=lede>The corpus census has not been run yet.</p></header>", "corpus.html")
    st = index["status"].value_counts()
    status_css = {"ran": "st-frozen", "input_error": "st-fail", "engine_error": "st-fail", "timeout": "st-draft", "not_run": "st-draft", "harness_error": "st-draft"}
    status_names = {"ran": "Ran cleanly", "input_error": "Input error", "engine_error": "Engine error", "timeout": "Timed out (60 s)", "not_run": "Not run", "harness_error": "Harness error"}
    bars = hbars("Census outcome on EPA SWMM 5.2.4", [(status_names.get(k, k), [(int(v), status_css.get(k, "st-draft"), status_names.get(k, k))]) for k, v in st.items()], unit=" models")
    rt = index.loc[index["status"] == "ran", "runtime_s"].dropna()
    edges = np.array([0, 0.1, 0.3, 1, 3, 10, 30, 60.01])
    hist, _ = np.histogram(rt.clip(upper=90), bins=edges)
    labels = ["< 0.1 s", "0.1–0.3 s", "0.3–1 s", "1–3 s", "3–10 s", "10–30 s", "30–60 s"]
    rt_bars = hbars("Runtime on SWMM 5.2.4 of the models that ran (one CPU core)", [(lab, [(int(n), "st-candidate", lab)]) for lab, n in zip(labels, hist)], unit=" models")
    tiers = index["tier"].value_counts()
    tag_counts = Counter(t for tags in index["tags"] for t in tags)
    top = [t for t, _ in tag_counts.most_common(24)]
    tag_rows = []
    for t in top:
        has = index["tags"].apply(lambda ts, t=t: t in ts)
        tag_rows.append((t.replace("_", " "), [
            (int((has & (index["tier"] == "tier_pr")).sum()), "st-frozen", "PR tier"),
            (int((has & (index["tier"] == "tier_nightly")).sum()), "st-candidate", "Nightly tier"),
            (int((has & (index["tier"] == "tier_release")).sum()), "st-release", "Release tier only"),
            (int((has & (index["tier"] == "none")).sum()), "st-draft", "Not in a tier"),
        ]))
    tag_bars = hbars("Models per tag and tier (24 most common tags)", tag_rows)
    cont = index["continuity_routing_pct"].dropna().abs()
    worst = index.dropna(subset=["continuity_routing_pct"]).assign(a=lambda d: d["continuity_routing_pct"].abs()).sort_values("a", ascending=False).head(12)
    worst_rows = "".join(f"<tr><td><code>{esc(r.model_id)}</code></td><td class=num>{r.continuity_routing_pct:+.2f} %</td><td class=num>{r.runtime_s:.2f} s</td></tr>" for r in worst.itertuples())
    commit = str(index["upstream_commit"].iloc[0])
    body = f"""
<header class="page-head">
  <h1>Track B corpus</h1>
  <p class="lede">{len(index):,} EPA SWMM models from <a href="https://github.com/HydroCouple/openswmm.engine.benchmarks/tree/{commit}">HydroCouple openswmm.engine.benchmarks</a> at commit <code>{commit[:12]}</code>, each run on the pinned EPA SWMM {esc(str(census['engine_version'].iloc[0]))} engine. Models are not copied here: the index records each file's URL at that commit and its SHA-256.</p>
</header>
<ul class="toc" aria-label="On this page"><li><a href="#census">Does it run?</a></li><li><a href="#tiers">Tiers</a></li><li><a href="#parity">Parity results</a></li><li><a href="#coverage">Coverage</a></li><li><a href="#continuity">Continuity</a></li><li><a href="#data">Data</a></li></ul>
<section id="census"><h2>Does each model run on the reference engine?</h2>{bars}
<p>A model joins a tier only if it runs cleanly <b>and</b> SWMM's own continuity error stays within ±5 %: a reference that loses or creates water cannot anchor parity. {int(st.get('input_error', 0)) + int(st.get('engine_error', 0))} models stop with input or engine errors (mostly older-version syntax: ERROR 205, 207, 209, 211, 235, and 32 missing rainfall files, ERROR 317), {int(st.get('timeout', 0))} exceed the 60 s census limit, and {int(((index['status'] == 'ran') & ~index['continuity_ok']).sum())} run but fail the continuity rule. All stay in the index so upstream maintainers can see them.</p></section>
<section id="tiers"><h2>Tiers</h2>
<div class="table-scroll"><table class="data"><thead><tr><th>Tier</th><th class=num>Models</th><th>Selection rule</th><th>Download</th></tr></thead><tbody>
<tr><td>PR</td><td class=num>{int(tiers.get('tier_pr', 0))} + 3 catalog cases</td><td>Runs in ≤ 5 s, picked for feature-tag coverage across collections, at least five control-rule models; gates every pull request</td><td><a href="data/track_b/tier_pr.json">selection.json</a></td></tr>
<tr><td>Nightly</td><td class=num>{int(tiers.get('tier_nightly', 0)) + int(tiers.get('tier_pr', 0))}</td><td>Runs in ≤ 10 s, picked greedily so every tag is covered</td><td><a href="data/track_b/tier_nightly.json">selection.json</a></td></tr>
<tr><td>Release</td><td class=num>{int((index['tier'] != 'none').sum())}</td><td>Every model that runs, keeps continuity within ±5 % and has a verified licence</td><td><a href="data/track_b/tier_release.json">selection.json</a></td></tr>
</tbody></table></div></section>
{parity_section(parity or [])}
{parity_history_section()}
{epanet_parity_section()}
<section><h2>Runtime</h2>{rt_bars}</section>
<section id="coverage"><h2>What the tiers cover</h2>{tag_bars}{legend([("PR", "st-frozen"), ("Nightly", "st-candidate"), ("Release only", "st-release"), ("Not in a tier", "st-draft")])}</section>
<section id="continuity"><h2>Largest routing continuity errors on SWMM 5.2.4</h2>
<p>Continuity error is SWMM's own mass-balance check. Models beyond ±5 % are excluded from every tier: their reference results are not physically meaningful, so agreeing with them proves nothing.</p>
<div class="table-scroll"><table class="data"><thead><tr><th>Model</th><th class=num>Routing continuity</th><th class=num>Runtime</th></tr></thead><tbody>{worst_rows}</tbody></table></div>
<p class="small">Median absolute routing continuity error across models that ran: {cont.median():.3f} %.</p></section>
<section id="data"><h2>Data</h2><p>Download the full index as <a href="data/track_b/corpus_index.csv">CSV</a> or <a href="data/track_b/corpus_index.parquet">Parquet</a>. Fetch models with <code>python scripts/fetch_track_b_models.py --tier nightly</code>; every file is checked against its hash.</p></section>"""
    return layout("Track B corpus", body, "corpus.html")


AUDIT = [
    ("Track B parity compared results with themselves", "Every non-analytic case (all of Track B, every measured case) was scored by comparing the solver's output with itself, so any output passed and earned a B-1 % claim.",
     "Parity now compares per element against the pinned engine's reference results; a case without its reference is not scored rather than passed. Regression tests cover pass, perturbed-fail and missing-reference."),
    ("Error norms inflated every observed order by one", "L1 was computed as mean(|e|) × dx, adding a power of dx; reported orders were +1 (L1) and +0.5 (L2) too high.",
     "Norms are domain-normalised. True orders: Ritter 0.95, Stoker 0.95, MacDonald 1.99, Joukowsky 0.49."),
    ("Two of four 1D 'passes' never solved anything", "The demo MacDonald and Joukowsky solvers returned the analytical solution; zero error was then reported as order 1.0 and passed.",
     "Real solvers: Heun integration of the gradually-varied-flow equation and a method-of-characteristics water-hammer solver. Convergence now refuses round-off errors on every mesh."),
    ("The Thacker reference violated mass conservation", "The bowl solution used ω = √(8gh₀)/L and omitted a cos² term; continuity residual was 83 % of ∂h/∂t, so every correct solver would fail.",
     "Corrected solution (ω = √(2gh₀)/L) with pointwise PDE-residual tests. A real 2D finite-volume solver now passes with order 0.91."),
    ("The Joukowsky convergence target was unreachable", "A minimum order of 0.8 cannot be met by any first-order fixed-grid scheme on a linear discontinuity (theory gives 0.5).",
     "Target set from theory to 0.5 / 0.4 minimum; case version bumped to 2.0.0 because scores are not comparable."),
    ("EA Tests 1, 2, 4, 5 were filed as laboratory validation", "These are code inter-comparison tests with no measured truth; inputs were empty placeholders.",
     "Reclassified as A2C code inter-comparison with real inputs from the official archive (by hash) and objective expected states: settled pond level and mass conservation."),
    ("Placeholder and mis-licensed inputs", "Most inputs were 0-byte files; Weber, Bergant and Rubinato data were labelled Unlicense; Bellinge rain-gauge data is CC BY-NC.",
     "Real case definitions or explicit pending inputs that block promotion; journal-only data marked TBD-confirm; the CC BY-NC item is excluded."),
    ("Two Track B cases did not test what they claimed", "B-EXTRAN-001 was a 2-conduit synthetic network presented as EXTRAN Example 1; in B-RTC-001 the rule's condition never changed, so no control switch was ever exercised.",
     "B-EXTRAN-001 now runs the real EXTRAN Example 1; B-RTC-001 is a pump-station network whose rules switch one pump 74 times in 36 h."),
    ("Gauges on cell faces mixed two cells", "A probe exactly between cells took depth from one cell and bed from another, producing ±4 cm level errors in a flat pond.",
     "Ties resolve to a single cell; regression test added."),
    ("The PR tier contained models that cannot serve as references", "11 of its 49 corpus models were unfit: 4 do not run on SWMM 5.2.4 (input errors) and 7 run with continuity errors of 6.6 % to 100 %. The PR gate could never have passed, and agreeing with a non-conserving reference proves nothing.",
     "A full census runs every corpus model on SWMM 5.2.4; tiers admit only models that run cleanly with |continuity| ≤ 5 %. The PR tier is now 38 corpus models (7 with control rules) plus the 3 catalog cases."),
    ("Signatures implied authorship", "All published cards were signed with development keys hard-coded in the repository, and the documented verify command checked manifests, not cards.",
     "benchmark1d2d verify-card checks the content hash and says when a card carries a public development key; the site no longer presents those signatures as proof of origin."),
    ("Every pass was labelled A-V", "Validation and parity passes received verification or fixed B-1 % claims.",
     "Claims follow the case class (A-V, A-C, A-L, A-F) and the gating tolerance (B-x %)."),
]


AUDIT_2 = [
    ("Six exact-solution cases had never been scored, and their specifications could not be met", "Darcy–Weisbach, Todini network, Ogata–Banks tracer, Bélanger jump, MacDonald 2D and oblique jump had references but no runs. The pipe cases asked for grid convergence of a steady closed-form solution, and their \"1 %\" tolerances were compared against absolute errors in pascals.",
     "Each case is re-specified for its physics: relative norms when a tolerance is in %, a head-loss metric, element-keyed network references, and \"convergence not applicable\" where nothing is discretised. EPA EPANET 2.2 passes both pipe cases (head loss 0.60 % high, the Swamee–Jain offset theory predicts); new demo solvers pass the tracer (order 1.67), the jump (1.00), MacDonald 2D (1.02) and the oblique jump (0.91)."),
    ("The MacDonald 2D reference was not a solution of the shallow-water equations", "It held the free surface flat while water flowed at 0.2 m²/s without friction, which momentum forbids; the module's docstring admitted that a solver copying the field would pass.",
     "Rebuilt by MacDonald's method: A1F-001's profile on a 2D grid with Manning friction and a bed constructed so the steady equations hold exactly (momentum residual tested). Case version 2.0.0."),
    ("The oblique-jump reference used the wrong jump relation and the wrong side", "It solved the gas-dynamics θ–β–M relation (jump at 34.0° instead of the shallow-water 39.6° for Fr₁ = 2.5, θ = 15°) and labelled the region between wall and jump as upstream.",
     "Rewritten from the exact shallow-water Rankine–Hugoniot conditions, with tests for mass, normal momentum and tangential velocity across the jump. Case version 2.0.0."),
    ("The Joukowsky \"continuity\" check measured front smearing, not mass", "Mean |u| where p exceeds half the rise grows with the smeared zone, so accurate first-order schemes failed (1.87 %) while a non-conserving sharp scheme could pass.",
     "Replaced by an exact storage balance: the packed volume ∫Δp dx must equal ρa²V₀t. The method-of-characteristics demo conserves it to round-off. Case version 3.0.0."),
    ("Two builds of SWMM 5.2.4 disagree on the control-rule case", "The official win64 binaries and the swmm-toolkit build match EXTRAN Example 1 exactly, but on B-RTC-001 differ by −3.7 % peak depth and move a pump-cycle peak by 92,400 s.",
     "Reported every run by the cross-build job; B-RTC-001 cannot be frozen until its tolerances or timing metric are revised (decision recorded in the case README)."),
    ("The PR corpus tier tested one collection only", "All 38 PR-tier models were legacy EXTRAN examples, on which SWMM 5.1.15 and 5.2.4 give bit-identical output, so the gate could not see most engine changes.",
     "The PR tier is now 40 models picked to cover feature tags (9 collections, ≥ 5 control-rule models). A corpus parity runner scores any SWMM build against 5.2.4 across a tier; a self-check requires exactly zero against itself on every PR run."),
    ("Nothing said how a case becomes frozen", "Only frozen cases count, but there was no rule for getting there, so no case could ever be frozen on evidence.",
     "Eight promotion rules, seven computed from the manifest and score cards; every case page shows its checklist and the catalog lists what each case still needs."),
]


def reports_page(manifests: list[dict], cards: dict, evidence: dict[str, list[dict]] | None = None) -> str:
    rows = []
    for m in manifests:
        c = cards.get(m["test_id"])
        if not c:
            continue
        conv = c.get("convergence_result") or {}
        text = f'{m["test_id"]} {m.get("title", "")} {c["solver"]["name"]}'.lower()
        rows.append(
            f'<tr data-text="{esc(text)}" data-result="{card_verdict(c)}"><td><a href="{page_name(m["test_id"])}">{esc(short_id(m["test_id"]))}</a><div class=muted>{esc(m.get("title", ""))}</div></td><td>{esc(c["solver"]["name"])}</td><td>{verdict(c)}</td>'
            f'<td>{esc(", ".join(c.get("certification_claims") or []) or "–")}</td>'
            f'<td class=num>{fmt(conv["observed_order"]) if conv.get("observed_order") is not None else "–"}</td>'
            f'<td><code class="hash" title="{esc(c.get("content_hash", ""))}" data-copy="{esc(c.get("content_hash", ""))}" data-label="content hash">{esc(c.get("content_hash", "")[:10])}…</code></td>'
            f'<td><a href="data/scorecards/{esc(c["_path"].name)}" download>JSON</a></td></tr>'
        )
    audit = "".join(f"<li><h3>{esc(t)}</h3><p><b>Found:</b> {esc(a)}</p><p><b>Now:</b> {esc(b)}</p></li>" for t, a, b in AUDIT)
    audit2 = "".join(f"<li><h3>{esc(t)}</h3><p><b>Found:</b> {esc(a)}</p><p><b>Now:</b> {esc(b)}</p></li>" for t, a, b in AUDIT_2)
    xb_rows = "".join(
        f'<tr><td><a href="{page_name(c["test_id"])}">{esc(short_id(c["test_id"]))}</a></td><td>{esc(c["solver"]["name"])}</td><td>{verdict(c)}</td>'
        f'<td>{esc("; ".join(r["id"] + " " + fmt(r["observed"]) + " " + r["threshold"]["units"] for r in c["criteria_results"]))}</td></tr>'
        for lst in (evidence or {}).values() for c in lst)
    body = f"""
<header class="page-head"><h1>Reports</h1>
<p class="lede">Every score card is canonical JSON with a SHA-256 content hash, so any change to a published result is detectable. Cards are also Ed25519-signed; the demo runs below use a development key published in the repository, so their signatures show integrity, not authorship. Certification runs will be signed with a key held by the maintainers.</p></header>
<section><h2>Score cards</h2>
<form class="filters" role="search" onsubmit="return false">
  <label>Search <input type="search" id="rq" placeholder="Case, title or solver"></label>
  <label>Result <select id="rq-result"><option value="">Any</option><option value="pass">Pass</option><option value="fail">Fail</option></select></label>
  <output id="rq-count" aria-live="polite"></output>
</form>
<div class="table-scroll"><table class="data" data-filter="rq"><thead><tr><th>Case</th><th>Solver</th><th>Result</th><th>Claims</th><th class=num>Observed order</th><th>Content hash</th><th>File</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="small"><a href="data/scorecards.zip" download>Download every score card (.zip)</a>. Check one with <code>benchmark1d2d verify-card path/to/card.json</code>.</p></section>
{f"""<section><h2>Second build of the reference engine</h2>
<p>The official EPA SWMM 5.2.4 Windows binaries run on each SWMM catalog input and are scored against the reference built from the same source in <code>swmm-toolkit</code>. Agreement shows a parity reference does not depend on the compiler.</p>
<div class="table-scroll"><table class="data"><thead><tr><th>Case</th><th>Build</th><th>Result</th><th>Worst element per criterion</th></tr></thead><tbody>{xb_rows}</tbody></table></div></section>""" if xb_rows else ""}
<section><h2>Audit log</h2>
<p>End-to-end reviews found the following defects. Each is fixed, covered by tests, and recorded here because earlier results published from this repository were affected.</p>
<h3>Second review, 14 October 2026</h3>
<ol class="audit">{audit2}</ol>
<h3>First review, 13 October 2026</h3>
<ol class="audit">{audit}</ol></section>"""
    return layout("Reports", body, "reports.html")



def downloads_page(files: list[tuple[str, str, Path]]) -> str:
    groups: dict[str, list] = defaultdict(list)
    for group, label, path in files:
        groups[group].append((label, path))
    sections = []
    for g, items in groups.items():
        rows = "".join(
            f'<tr><td><a href="{esc(p.relative_to(DIST).as_posix())}" download>{esc(label)}</a></td><td class=num>{size_text(p.stat().st_size)}</td>'
            f'<td><code class="hash" title="{esc(sha256(p))}" data-copy="{esc(sha256(p))}" data-label="SHA-256 of {esc(label)}">{esc(sha256(p)[:12])}…</code></td></tr>'
            for label, p in items
        )
        sections.append(f'<section><h2>{esc(g)}</h2><div class="table-scroll"><table class="data"><thead><tr><th>File</th><th class=num>Size</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    body = f"""<header class="page-head"><h1>Downloads</h1>
<p class="lede">Everything the site shows, as files. Hashes let you confirm a download matches what CI built; click Copy next to one and compare it with <code>sha256sum</code>.</p></header>
<section><h2>Which file do I need?</h2>
<div class="table-scroll"><table class="data guide"><tbody>
<tr><td>Run one case with my solver</td><td>The case bundle from its page (<a href="results.html">results</a>), then <code>python scripts/fetch_inputs.py &lt;ID&gt;</code> for any large input fetched by hash.</td></tr>
<tr><td>Run every case</td><td><a href="data/benchmark1d2d-catalog.zip" download>Every case (.zip)</a>, or clone the repository.</td></tr>
<tr><td>List or filter cases in a script</td><td><a href="data/catalog.csv" download>catalog.csv</a> (one row per case) or <a href="data/catalog.json" download>catalog.json</a> (full manifests).</td></tr>
<tr><td>Write results the scorer accepts</td><td><a href="data/schemas/results.schema.json" download>results.schema.json</a>; score cards follow <a href="data/schemas/scorecard.schema.json" download>scorecard.schema.json</a>.</td></tr>
<tr><td>Compare my SWMM engine with 5.2.4 node by node</td><td>The reference results (.parquet) below, or the <a href="corpus.html">corpus tiers</a> with <code>scripts/corpus_parity.py</code>.</td></tr>
<tr><td>Cite the sources</td><td><a href="data/citations.bib" download>citations.bib</a></td></tr>
</tbody></table></div></section>
{''.join(sections)}
<section><h2>Large inputs</h2><p>DEMs and corpus models are not mirrored here. Fetch and verify them with <code>python scripts/fetch_inputs.py</code> and <code>python scripts/fetch_track_b_models.py</code>; both refuse any file whose SHA-256 differs from the manifest.</p></section>"""
    return layout("Downloads", body, "downloads.html")


def doc_page(title: str, active: str, sources: list[Path], intro: str = "") -> str:
    parts = []
    for p in sources:
        if p.is_file():
            parts.append(f'<section class="prose">{md(p.read_text(encoding="utf-8"))}</section>')
    body = f'<header class="page-head"><h1>{esc(title)}</h1>{intro}</header>' + "".join(parts)
    return layout(title, body, active)


# ── bundles ─────────────────────────────────────────────────────────────────


def committed_files(m: dict) -> list[Path]:
    d = m["_case_dir"]
    skip = {e["path"] for e in m["inputs"] if e.get("committed", True) is False}
    out = []
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.name not in (".gitkeep", "SETUP.md") and p.relative_to(d).as_posix() not in skip and "__pycache__" not in p.parts:
            out.append(p)
    return out


def write_bundles(manifests: list[dict], cards: dict, index: pd.DataFrame | None) -> list[tuple[str, str, Path]]:
    data = DIST / "data"
    files: list[tuple[str, str, Path]] = []
    all_zip = data / "benchmark1d2d-catalog.zip"
    data.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(all_zip, "w", zipfile.ZIP_DEFLATED) as zall:
        for m in manifests:
            sid = short_id(m["test_id"])
            cdir = data / "cases" / sid
            zpath = data / "cases" / f"{sid}.zip"
            cdir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                from benchmark1d2d.catalog.kit import kit_files

                if m["status"] != "draft":
                    import kitpack

                    for name, blob in kitpack.files(m, DIST / "data" / "check").items():
                        (cdir / name).parent.mkdir(parents=True, exist_ok=True)
                        (cdir / name).write_bytes(blob)
                        z.writestr(f"{sid}/{name}", blob)
                for p in committed_files(m):
                    rel = p.relative_to(m["_case_dir"])
                    (cdir / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, cdir / rel)
                    z.write(p, f"{sid}/{rel.as_posix()}")
                    zall.write(p, f"test_catalog/{m['_rel'].split('test_catalog/')[1]}/{rel.as_posix()}")
    files.append(("Catalog", "Every case: manifests, READMEs, committed inputs (.zip)", all_zip))
    flat = []
    for m in manifests:
        clean = {k: v for k, v in m.items() if not k.startswith("_")}
        flat.append(clean)
    (data / "catalog.json").write_text(json.dumps(flat, indent=1, ensure_ascii=False), encoding="utf-8")
    with (data / "catalog.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["test_id", "title", "track", "component", "class", "status", "licence", "case_version", "dimensionality", "reference_kind", "latest_result"])
        for m in manifests:
            c = cards.get(m["test_id"])
            w.writerow([m["test_id"], m.get("title", ""), m["track"], dict((x[0], x[1]) for x in COMPONENTS)[m["_component"]], m["test_class"], m["status"],
                        m["provenance"]["license"], m["case_version"], m["physics"]["dimensionality"], m["reference"]["kind"],
                        "" if c is None else card_verdict(c)])
    files += [("Catalog", "catalog.json (all manifests)", data / "catalog.json"), ("Catalog", "catalog.csv (one row per case)", data / "catalog.csv")]
    bib = []
    seen = set()
    for m in manifests:
        for c in m["provenance"]["citations"]:
            key = (c.get("authors") or ["anon"])[0].split(",")[0].replace(" ", "") + str(c.get("year", ""))
            if key in seen:
                continue
            seen.add(key)
            fields = [f"  title = {{{c['title']}}}", f"  author = {{{' and '.join(c.get('authors') or [])}}}", f"  year = {{{c.get('year', '')}}}"]
            for k in ("doi", "url", "isbn"):
                if c.get(k):
                    fields.append(f"  {k} = {{{c[k]}}}")
            if c.get("report_number"):
                fields.append(f"  number = {{{c['report_number']}}}")
            bib.append(f"@misc{{{key},\n" + ",\n".join(fields) + "\n}")
    (data / "citations.bib").write_text("\n\n".join(bib) + "\n", encoding="utf-8")
    files.append(("Catalog", "citations.bib (every source cited by a case)", data / "citations.bib"))
    sdir = data / "schemas"
    sdir.mkdir(exist_ok=True)
    for p in sorted((ROOT / "schemas" / "v1").glob("*.schema.json")):
        shutil.copy2(p, sdir / p.name)
        files.append(("Schemas (v" + (ROOT / "schemas/v1/SCHEMA_VERSION").read_text().strip() + ")", p.name, sdir / p.name))
    scd = data / "scorecards"
    scd.mkdir(exist_ok=True)
    with zipfile.ZipFile(data / "scorecards.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for c in cards.values():
            shutil.copy2(c["_path"], scd / c["_path"].name)
            z.write(c["_path"], c["_path"].name)
    files.append(("Results", "All score cards (.zip)", data / "scorecards.zip"))
    for m in manifests:
        rp = (m["reference"] or {}).get("results_path")
        if rp:
            files.append(("Results", f"{short_id(m['test_id'])} reference results, {m['reference']['engine']} {m['reference']['version']} (.parquet)", data / "cases" / short_id(m["test_id"]) / rp))
    if index is not None:
        tb = data / "track_b"
        tb.mkdir(exist_ok=True)
        idx = index.copy()
        idx["tags"] = idx["tags"].apply(lambda t: ";".join(t))
        idx.to_csv(tb / "corpus_index.csv", index=False)
        shutil.copy2(ROOT / "test_catalog/track_b/corpus_index.parquet", tb / "corpus_index.parquet")
        for tier in ("pr", "nightly", "release"):
            shutil.copy2(ROOT / f"test_catalog/track_b/tier_{tier}/selection.json", tb / f"tier_{tier}.json")
        files += [("Track B corpus", "corpus_index.csv", tb / "corpus_index.csv"), ("Track B corpus", "corpus_index.parquet", tb / "corpus_index.parquet")]
        files += [("Track B corpus", f"tier_{t}.json", tb / f"tier_{t}.json") for t in ("pr", "nightly", "release")]
        if (PARITY_DIR / "history.csv").is_file():
            shutil.copy2(PARITY_DIR / "history.csv", tb / "history.csv")
            files.append(("Track B corpus", "Nightly parity history (history.csv)", tb / "history.csv"))
        for pq in sorted(PARITY_DIR.glob("*.parquet")):
            shutil.copy2(pq, tb / f"parity_{pq.name}")
            files.append(("Track B corpus", f"Parity results {pq.stem.replace('_', ', ')} (.parquet)", tb / f"parity_{pq.name}"))
    return files


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    import checkdata
    import pages
    import netcharts
    import profiles as prof

    pages.H = sys.modules[__name__]
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorecards", action="append", default=[], help="directories with *.scorecard.json (later wins)")
    ap.add_argument("--results", action="append", default=[], help="directories with demo results Parquet")
    args = ap.parse_args()
    suite_dirs = ["site/fixtures/scorecards", "out/track_b", "out/vertical_slice", "out/networks", "out/demo_2d"]
    production_dirs = ["site/fixtures/telemac", "site/fixtures/hecras", "site/fixtures/hecras66", "site/fixtures/anuga", "site/fixtures/geoclaw",
                       "site/fixtures/lisflood", "site/fixtures/hecras2d", "site/fixtures/hecras66_2d", "site/fixtures/openswmm", "site/fixtures/swmm_track_a", "out/openswmm", "out/swmm_track_a", "site/fixtures/hydronet", "out/hydronet", "site/fixtures/hydra", "out/hydra", "out/hydra_networks", "site/fixtures/coupled", "out/coupled", "out/submitted", "site/fixtures/tsnet", "out/tsnet", "site/fixtures/basilisk", "out/basilisk", "site/fixtures/landlab", "out/landlab", "site/fixtures/wntr", "out/wntr", "out/openswmm_fv", "out/telemac", "out/hecras", "out/hecras2d", "out/hecras66", "out/hecras66_2d", "out/anuga", "out/geoclaw", "out/lisflood"]
    score_dirs = [Path(p) for p in (args.scorecards or suite_dirs)]
    result_dirs = [Path(p) for p in (args.results or ["out/vertical_slice", "out/networks", "out/demo_2d"])]
    score_dirs = [p if p.is_absolute() else ROOT / p for p in score_dirs]
    result_dirs = [p if p.is_absolute() else ROOT / p for p in result_dirs]
    all_dirs = score_dirs + [ROOT / p for p in production_dirs]

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "tests").mkdir(parents=True)
    assets = DIST / "assets"
    assets.mkdir()
    shutil.copytree(SITE / "static", DIST / "static")

    manifests = load_manifests()
    known = {m["test_id"] for m in manifests}
    fields_by: dict[str, dict] = {}  # sid -> model key -> depth map (results viewer)
    cards = {k: v for k, v in load_scorecards(score_dirs).items() if k in known}  # one card per test (bundles, reports)
    runs = {k: v for k, v in pages.load_runs(all_dirs).items() if k in known}      # every solver's card per test
    idx_path = ROOT / "test_catalog/track_b/corpus_index.parquet"
    index = pd.read_parquet(idx_path) if idx_path.is_file() else None
    if index is not None and "status" not in index.columns:
        index = None
    census_path = ROOT / "test_catalog/track_b/corpus_census.parquet"
    census = pd.read_parquet(census_path) if census_path.is_file() else None

    evidence: dict[str, list[dict]] = defaultdict(list)  # second builds of reference engines (cross-build job)
    for p in sorted((SITE / "fixtures" / "cross_build").glob("*.json")) + sorted((ROOT / "out" / "cross_build").glob("*.cross_build.scorecard.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        c["_path"] = p
        evidence[c["test_id"]] = [c]  # later (fresh CI output) wins
    parity = load_parity()
    names = {pages.sid_of(m["test_id"]): pages.story(m)["name"] for m in manifests}
    checkable = checkdata.build(manifests, result_dirs, DIST / "data" / "check", names)  # before the downloads: they carry its sheets
    files = write_bundles(manifests, cards, index)
    # how each result was run: the build's commit and the model files the runners kept
    import os
    import subprocess as _sp

    pages.BUILD_COMMIT = os.environ.get("GITHUB_SHA") or _sp.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    for zp in sorted((SITE / "fixtures" / "inputs").glob("*/*.zip")):
        rel = Path("data") / "inputs" / zp.parent.name / zp.name
        (DIST / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zp, DIST / rel)
        pages.INPUT_ZIPS[(zp.parent.name, zp.stem)] = (rel.as_posix(), zp.stat().st_size)
    import netresults

    netindex = netresults.write_data(DIST, manifests, runs, pages.SOLVER, pages.SOLVERS_ORDER, pages.verdict, pages.story)
    pages.NETVIEW = {t["sid"]: t for t in netindex}
    for tid, by in runs.items():  # every run's signed card, by solver
        for k, c in by.items():
            d = DIST / "data" / "scorecards" / k
            d.mkdir(parents=True, exist_ok=True)
            shutil.copy2(c["_path"], d / c["_path"].name)

    out_pages = {
        "index.html": pages.home_page(manifests, runs, census, parity, evidence),
        "results.html": pages.results_page(manifests, runs, parity, census),
        "score.html": pages.score_page(manifests, checkable),
        "how-it-works.html": pages.how_page(manifests, runs),
        "catalog.html": pages.redirect("results.html"),
        "corpus.html": corpus_page(index, census, parity),
        "reports.html": reports_page(manifests, cards, evidence),
        "method.html": doc_page("Method", "method.html", [ROOT / "docs/methodology/vv_plan.md", ROOT / "docs/methodology/promotion.md", ROOT / "docs/methodology/tolerance_rationale.md", ROOT / "docs/bibliography.md"],
                                '<p class="lede">How tests are verified and validated, how limits are chosen, and the literature behind every test.</p>'),
        "get-started.html": doc_page("Command line", "get-started.html", [ROOT / "docs/get_started.md"]),
    }
    for m in manifests:
        sid = short_id(m["test_id"])
        by = runs.get(m["test_id"], {})
        exact = None
        try:
            exact = prof.exact_curves(m)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN exact curve for {sid}: {exc}", file=sys.stderr)
        curves = {}
        fixture = SITE / "fixtures" / "profiles" / f"{sid}.json"
        if fixture.is_file():
            curves.update({k: v for k, v in json.loads(fixture.read_text(encoding="utf-8")).items() if k in by})
        # extracts collected from the solver workflows (scripts/export_curves.py), newest first
        net_data = {}
        for cf in sorted((SITE / "fixtures" / "curves" / sid).glob("*.json")):
            try:
                rec = json.loads(cf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            k = rec.get("key", cf.stem)
            if k not in by or rec.get("case_version") != m["case_version"]:
                continue
            if rec.get("profile"):
                curves[k] = rec["profile"]
            if rec.get("net"):
                net_data[k] = rec["net"]
            if rec.get("field"):
                fields_by.setdefault(sid, {})[k] = rec["field"]
        for k in ("demo2d",):
            if k in by and sid in netcharts.SIDS:
                for d in result_dirs:
                    try:
                        dd = netcharts.extract(m, d)
                    except Exception:  # noqa: BLE001
                        dd = None
                    if dd:
                        net_data[k] = dd
                        break
        try:
            extra = netcharts.build(m, net_data) if sid in netcharts.SIDS else None
        except Exception as exc:  # noqa: BLE001 - a chart must not break the build
            print(f"WARN charts for {sid}: {exc}", file=sys.stderr)
            extra = None
        for k in ("demo1d", "demo2d"):
            if k in by:
                for d in result_dirs:
                    pq = prof.finest(d, m["test_id"])
                    if pq is not None:
                        try:
                            cv = prof.model_curve(m, pq)
                        except Exception as exc:  # noqa: BLE001
                            print(f"WARN demo curve for {sid}: {exc}", file=sys.stderr)
                            cv = None
                        if cv:
                            curves[k] = cv
                            break
        figs = legacy_figures(m, result_dirs, assets)
        out_pages[page_name(m["test_id"])] = pages.case_page(m, by, exact, curves, figs, evidence.get(m["test_id"], []), extra)
    # social preview images and result badges
    import og

    for m in manifests:
        sid = short_id(m["test_id"])
        by = runs.get(m["test_id"], {})
        st = pages.story(m)
        try:
            og.og_image(DIST / "assets" / "og" / f"{sid}.png", sid, pages.GROUPS.get(st["group"], ""), st["name"], st["question"],
                        sum(1 for c in by.values() if (pages.ranking.score(c) or 9) <= 1.0), len(by))
        except Exception as exc:  # noqa: BLE001 - a preview image must not break the build
            print(f"WARN preview image for {sid}: {exc}", file=sys.stderr)
        for k, c in by.items():
            bp = DIST / "badges" / sid / f"{k}.svg"
            bp.parent.mkdir(parents=True, exist_ok=True)
            sc = pages.ranking.score(c)
            rk = next((r for r in pages.ranking.rank_test(by) if r["key"] == k), {})
            right = (f"#{rk['rank']} of {len(by)} · " if rk.get("rank") else "") + pages.ranking.short(sc) + " of allowance"
            bp.write_text(og.badge_svg(f"OpenHydro Bench {sid}", right, pages.ranking.klass(sc)), encoding="utf-8")
    try:
        og.og_image(DIST / "assets" / "og" / "home.png", "A1F-010", "Open benchmarks for water models",
                    "Does your flood model get the water right?", "Every test has a known right answer. Run your model, compare, and get a result anyone can check.",
                    0, 0, footer=f"{sum(1 for m in manifests if m['status'] != 'draft')} tests · {len({k for v in runs.values() for k in v})} models · open source")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN home preview image: {exc}", file=sys.stderr)
    out_pages["downloads.html"] = downloads_page(files)
    import news

    out_pages["news.html"] = news.news_page(pages.layout, md, ROOT / "CHANGELOG.md", SITE / "fixtures" / "news.jsonl")
    news.atom_feed(ROOT / "CHANGELOG.md", SITE / "fixtures" / "news.jsonl", DIST / "feed.xml")
    out_pages["solvers.html"] = pages.solvers_index(manifests, runs)
    out_pages["compare.html"] = pages.compare_page(manifests, runs)
    import fields as fields_mod
    import viewer

    for m in manifests:  # the demo solver's maps come from its local results (it runs in every build's CI)
        sid_ = pages.sid_of(m["test_id"])
        if "demo2d" in (runs.get(m["test_id"]) or {}) and fields_mod.is_2d(m):
            for d in result_dirs:
                try:
                    f = fields_mod.extract_field(m, d)
                except Exception:  # noqa: BLE001
                    f = None
                if f:
                    fields_by.setdefault(sid_, {})["demo2d"] = f
                    break
    vindex = viewer.write_data(DIST, manifests, runs, fields_by, pages.SOLVER, pages.SOLVERS_ORDER, pages.verdict, pages.story)
    out_pages["viewer.html"] = viewer.viewer_page(pages.layout, vindex)
    out_pages["network.html"] = netresults.page(pages.layout, netindex)
    import rankpage

    out_pages["rankings.html"] = rankpage.page(pages.layout, rankpage.data(manifests, runs, pages.SOLVER, pages.story, pages.sid_of, pages.machine_info.summary))
    import coupledview

    cindex = coupledview.write_data(DIST, manifests, runs, pages.SOLVER, pages.verdict, pages.story)
    pages.COUPLEDVIEW = {t["sid"] for t in cindex}
    out_pages["coupled.html"] = coupledview.page(pages.layout, cindex)
    out_pages["scoring-review.html"] = pages.review.review_page(pages.layout, manifests, runs, pages.SOLVER, pages.SOLVERS_ORDER)
    (DIST / "solvers").mkdir(exist_ok=True)
    for k in {k for v in runs.values() for k in v}:
        out_pages[f"solvers/{k}.html"] = pages.solver_page(k, manifests, runs)
    for name, html_text in out_pages.items():
        (DIST / name).write_text(html_text, encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    n_runs = sum(len(v) for v in runs.values())
    print(f"site: {len(out_pages)} pages, {n_runs} runs from {len({k for v in runs.values() for k in v})} solvers, "
          f"{len(checkable)} browser-checkable tests, {len(files)} downloads -> {DIST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
