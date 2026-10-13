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

DIST = SITE / "dist"
REPO_URL = "https://github.com/scott-jeffers/benchmark1d2d"
BLOB = REPO_URL + "/blob/main/"

COMPONENTS = [
    ("A1P", "1D pressurized", "Pipe networks, water hammer and transport, checked against exact solutions."),
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

NAV = [
    ("index.html", "Overview"),
    ("catalog.html", "Catalog"),
    ("corpus.html", "Track B corpus"),
    ("reports.html", "Reports"),
    ("downloads.html", "Downloads"),
    ("method.html", "Method"),
    ("get-started.html", "Get started"),
]


def layout(title: str, body: str, active: str, depth: int = 0, description: str = "") -> str:
    up = "../" * depth
    nav = "".join(
        f'<a href="{up}{href}"{" aria-current=\"page\"" if href == active else ""}>{esc(label)}</a>' for href, label in NAV
    )
    built = datetime.now(timezone.utc).strftime("%d %b %Y")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Benchmark1d2d</title>
<meta name="description" content="{esc(description or 'Open verification and validation benchmarks for 1D, 2D and coupled hydraulic solvers.')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,600;0,800;1,400&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}static/style.css">
<link rel="icon" href="{up}static/favicon.svg" type="image/svg+xml">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
  <div class="wrap masthead-inner">
    <a class="wordmark" href="{up}index.html" aria-label="Benchmark1d2d home">
      <svg viewBox="0 0 40 24" aria-hidden="true"><path class="wm-bed" d="M0 22 L40 22"/><path class="wm-water" d="M0 6 L12 6 C18 6 22 18 40 18"/></svg>
      Benchmark1d2d
    </a>
    <nav class="nav" aria-label="Main">{nav}<a class="gh" href="{REPO_URL}">GitHub</a></nav>
  </div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="footer">
  <div class="wrap">
    <p>Benchmark1d2d is open source under Apache-2.0. Each dataset keeps its own licence, listed on its test page and in the <a href="{BLOB}DATA_LICENSES.md">data licence register</a>.</p>
    <p>Site built {built} from <a href="{REPO_URL}">{REPO_URL.split('github.com/')[1]}</a>.</p>
  </div>
</footer>
<script src="{up}static/site.js" defer></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
</body>
</html>
"""


def chip(status: str) -> str:
    return f'<span class="chip st-{esc(status)}" title="{esc(STATUS_TEXT.get(status, status))}">{esc(status)}</span>'


def verdict(card: dict | None) -> str:
    if card is None:
        return '<span class="verdict v-none">Not scored</span>'
    return '<span class="verdict v-pass">Pass</span>' if card.get("passed") else '<span class="verdict v-fail">Fail</span>'


def md(text: str) -> str:
    import markdown

    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


# ── figures ─────────────────────────────────────────────────────────────────


def _results_for(test_id: str, result_dirs: list[Path]) -> Path | None:
    sid = short_id(test_id)
    for d in result_dirs:
        for cand in (d / f"{test_id}.parquet", d / f"{sid}.parquet"):
            if cand.is_file():
                return cand
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
        x = np.linspace(0, 1000, 801)
        series = [Series(x, fn(x, t, **prm)["c"], f"t = {t / 3600:g} h", css=f"s-time s-t{k}") for k, t in enumerate([900, 1800, 2700, 3600])]
        return Chart("Tracer concentration, Ogata–Banks", Axis("Distance x (m)"), Axis("c / c₀", lo=0, hi=1.05), series).render()
    if tid.startswith("A1P-001"):
        x = np.linspace(0, prm.get("L", 1000.0), 101)
        r = fn(x, **prm)
        return Chart("Hydraulic grade line along the pipe", Axis("Distance x (m)"), Axis("Head H (m)"), [Series(x, r["H"], "Exact HGL", css="s-water")],
                     note=f"Total loss {r['head_loss_total']:.3f} m with f = {r['friction_factor']}.").render()
    if tid.startswith("A1F-020"):
        x = np.linspace(0, 100, 801)
        r = fn(x, **prm)
        return Chart("Conjugate depths across the jump", Axis("Distance x (m)"), Axis("Depth h (m)", lo=0), [Series(x, r["h"], "Bélanger sequent depths", css="s-water", kind="step")],
                     note=f"h₁ = {r['h1']:.3f} m, h₂ = {r['h2']:.3f} m, energy loss {r['energy_loss']:.3f} m. The jump position is neutral on a frictionless bed.").render()
    if tid.startswith("A1P-010"):
        from references.todini import solve_network

        net = json.loads((m["_case_dir"] / "inputs/network.json").read_text())
        sol = solve_network(net)
        rows = "".join(f"<tr><td>{esc(n)}</td><td class=num>{h:.3f}</td></tr>" for n, h in zip(sol["nodes"], sol["head"]))
        rows2 = "".join(f"<tr><td>{esc(p)}</td><td class=num>{q * 3600:.2f}</td></tr>" for p, q in zip(sol["pipes"], sol["flow"]))
        return f'<div class="split"><table class="data"><caption>Reference nodal heads</caption><thead><tr><th>Node</th><th class=num>Head (m)</th></tr></thead><tbody>{rows}</tbody></table><table class="data"><caption>Reference pipe flows</caption><thead><tr><th>Pipe</th><th class=num>Flow (m³/h)</th></tr></thead><tbody>{rows2}</tbody></table></div>'
    return ""


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
        ax.add_patch(plt.Rectangle((0, 0), ext[1], ext[3], color="#e8dcc6"))
        title = "Flat floodplain at 0 m"
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
            im = ax.imshow(grid, origin="lower", extent=[gx[0] - dx_ / 2, gx[-1] + dx_ / 2, gy[0] - dy_ / 2, gy[-1] + dy_ / 2], cmap="Blues", vmin=0, alpha=0.9, interpolation="nearest")
            cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
            cb.set_label("Depth at end of run (m)", fontsize=7)
            cb.ax.tick_params(labelsize=7)
            title += ", water depth at the end of the run (demo solver)"
    for p in m["simulation"].get("probes") or []:
        ax.plot(p["x"], p.get("y", 0), marker="o", ms=5, mfc="white", mec="#12263a")
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


def run_length(t: float) -> str:
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


def test_page(m: dict, card: dict | None, result_dirs: list[Path], assets: Path) -> str:
    tid = m["test_id"]
    comp = dict((c[0], c[1]) for c in COMPONENTS)[m["_component"]]
    kind = m["reference"]["kind"]
    figs = ""
    try:
        if kind == "analytic" and tid.startswith("A2A-001"):
            figs = fig_thacker(m, result_dirs)
        elif kind == "analytic" and m["physics"]["dimensionality"] == "1D":
            figs = fig_analytic_1d(m, result_dirs)
        elif kind == "intercomparison" or (tid.startswith("A2L-EA6A")):
            figs = fig_ea(m, result_dirs, assets)
        elif kind == "pinned_engine":
            figs = fig_track_b(m)
    except Exception as exc:  # a missing optional input must not break the build
        print(f"WARN figures for {tid}: {exc}", file=sys.stderr)
    ref_desc = {
        "analytic": f"Exact solution from <code>{esc(m['reference'].get('generator', {}).get('module', ''))}.{esc(m['reference'].get('generator', {}).get('function', ''))}</code>.",
        "intercomparison": "No exact or measured answer exists. The case is scored on states that follow from the inputs alone; published package results are context only.",
        "measured": f"Measured data at <code>{esc(m['reference'].get('data_path', ''))}</code> — availability: <b>{esc(m['reference'].get('availability', 'unknown').replace('_', ' '))}</b>.",
        "pinned_engine": f"{esc(m['reference'].get('engine'))} {esc(m['reference'].get('version'))}, run on the case's own input ({esc(m['reference'].get('build', 'build recorded in manifest'))}).",
    }[kind]
    states = ""
    if kind == "intercomparison":
        states = '<table class="data"><thead><tr><th>Expected state</th><th class=num>Value</th><th>Why it must hold</th></tr></thead><tbody>' + "".join(
            f"<tr><td><b>{esc(s['id'])}</b><div class=muted>{esc(s['variable'])}{(' at ' + esc(s['where'])) if s.get('where') else ''}</div></td>"
            f"<td class=num>{fmt(s['value'])} {esc(s['units'])}</td><td>{esc(s['derivation'])}</td></tr>"
            for s in m["reference"]["expected_states"]) + "</tbody></table>"
        ens = m["reference"]["ensemble"]
        states += f'<p class="callout">Published package results: {esc(ens["availability"].replace("_", " "))}. {esc(ens.get("notes", ""))}</p>'
    pending = [e for e in m["inputs"] if e.get("pending")]
    missing = ""
    if pending or (kind == "measured" and m["reference"].get("availability") != "available"):
        items = "".join(f"<li><b>{esc(e['path'])}</b>: {esc(e['pending']['reason'])} <span class=muted>Source: {esc(e['pending'].get('obtain_from', ''))}</span></li>" for e in pending)
        if kind == "measured" and m["reference"].get("availability") != "available":
            items += f"<li><b>Reference data</b>: {esc(m['reference'].get('availability', '').replace('_', ' '))}.</li>"
        missing = f'<section class="callout warn"><h2>What this case still needs</h2><ul>{items}</ul></section>'
    readme = m["_case_dir"] / "README.md"
    readme_html = md(readme.read_text(encoding="utf-8")) if readme.is_file() else ""
    if readme_html.startswith("<h1"):
        readme_html = readme_html.split("</h1>", 1)[1]
    sid = short_id(tid)
    downloads = [f'<li><a href="../data/cases/{sid}.zip" download>Case bundle (.zip)</a> <span class=muted>manifest, README, committed inputs</span></li>',
                 f'<li><a href="../data/cases/{sid}/manifest.json">manifest.json</a></li>']
    if kind == "pinned_engine" and m["reference"].get("results_path"):
        downloads.append(f'<li><a href="../data/cases/{sid}/{esc(m["reference"]["results_path"])}" download>Reference results (.parquet)</a></li>')
    if card:
        downloads.append(f'<li><a href="../data/scorecards/{esc(card["_path"].name)}" download>Latest score card (.json)</a></li>')
    conv = fig_convergence(card) if card else ""
    score_block = ""
    if card:
        claims = ", ".join(card.get("certification_claims") or []) or "none"
        score_block = (f'<p class="lede">Latest run: {verdict(card)} by <b>{esc(card["solver"]["name"])}</b> {esc(card["solver"].get("version", ""))}. '
                       f'Certification claims: <b>{esc(claims)}</b>.</p>')
    else:
        score_block = '<p class="lede">No solver has been scored on this case yet.</p>'
    phen = ", ".join(p.replace("_", " ") for p in m["physics"]["phenomena"])
    eqs = ", ".join(p.replace("_", " ") for p in m["physics"]["governing_equations"])
    cites = "".join(f"<li>{citation_text(c)}</li>" for c in m["provenance"]["citations"])
    body = f"""
<nav class="crumbs"><a href="../catalog.html">Catalog</a> / {esc(comp)}</nav>
<header class="page-head">
  <p class="test-id">{esc(sid)} {chip(m['status'])}</p>
  <h1>{esc(m.get('title', tid))}</h1>
  <p class="lede">{esc(m.get('description', ''))}</p>
</header>
<div class="test-layout">
  <aside class="facts">
    <dl>
      <dt>Track</dt><dd>{'A — physics' if m['track'] == 'A' else 'B — industry parity'}</dd>
      <dt>Class</dt><dd>{esc(CLASS_NAMES.get(m['test_class'], m['test_class']))}</dd>
      <dt>Dimension</dt><dd>{esc(m['physics']['dimensionality'])}, {esc(m['physics']['flow_type'].replace('_', ' '))}</dd>
      <dt>Equations</dt><dd>{esc(eqs)}</dd>
      <dt>Phenomena</dt><dd>{esc(phen)}</dd>
      <dt>Data licence</dt><dd><a href="{BLOB}DATA_LICENSES.md">{esc(m['provenance']['license'])}</a></dd>
      <dt>Case version</dt><dd>{esc(m['case_version'])}</dd>
      <dt>Run length</dt><dd>{run_length(float(m['simulation']['t_end']))}</dd>
    </dl>
    <h2 class="h-small">Downloads</h2>
    <ul class="downloads">{''.join(downloads)}</ul>
    <p class="small"><a href="{BLOB}{esc(m['_rel'])}">View this case on GitHub</a></p>
  </aside>
  <article class="test-main">
    {missing}
    <section><h2>Reference</h2><p>{ref_desc}</p>{states}{figs}</section>
    <section><h2>Scoring</h2>{score_block}{criteria_table(m, card)}{conv}</section>
    <section><h2>Inputs</h2>{inputs_table(m)}</section>
    <section class="prose">{readme_html}<p class="small">{esc(m['provenance'].get('adaptation_notes', ''))}</p></section>
    <section><h2>Sources</h2><ul class="cites">{cites}</ul></section>
  </article>
</div>"""
    return layout(m.get("title", tid), body, "catalog.html", depth=1, description=m.get("description", ""))


def coverage_matrix(manifests: list[dict], cards: dict) -> str:
    rows = []
    for code, name, blurb in COMPONENTS:
        ms = [m for m in manifests if m["_component"] == code]
        cells = "".join(
            f'<a class="cell st-{esc(m["status"])} {"scored-pass" if cards.get(m["test_id"], {}).get("passed") else ("scored-fail" if m["test_id"] in cards else "")}" '
            f'href="{page_name(m["test_id"])}" title="{esc(short_id(m["test_id"]))}: {esc(m.get("title", ""))} ({esc(m["status"])}{", scored " + ("pass" if cards[m["test_id"]]["passed"] else "fail") if m["test_id"] in cards else ""})">'
            f'<span>{esc(short_id(m["test_id"]).split("-", 1)[1] if "-" in short_id(m["test_id"]) else short_id(m["test_id"]))}</span></a>'
            for m in ms
        )
        rows.append(f'<div class="cov-row"><div class="cov-name"><b>{esc(name)}</b><span>{esc(blurb)}</span></div><div class="cov-cells">{cells}</div></div>')
    key = legend([("Frozen", "st-frozen"), ("Candidate", "st-candidate"), ("Draft", "st-draft")])
    return f'<div class="coverage">{"".join(rows)}</div><div class="cov-key">{key}<span class="muted">A dot marks a scored case: filled for pass, ringed for fail.</span></div>'


def catalog_page(manifests: list[dict], cards: dict) -> str:
    rows = []
    for m in manifests:
        c = cards.get(m["test_id"])
        comp = dict((x[0], x[1]) for x in COMPONENTS)[m["_component"]]
        rows.append(
            f'<tr data-track="{esc(m["track"])}" data-status="{esc(m["status"])}" data-comp="{esc(m["_component"])}" '
            f'data-text="{esc((m["test_id"] + " " + m.get("title", "") + " " + " ".join(m["physics"]["phenomena"])).lower())}">'
            f'<td><a href="{page_name(m["test_id"])}"><b>{esc(short_id(m["test_id"]))}</b></a></td>'
            f'<td><a href="{page_name(m["test_id"])}">{esc(m.get("title", ""))}</a><div class=muted>{esc(comp)}</div></td>'
            f"<td>{esc(CLASS_NAMES.get(m['test_class'], m['test_class']))}</td><td>{chip(m['status'])}</td>"
            f"<td><code>{esc(m['provenance']['license'])}</code></td><td>{verdict(c)}</td></tr>"
        )
    comp_opts = "".join(f'<option value="{c}">{esc(n)}</option>' for c, n, _ in COMPONENTS)
    counts = Counter(m["status"] for m in manifests)
    body = f"""
<header class="page-head">
  <h1>Test catalog</h1>
  <p class="lede">{len(manifests)} cases: {counts.get('frozen', 0)} frozen, {counts.get('candidate', 0)} candidate, {counts.get('draft', 0)} draft. Each one has a manifest that fixes its inputs by SHA-256, its reference, and every tolerance with the reason for it.</p>
</header>
<section><h2>Coverage</h2>{coverage_matrix(manifests, cards)}</section>
<section>
  <h2>All cases</h2>
  <form class="filters" role="search" onsubmit="return false">
    <label>Search <input type="search" id="q" placeholder="ID, title or phenomenon"></label>
    <label>Track <select id="f-track"><option value="">Both</option><option value="A">A — physics</option><option value="B">B — parity</option></select></label>
    <label>Component <select id="f-comp"><option value="">All</option>{comp_opts}</select></label>
    <label>Status <select id="f-status"><option value="">Any</option><option>frozen</option><option>candidate</option><option>draft</option></select></label>
    <output id="count" aria-live="polite"></output>
  </form>
  <div class="table-scroll"><table class="data catalog" id="catalog">
    <thead><tr><th>ID</th><th>Case</th><th>Class</th><th>Status</th><th>Data licence</th><th>Latest run</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
  <p class="small">Download the whole catalog as <a href="data/catalog.json">JSON</a> or <a href="data/catalog.csv">CSV</a>.</p>
</section>"""
    return layout("Catalog", body, "catalog.html")


def hero_svg(cards: dict, result_dirs: list[Path]) -> str:
    from references.ritter import depth_velocity

    x = np.linspace(400, 1600, 900)
    W_, H_ = 1100, 360
    px = lambda v: 40 + (np.asarray(v) - 400) / 1200 * (W_ - 80)  # noqa: E731
    py = lambda v: H_ - 60 - np.asarray(v) * (H_ - 110)  # noqa: E731
    parts = [f'<svg class="hero-svg" viewBox="0 0 {W_} {H_}" role="img" aria-label="Exact Ritter dam-break water surface at 0, 15, 30, 45 and 60 seconds, with the demo solver\'s computed depths at 60 seconds">']
    parts.append(f'<rect class="bed-fill" x="40" y="{py(0):.1f}" width="{W_ - 80}" height="22"/>')
    for k, t in enumerate([0, 15, 30, 45, 60]):
        h = depth_velocity(x, float(t), h0=1.0, x0=1000.0)["h"]
        pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px(x), py(h)))
        parts.append(f'<polygon class="hero-water hw{k}" points="{px(x[0]):.1f},{py(0):.1f} {pts} {px(x[-1]):.1f},{py(0):.1f}"/>')
        parts.append(f'<polyline class="hero-line hl{k}" style="--i:{k}" points="{pts}"/>')
        xf = 1000 + 2 * t * np.sqrt(9.81) if t else 1000
        parts.append(f'<text class="hero-t" x="{px(min(xf, 1590)) + 6:.1f}" y="{py(0) - 8:.1f}">{t} s</text>')
    demo = _demo_profile("A1F-010_ritter_dry_bed_dambreak", result_dirs)
    if demo is not None:
        sel = demo[(demo["x"] >= 400) & (demo["x"] <= 1600)]
        sel = sel.iloc[:: max(1, len(sel) // 70)]
        for a, b in zip(px(sel["x"]), py(sel["h"])):
            parts.append(f'<circle class="hero-dot" cx="{a:.1f}" cy="{b:.1f}" r="3.4"/>')
    parts.append(f'<line class="hero-gate" x1="{px(1000):.1f}" x2="{px(1000):.1f}" y1="{py(1.08):.1f}" y2="{py(0):.1f}"/>')
    parts.append(f'<text class="hero-cap" x="{px(1000) + 8:.1f}" y="{py(1.04):.1f}">dam, removed at t = 0</text>')
    parts.append("</svg>")
    return "".join(parts)


def index_page(manifests: list[dict], cards: dict, census: pd.DataFrame | None, result_dirs: list[Path]) -> str:
    status_rows = []
    for code, name, _ in COMPONENTS:
        ms = [m for m in manifests if m["_component"] == code]
        c = Counter(m["status"] for m in ms)
        status_rows.append((name, [(c.get("frozen", 0), "st-frozen", "Frozen"), (c.get("candidate", 0), "st-candidate", "Candidate"), (c.get("draft", 0), "st-draft", "Draft")]))
    bars = hbars("Cases by component and status", status_rows, link={name: f"catalog.html#{code}" for code, name, _ in COMPONENTS})
    scored = [cards[m["test_id"]] for m in manifests if m["test_id"] in cards]
    scored_rows = "".join(
        f'<tr><td><a href="{page_name(c["test_id"])}">{esc(short_id(c["test_id"]))}</a></td><td>{esc(next(m.get("title", "") for m in manifests if m["test_id"] == c["test_id"]))}</td>'
        f'<td>{esc(c["solver"]["name"].split(" (")[0])}</td><td>{verdict(c)}</td>'
        f'<td class=num>{fmt(c["convergence_result"]["observed_order"]) if c.get("convergence_result") and c["convergence_result"].get("observed_order") is not None else "–"}</td></tr>'
        for c in scored
    )
    n_ran = int((census["status"] == "ran").sum()) if census is not None else 0
    n_models = len(census) if census is not None else 0
    corpus_block = (
        f"""<section>
  <h2>Track B corpus</h2>
  <p>{n_models:,} SWMM models federated from HydroCouple's <code>openswmm.engine.benchmarks</code>, pinned to one commit. {n_ran:,} of them run cleanly on EPA SWMM 5.2.4; those form the nightly and release tiers. <a href="corpus.html">Explore the corpus</a>.</p>
</section>"""
        if census is not None
        else ""
    )
    ritter = cards.get("A1F-010_ritter_dry_bed_dambreak")
    ritter_line = ""
    if ritter:
        front = next((r for r in ritter["criteria_results"] if r["id"] == "front_position"), None)
        if front:
            ritter_line = f"The dots are the demo solver: its wet front sits {front['observed']:.2f} m from the exact one after 60 s, inside the 2.5 m tolerance."
    body = f"""
<section class="hero">
  <div class="hero-copy">
    <h1>Is your water solver right, and does it match SWMM?</h1>
    <p class="lede">Benchmark1d2d is an open suite that answers those as two separate questions, for 1D, 2D and coupled hydraulic models written in any language, including neural surrogates.</p>
    <p class="cta"><a class="button" href="catalog.html">Browse the {len(manifests)} test cases</a> <a class="button ghost" href="get-started.html">Score your solver</a></p>
  </div>
  <figure class="hero-fig">{hero_svg(cards, result_dirs)}
    <figcaption>Ritter (1892): a dam holding 1 m of water vanishes at t = 0. Shaded profiles are the exact solution every 15 s. {esc(ritter_line)} <a href="{page_name('A1F-010')}">See test A1F-010</a>.</figcaption>
  </figure>
</section>
<section class="tracks">
  <h2>Two tracks, kept apart on purpose</h2>
  <div class="table-scroll"><table class="data compare">
    <thead><tr><th></th><th class="track-a">Track A — physics</th><th class="track-b">Track B — industry parity</th></tr></thead>
    <tbody>
      <tr><th>Question</th><td>Does it solve the equations correctly?</td><td>Does it behave like EPA SWMM 5.2.4 and EPANET 2.2?</td></tr>
      <tr><th>Ground truth</th><td>Exact solutions, conservation laws, laboratory and field measurements</td><td>Element-by-element output of the pinned engine on the same input</td></tr>
      <tr><th>A failure means</th><td>The solver is <b>wrong</b></td><td>The solver <b>differs</b> from the reference engine</td></tr>
      <tr><th>Scored on</th><td>L1/L2/L∞ error, observed order of accuracy, mass error, arrival time</td><td>Peak, volume and timing at every node and link; the worst element is reported</td></tr>
      <tr><th>Claims</th><td>A-V verified, A-C conserves, A-L / A-F validated</td><td>B-x %: within x % of the reference everywhere</td></tr>
    </tbody>
  </table></div>
</section>
<section>
  <h2>Where the catalog stands</h2>
  <p>Only <b>frozen</b> cases count toward certification. Drafts are listed so you can see what is coming and what is blocked, usually on data licences.</p>
  {bars}
  {legend([("Frozen", "st-frozen"), ("Candidate", "st-candidate"), ("Draft", "st-draft")])}
</section>
<section>
  <h2>Latest scored runs</h2>
  <p>These runs use the demo solvers shipped in <code>examples/</code>: deliberately plain first- and second-order schemes that show the scoring at work. They are not certification claims for any product.</p>
  <div class="table-scroll"><table class="data"><thead><tr><th>Case</th><th>Title</th><th>Solver</th><th>Result</th><th class=num>Observed order</th></tr></thead><tbody>{scored_rows}</tbody></table></div>
  <p><a href="reports.html">All score cards and the audit log</a></p>
</section>
{corpus_block}"""
    return layout("Open V&V benchmarks for water solvers", body, "index.html")


def corpus_page(index: pd.DataFrame | None, census: pd.DataFrame | None) -> str:
    if index is None or census is None:
        return layout("Track B corpus", "<header class=page-head><h1>Track B corpus</h1><p class=lede>The corpus census has not been run yet.</p></header>", "corpus.html")
    st = index["status"].value_counts()
    status_css = {"ran": "st-frozen", "input_error": "st-fail", "engine_error": "st-fail", "timeout": "st-draft", "not_run": "st-draft"}
    status_names = {"ran": "Ran cleanly", "input_error": "Input error", "engine_error": "Engine error", "timeout": "Timed out (90 s)", "not_run": "Not run"}
    bars = hbars("Census outcome on EPA SWMM 5.2.4", [(status_names.get(k, k), [(int(v), status_css.get(k, "st-draft"), status_names.get(k, k))]) for k, v in st.items()], unit=" models")
    rt = index["runtime_s"].dropna()
    edges = np.array([0, 0.1, 0.3, 1, 3, 10, 30, 90.01])
    hist, _ = np.histogram(rt.clip(upper=90), bins=edges)
    labels = ["< 0.1 s", "0.1–0.3 s", "0.3–1 s", "1–3 s", "3–10 s", "10–30 s", "30–90 s"]
    rt_bars = hbars("Runtime on SWMM 5.2.4 (one CPU core)", [(lab, [(int(n), "st-candidate", lab)]) for lab, n in zip(labels, hist)], unit=" models")
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
<section><h2>Does each model run on the reference engine?</h2>{bars}
<p>A model joins a tier only if it runs cleanly. {int(st.get('input_error', 0)) + int(st.get('engine_error', 0))} models stop with input or engine errors and {int(st.get('timeout', 0))} exceed the 90 s census limit; they stay in the index so the upstream maintainers can see them.</p></section>
<section><h2>Tiers</h2>
<div class="table-scroll"><table class="data"><thead><tr><th>Tier</th><th class=num>Models</th><th>Selection rule</th><th>Download</th></tr></thead><tbody>
<tr><td>PR</td><td class=num>{int(tiers.get('tier_pr', 0))} + 3 catalog cases</td><td>Runs in ≤ 5 s, includes at least five control-rule models, gates every pull request</td><td><a href="data/track_b/tier_pr.json">selection.json</a></td></tr>
<tr><td>Nightly</td><td class=num>{int(tiers.get('tier_nightly', 0)) + int(tiers.get('tier_pr', 0))}</td><td>Runs in ≤ 10 s, picked greedily so every tag is covered</td><td><a href="data/track_b/tier_nightly.json">selection.json</a></td></tr>
<tr><td>Release</td><td class=num>{int((index['tier'] != 'none').sum())}</td><td>Every model that runs and has a verified licence</td><td><a href="data/track_b/tier_release.json">selection.json</a></td></tr>
</tbody></table></div></section>
<section><h2>Runtime</h2>{rt_bars}</section>
<section><h2>What the tiers cover</h2>{tag_bars}{legend([("PR", "st-frozen"), ("Nightly", "st-candidate"), ("Release only", "st-release"), ("Not in a tier", "st-draft")])}</section>
<section><h2>Largest routing continuity errors on SWMM 5.2.4</h2>
<p>Continuity error is SWMM's own mass-balance check. These models are kept in the release tier only if they run; a large error here is a property of the model or engine, and parity is still judged against it.</p>
<div class="table-scroll"><table class="data"><thead><tr><th>Model</th><th class=num>Routing continuity</th><th class=num>Runtime</th></tr></thead><tbody>{worst_rows}</tbody></table></div>
<p class="small">Median absolute routing continuity error across models that ran: {cont.median():.3f} %.</p></section>
<section><h2>Data</h2><p>Download the full index as <a href="data/track_b/corpus_index.csv">CSV</a> or <a href="data/track_b/corpus_index.parquet">Parquet</a>. Fetch models with <code>python scripts/fetch_track_b_models.py --tier nightly</code>; every file is checked against its hash.</p></section>"""
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
    ("Every pass was labelled A-V", "Validation and parity passes received verification or fixed B-1 % claims.",
     "Claims follow the case class (A-V, A-C, A-L, A-F) and the gating tolerance (B-x %)."),
]


