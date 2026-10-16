#!/usr/bin/env python3
"""Fetch and check the Bellinge EPA SWMM model (Pedersen et al. 2021, CC BY 4.0).

``fetch`` downloads item 7 (Models, SWMM) of the Bellinge data set from DTU
Data, checks the published MD5, records the SHA-256, unpacks it under
``<out>/model/`` and writes an inventory. ``run`` runs every ``.inp`` it
finds once in EPA SWMM 5.2.4 (swmm-toolkit) and records the run time and the
report's continuity errors.

DTU's file store is not reachable from the build sandbox, so this runs in CI
(``.github/workflows/bellinge.yml``).

Usage::

    python scripts/bellinge.py fetch --out out/bellinge
    python scripts/bellinge.py run --out out/bellinge [--timeout 3000]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

_RUN = (
    "import sys\n"
    "from swmm.toolkit import solver\n"
    "solver.swmm_run(sys.argv[1], sys.argv[2], sys.argv[3])\n"
)


def network_input() -> dict:
    from benchmark1d2d.catalog import load_manifest

    m = load_manifest("A1F-100", repo=REPO)
    return next(e for e in m["inputs"] if e["role"] == "network")


def fetch(out: Path) -> None:
    entry = network_input()
    url, md5_expected = entry["source"]["url"], entry["source"].get("md5")
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / Path(entry["path"]).name
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d (github.com/scott-jeffers/benchmark1d2d)"})
    with urllib.request.urlopen(req, timeout=600) as r, zpath.open("wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    data = zpath.read_bytes()
    md5, sha = hashlib.md5(data).hexdigest(), hashlib.sha256(data).hexdigest()
    info = {"url": url, "bytes": len(data), "md5": md5, "md5_expected": md5_expected,
            "md5_ok": (md5 == md5_expected) if md5_expected else None, "sha256": sha,
            "seconds": round(time.perf_counter() - t0, 1)}
    print(json.dumps(info, indent=1))
    if md5_expected and md5 != md5_expected:
        raise SystemExit("MD5 does not match the published value")
    dest = out / "model"
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
        lines = [f"{zi.file_size:>12,d}  {zi.filename}" for zi in z.infolist() if not zi.is_dir()]
    (out / "inventory.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    info["inp_files"] = sorted(str(p.relative_to(dest)) for p in dest.rglob("*.inp"))
    (out / "fetch.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    zpath.unlink()  # the archive itself is not needed once unpacked and hashed
    print(f"{len(lines)} files; .inp: {info['inp_files']}")


def continuity(rpt: Path) -> dict:
    text = rpt.read_text(encoding="latin-1", errors="replace") if rpt.is_file() else ""
    errs = re.findall(r"Continuity Error \(%\) \.+\s+(-?[\d.]+)", text)
    keys = ["runoff", "routing"] if len(errs) >= 2 else ["routing"]
    out = {k: float(v) for k, v in zip(keys, errs[-len(keys):])} if errs else {}
    m = re.search(r"Version\s+([\d.]+)", text)
    if m:
        out["version"] = m.group(1)
    return out


def run(out: Path, timeout: float) -> None:
    dest = out / "model"
    results = []
    for inp in sorted(dest.rglob("*.inp")):
        rpt, bin_ = inp.with_suffix(".rpt"), out / (inp.stem + ".out")
        t0 = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, "-c", _RUN, str(inp.resolve()), str(rpt.resolve()), str(bin_.resolve())], cwd=inp.parent,
                               capture_output=True, text=True, timeout=timeout)
            status = "ran" if p.returncode == 0 else f"exit {p.returncode}: {(p.stderr or p.stdout)[-300:]}"
        except subprocess.TimeoutExpired:
            status = f"timeout after {timeout:g} s"
        rec = {"inp": str(inp.relative_to(dest)), "status": status, "seconds": round(time.perf_counter() - t0, 1),
               "continuity_pct": continuity(rpt), "out_bytes": bin_.stat().st_size if bin_.is_file() else 0}
        if rpt.is_file():
            (out / (inp.stem + ".rpt")).write_text(rpt.read_text(encoding="latin-1", errors="replace"), encoding="utf-8")
        if bin_.is_file():
            bin_.unlink()  # large; the parity job re-runs it
        results.append(rec)
        print(json.dumps(rec))
    (out / "run.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")


def inventory(out: Path, role: str) -> None:
    """Download another Bellinge item (by its role in A1F-100's manifest), list it, and show the head of a few files."""
    from benchmark1d2d.catalog import load_manifest

    m = load_manifest("A1F-100", repo=REPO)
    entry = next(e for e in m["inputs"] if e["role"] == role)
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / Path(entry["path"]).name
    req = urllib.request.Request(entry["source"]["url"], headers={"User-Agent": "benchmark1d2d (github.com/scott-jeffers/benchmark1d2d)"})
    with urllib.request.urlopen(req, timeout=1800) as r, zpath.open("wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    data_hash = hashlib.sha256()
    with zpath.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            data_hash.update(chunk)
    lines = [f"{role}: {zpath.stat().st_size:,d} bytes, SHA-256 {data_hash.hexdigest()}"]
    with zipfile.ZipFile(zpath) as z:
        infos = [zi for zi in z.infolist() if not zi.is_dir()]
        lines += [f"{zi.file_size:>14,d}  {zi.filename}" for zi in infos]
        lines.append("")
        for zi in infos[:400]:
            if zi.filename.lower().endswith((".csv", ".txt", ".dat", ".json", ".md")) and zi.file_size:
                with z.open(zi) as fh:
                    head = fh.read(1500).decode("latin-1", "replace")
                lines += [f"==> {zi.filename}", head, ""]
    (out / f"inventory_{role}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:80]))


# Storms picked from the model's own rain-gauge series (rg5425): the most intense 10-minute
# rainfall and the largest daily totals after the level meters start (August 2010). The first is
# the event the published model is set up for.
EVENTS = ["2012-06-29", "2011-06-30", "2011-08-26", "2013-08-12", "2014-06-24", "2014-08-17", "2015-07-25", "2019-10-11"]


def extract(out: Path) -> None:
    """Measured levels at every level meter for two days from the start of each storm (CC BY 4.0, DTU Data item 2)."""
    import pandas as pd

    from benchmark1d2d.catalog import load_manifest

    m = load_manifest("A1F-100", repo=REPO)
    entry = next(e for e in m["inputs"] if e["role"] == "observations")
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / Path(entry["path"]).name
    if not zpath.is_file():
        req = urllib.request.Request(entry["source"]["url"], headers={"User-Agent": "benchmark1d2d (github.com/scott-jeffers/benchmark1d2d)"})
        with urllib.request.urlopen(req, timeout=1800) as r, zpath.open("wb") as fh:
            while chunk := r.read(1 << 20):
                fh.write(chunk)
    windows = [(pd.Timestamp(d), pd.Timestamp(d) + pd.Timedelta("2D")) for d in EVENTS]
    frames = []
    with zipfile.ZipFile(zpath) as z:
        for zi in z.infolist():
            name = Path(zi.filename).name
            if not name.endswith("_proc_v6.csv"):
                continue
            stem = name[: -len("_proc_v6.csv")]
            node = stem.split("_")[0].replace("p1", "")
            sensor = stem.rsplit("_", 1)[0]  # e.g. G71F04R_Level1
            source = stem.rsplit("_", 1)[1]  # iFixp1, System2000p1, Danovap1 ...
            with z.open(zi) as fh:
                for ch in pd.read_csv(fh, usecols=lambda c: c in ("time", "level", "depth_s"), chunksize=1_000_000):
                    t = pd.to_datetime(ch["time"])
                    keep = False
                    for a, b in windows:
                        keep = keep | ((t >= a) & (t < b))
                    if keep.any():
                        sel = ch[keep].copy()
                        sel["time"] = t[keep]
                        sel["node"], sel["sensor"], sel["source"] = node, sensor, source
                        frames.append(sel)
            print(f"  {name}: {sum(len(f) for f in frames if f['sensor'].iloc[0] == sensor and f['source'].iloc[0] == source)} rows in the event windows", flush=True)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["time", "level", "depth_s", "node", "sensor", "source"])
    df = df.dropna(subset=["level"]).sort_values(["sensor", "source", "time"])
    df["event"] = df["time"].dt.normalize()
    for d in EVENTS:  # label each row with its event
        df.loc[(df["time"] >= pd.Timestamp(d)) & (df["time"] < pd.Timestamp(d) + pd.Timedelta("2D")), "event"] = pd.Timestamp(d)
    df.to_csv(out / "levels_events.csv.gz", index=False, compression="gzip")
    cov = df.groupby(["event", "sensor", "source"]).size().unstack(["sensor", "source"]).fillna(0).astype(int)
    (out / "coverage.txt").write_text(cov.to_string() + "\n", encoding="utf-8")
    print(cov.to_string())


SENSOR_NODES = ["G71F04R", "G71F05R", "G71F06R", "G71F68Y", "G72F040", "G73F010", "G80F11B", "G80F13P", "G80F66Y"]


def scout(out: Path) -> None:
    """The model's set-up and the nodes around each level meter, and one SWMM 5.2.4 run of the June 2012 storm.

    Writes ``scout.txt`` (options, rain gauges, report section; every node whose
    name starts with a sensor's node name, with its invert, depth and the links
    touching it) and ``scout_heads.csv.gz`` (water level, invert + depth, at those
    nodes, every minute from 29 June to 1 July 2012).
    """
    from datetime import datetime

    import numpy as np
    import pandas as pd

    import run_bellinge as rb
    from benchmark1d2d.adapters.swmm5 import read_out

    fetch(out)
    model = out / "model" / "7_SWMM"
    inp = next(model.glob("*.inp"))
    text = inp.read_text(encoding="latin-1")
    sec = rb._sections(text)
    lines = [f"model: {inp.name}", ""]
    for name in ("OPTIONS", "RAINGAGES", "REPORT", "FILES", "EVAPORATION", "DWF", "INFLOWS"):
        rows = sec.get(name, [])
        lines += [f"[{name}] ({len(rows)} rows)"] + ["  " + " ".join(r) for r in rows[:30]] + [""]
    lines += ["section sizes: " + ", ".join(f"{k} {len(v)}" for k, v in sec.items()), ""]
    kinds = {}
    for k in ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS"):
        for r in sec.get(k, []):
            kinds[r[0]] = (k, r)
    links = []
    for k in ("CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS"):
        links += [(k, r) for r in sec.get(k, [])]
    near = sorted(n for n in kinds if any(n.startswith(p) for p in SENSOR_NODES))
    for n in near:
        k, r = kinds[n]
        lines.append(f"{n:<14} {k:<10} {' '.join(r[1:])}")
        for lk, lr in links:
            if n in lr[1:3]:
                lines.append(f"    {lk:<9} {' '.join(lr[:6])}")
    (out / "scout.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    ev = {"id": "2012-06-29", "start": "2012-06-28T12:00:00", "score_from": "2012-06-29T00:00:00", "end": "2012-07-01T00:00:00"}
    epoch = datetime.fromisoformat(ev["score_from"])
    series, version, secs = rb.run_event("swmm524", model, ev, epoch, 60, {n: n for n in near}, None, 7200)
    nodes = rb.node_table(text)
    frames = [pd.DataFrame({"time": epoch + pd.to_timedelta(t, unit="s"), "node": n, "depth": h, "head": h + nodes[n]["z"]})
              for n, (t, h) in series.items()]
    pd.concat(frames).to_csv(out / "scout_heads.csv.gz", index=False, compression="gzip")
    print(f"SWMM {version}: {secs:.0f} s; {len(series)} nodes written")


# level meter (sensor, as the data set names it) -> the model node it sits in. Each sits in that node by name,
# except the inlet meter at the G71F05R basin, which reads the inlet chamber (G71F05R_skyl). Not used: G71F04R
# Level1 (Level2 is the same basin with fuller records), G71F05R_position (a gate) and G71F68Yp1 (a pump).
GAUGES = {
    "G71F04R_Level2": "G71F04R",
    "G71F05R_LevelBasin": "G71F05R",
    "G71F05R_LevelInlet": "G71F05R_skyl",
    "G71F06R_LevelInlet": "G71F06R",
    "G71F68Y_LevelPS": "G71F68Y",
    "G73F010": "G73F010",
    "G80F13P_LevelPS": "G80F13P",
}
EPOCH = "2010-01-01T00:00:00"


def reference(levels: Path, dest: Path) -> None:
    """Build A1F-100's reference/levels.parquet from ``extract``'s levels_events.csv.gz.

    Columns: ``t`` (s from the test's epoch), ``gauge``, ``wse`` (measured level,
    m above DVR90, to the mm), ``event``, ``floor`` (the lowest level the gauge
    recorded in any event: the meters do not read below it, so the scorer reads
    the model the same way). Where a gauge has two sources in one event, the one
    with more records is used.
    """
    import pandas as pd

    d = pd.read_csv(levels, parse_dates=["time", "event"])
    d = d[d["sensor"].isin(GAUGES)]
    keep = d.groupby(["sensor", "event", "source"]).size().reset_index(name="n")
    keep = keep.sort_values("n").groupby(["sensor", "event"]).tail(1)
    d = d.merge(keep[["sensor", "event", "source"]], on=["sensor", "event", "source"])
    d = d[d.groupby(["sensor", "event"])["level"].transform("size") >= 0.9 * 2880]  # whole windows only
    floor = d.groupby("sensor")["level"].min()
    out = pd.DataFrame({
        "t": (d["time"] - pd.Timestamp(EPOCH)).dt.total_seconds().astype(float),
        "gauge": d["sensor"].astype(str),
        "wse": d["level"].round(3).astype(float),
        "event": d["event"].dt.strftime("%Y-%m-%d"),
        "floor": d["sensor"].map(floor).round(3).astype(float),
    }).sort_values(["gauge", "t"]).reset_index(drop=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest, index=False, compression="zstd")
    print(out.groupby(["event", "gauge"]).size().unstack().fillna(0).astype(int).to_string())
    print(f"{len(out)} rows -> {dest} ({dest.stat().st_size:,d} bytes)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=["fetch", "run", "inventory", "extract", "scout", "reference"])
    ap.add_argument("--role", default="observations", help="inventory: which A1F-100 input (observations, rainfall)")
    ap.add_argument("--out", type=Path, default=REPO / "out" / "bellinge")
    ap.add_argument("--timeout", type=float, default=3000)
    a = ap.parse_args()
    if a.action == "fetch":
        fetch(a.out)
    elif a.action == "run":
        run(a.out, a.timeout)
    elif a.action == "extract":
        extract(a.out)
    elif a.action == "scout":
        scout(a.out)
    elif a.action == "reference":
        reference(a.out / "levels_events.csv.gz", REPO / "test_catalog" / "track_a" / "1d_free_surface"
                  / "A1F-100_bellinge_urban_drainage" / "reference" / "levels.parquet")
    else:
        inventory(a.out, a.role)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