def reports_page(manifests: list[dict], cards: dict) -> str:
    rows = []
    for m in manifests:
        c = cards.get(m["test_id"])
        if not c:
            continue
        conv = c.get("convergence_result") or {}
        rows.append(
            f'<tr><td><a href="{page_name(m["test_id"])}">{esc(short_id(m["test_id"]))}</a></td><td>{esc(c["solver"]["name"])}</td><td>{verdict(c)}</td>'
            f'<td>{esc(", ".join(c.get("certification_claims") or []) or "–")}</td>'
            f'<td class=num>{fmt(conv["observed_order"]) if conv.get("observed_order") is not None else "–"}</td>'
            f'<td><code title="{esc(c.get("content_hash", ""))}">{esc(c.get("content_hash", "")[:12])}…</code></td>'
            f'<td><a href="data/scorecards/{esc(c["_path"].name)}" download>JSON</a></td></tr>'
        )
    audit = "".join(f"<li><h3>{esc(t)}</h3><p><b>Found:</b> {esc(a)}</p><p><b>Now:</b> {esc(b)}</p></li>" for t, a, b in AUDIT)
    body = f"""
<header class="page-head"><h1>Reports</h1>
<p class="lede">Every score card is canonical JSON with a SHA-256 content hash and an Ed25519 signature, so a published result can be checked byte for byte.</p></header>
<section><h2>Score cards</h2>
<div class="table-scroll"><table class="data"><thead><tr><th>Case</th><th>Solver</th><th>Result</th><th>Claims</th><th class=num>Observed order</th><th>Content hash</th><th>File</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="small"><a href="data/scorecards.zip" download>Download every score card (.zip)</a>. Verify one with <code>benchmark1d2d verify path/to/card.json</code>.</p></section>
<section><h2>Audit log, 13 October 2026</h2>
<p>An end-to-end review found the following defects. Each is fixed, covered by tests, and recorded here because earlier results published from this repository were affected.</p>
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
            f'<td><code title="{esc(sha256(p))}">{esc(sha256(p)[:16])}…</code></td></tr>'
            for label, p in items
        )
        sections.append(f'<section><h2>{esc(g)}</h2><div class="table-scroll"><table class="data"><thead><tr><th>File</th><th class=num>Size</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    body = f"""<header class="page-head"><h1>Downloads</h1>
<p class="lede">Everything the site shows, as files. Hashes let you confirm a download matches what CI built.</p></header>
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
        if p.is_file() and p.name != ".gitkeep" and p.relative_to(d).as_posix() not in skip and "__pycache__" not in p.parts:
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
                for p in committed_files(m):
                    rel = p.relative_to(m["_case_dir"])
                    (cdir / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, cdir / rel)
                    z.write(p, f"{m['test_id']}/{rel.as_posix()}")
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
                        "" if c is None else ("pass" if c["passed"] else "fail")])
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
    return files


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorecards", action="append", default=[], help="directories with *.scorecard.json (later wins)")
    ap.add_argument("--results", action="append", default=[], help="directories with demo results Parquet")
    args = ap.parse_args()
    score_dirs = [Path(p) for p in (args.scorecards or ["site/fixtures/scorecards", "out/track_b", "out/vertical_slice", "out/demo_2d"])]
    result_dirs = [Path(p) for p in (args.results or ["out/vertical_slice", "out/demo_2d"])]
    score_dirs = [p if p.is_absolute() else ROOT / p for p in score_dirs]
    result_dirs = [p if p.is_absolute() else ROOT / p for p in result_dirs]

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "tests").mkdir(parents=True)
    assets = DIST / "assets"
    assets.mkdir()
    shutil.copytree(SITE / "static", DIST / "static")

    manifests = load_manifests()
    cards = load_scorecards(score_dirs)
    known = {m["test_id"] for m in manifests}
    cards = {k: v for k, v in cards.items() if k in known}
    idx_path = ROOT / "test_catalog/track_b/corpus_index.parquet"
    index = pd.read_parquet(idx_path) if idx_path.is_file() else None
    if index is not None and "status" not in index.columns:
        index = None
    census_path = ROOT / "test_catalog/track_b/corpus_census.parquet"
    census = pd.read_parquet(census_path) if census_path.is_file() else None

    files = write_bundles(manifests, cards, index)
    pages = {
        "index.html": index_page(manifests, cards, census, result_dirs),
        "catalog.html": catalog_page(manifests, cards),
        "corpus.html": corpus_page(index, census),
        "reports.html": reports_page(manifests, cards),
        "method.html": doc_page("Method", "method.html", [ROOT / "docs/methodology/vv_plan.md", ROOT / "docs/methodology/tolerance_rationale.md", ROOT / "docs/bibliography.md"],
                                '<p class="lede">How cases are verified and validated, how tolerances are chosen, and the literature behind every test.</p>'),
        "get-started.html": doc_page("Get started", "get-started.html", [ROOT / "docs/get_started.md"]),
    }
    for m in manifests:
        pages[page_name(m["test_id"])] = test_page(m, cards.get(m["test_id"]), result_dirs, assets)
    pages["downloads.html"] = downloads_page(files)
    for name, html_text in pages.items():
        (DIST / name).write_text(html_text, encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    print(f"site: {len(pages)} pages, {len(cards)} score cards, {len(files)} downloads -> {DIST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
