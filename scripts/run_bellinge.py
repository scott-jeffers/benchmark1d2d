#!/usr/bin/env python3
"""Score SWMM engines on A1F-100, the Bellinge field case (Track A, measured levels).

The published Bellinge EPA SWMM model (Pedersen et al. 2021, CC BY 4.0) is run
once per storm listed in the test's ``simulation.events``: a copy of the
model folder with the run dates set to the event's window (a warm-up, then
the scored window) and a one-minute report step. The model's own rain-gauge
file covers 2010-2021, so no rainfall is changed. Each run's node depths at
the level-meter nodes are written to the results contract with ``t`` in
seconds from the test's epoch and the node's invert as ``z``, so the runs
concatenate into one results file and the scorer compares each gauge's
measured water level (``wse`` = ``h`` + ``z``) with the model's.

Engines (each with its own defaults, as the model is published):

* ``swmm524``      EPA SWMM 5.2.4 (``swmm-toolkit`` 0.17.0), this interpreter
* ``openswmm-dw``  OpenSWMM Engine v6, dynamic wave (``--openswmm-python``)
* ``openswmm-fv``  OpenSWMM Engine v6, its finite-volume routing
* ``hydra-uds``    NEER AI Hydra, urban-drainage engine (``--hydra-exe``)

The model folder comes from ``scripts/bellinge.py fetch`` (DTU's file store
is reachable from CI, not from every machine).

Usage::

    python scripts/bellinge.py fetch --out out/bellinge
    python scripts/run_bellinge.py --model-dir out/bellinge/model/7_SWMM --engines swmm524
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO / "scripts")]

OUT = REPO / "out" / "bellinge_track_a"
TS = "2026-01-01T00:00:00Z"
TEST = "A1F-100"
ENGINES = {
    "swmm524": {"label": "EPA SWMM 5.2.4", "engine": "toolkit", "routing": None},
    "openswmm-dw": {"label": "OpenSWMM Engine v6 dynamic wave", "engine": "openswmm", "routing": None},
    "openswmm-fv": {"label": "OpenSWMM Engine v6 finite volume", "engine": "openswmm", "routing": "FV"},
    "hydra-uds": {"label": "Hydra urban drainage", "engine": "hydra", "routing": None},
}


def _sections(text: str) -> dict[str, list[list[str]]]:
    """Data rows of each [SECTION], comments and blank lines dropped."""
    out: dict[str, list[list[str]]] = {}
    cur = None
    for line in text.splitlines():
        s = line.split(";", 1)[0].strip()
        if not s:
            continue
        if s.startswith("["):
            cur = s.strip("[]").upper()
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(s.split())
    return out


def node_table(text: str) -> dict[str, dict]:
    """Invert elevation and map coordinates of every node."""
    sec = _sections(text)
    nodes: dict[str, dict] = {}
    for name in ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS"):
        for r in sec.get(name, []):
            nodes[r[0]] = {"z": float(r[1])}
    for r in sec.get("COORDINATES", []):
        if r[0] in nodes:
            nodes[r[0]].update(x=float(r[1]), y=float(r[2]))
    return nodes


def set_window(text: str, start: datetime, report: datetime, end: datetime, step_s: int) -> str:
    vals = {
        "START_DATE": start.strftime("%m/%d/%Y"), "START_TIME": start.strftime("%H:%M:%S"),
        "REPORT_START_DATE": report.strftime("%m/%d/%Y"), "REPORT_START_TIME": report.strftime("%H:%M:%S"),
        "END_DATE": end.strftime("%m/%d/%Y"), "END_TIME": end.strftime("%H:%M:%S"),
        "REPORT_STEP": time.strftime("%H:%M:%S", time.gmtime(step_s)),
    }
    for k, v in vals.items():
        pat = re.compile(rf"(?im)^(\s*{k}\s+)\S+")
        if pat.search(text):
            text = pat.sub(lambda m, v=v: m.group(1) + v, text, count=1)
        else:
            text = re.sub(r"(?im)^\[OPTIONS\]\s*$", lambda m, k=k, v=v: f"[OPTIONS]\n{k:<21}{v}", text, count=1)
    # report every node (the level meters must be in the binary output)
    if re.search(r"(?im)^\[REPORT\]", text):
        text = re.sub(r"(?im)^(\s*NODES\s+).*$", r"\1ALL", text)
        if not re.search(r"(?im)^\s*NODES\s+ALL", text):
            text = re.sub(r"(?im)^\[REPORT\]\s*$", "[REPORT]\nNODES ALL", text, count=1)
    else:
        text += "\n[REPORT]\nNODES ALL\n"
    return text


def run_event(engine: str, model_dir: Path, ev: dict, epoch: datetime, step_s: int, probes: dict[str, str],
              cand_python: str | None, timeout: float) -> tuple[dict, str, float]:
    import corpus_parity as cp

    from benchmark1d2d import keep as kept
    from benchmark1d2d.adapters.swmm5 import read_out

    spec = ENGINES[engine]
    start, end = datetime.fromisoformat(ev["start"]), datetime.fromisoformat(ev["end"])
    report = datetime.fromisoformat(ev.get("score_from", ev["start"]))
    with tempfile.TemporaryDirectory() as tdn:
        td = Path(tdn)
        folder = td / "model"
        shutil.copytree(model_dir, folder, ignore=shutil.ignore_patterns("*.out", "*.rpt"))
        inp = next(folder.glob("*.inp"))
        text = inp.read_text(encoding="latin-1")
        inp.write_text(set_window(text, start, report, end, step_s), encoding="latin-1")
        kept.inputs(engine, TEST, folder, ev["id"], files=[p.name for p in folder.iterdir() if p.is_file()])
        if spec["routing"]:
            inp, _ = cp.with_routing(inp, spec["routing"], td)
        python = sys.executable if spec["engine"] == "toolkit" else cand_python
        t0 = time.perf_counter()
        out, _, version = cp._run(python, inp.resolve(), td, ev["id"], timeout, spec["engine"])
        secs = time.perf_counter() - t0
        data = read_out(out)
    off = (report - epoch).total_seconds()
    series = {}
    for node in probes.values():
        if node not in data["nodes"]:
            raise RuntimeError(f"node {node} is not in the {engine} output")
        series[node] = (data["t"] + off, data["nodes"][node])
    return series, version, secs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", type=Path, required=True, help="the unpacked 7_SWMM folder (.inp and rain .dat)")
    ap.add_argument("--engines", nargs="+", choices=list(ENGINES), default=["swmm524"])
    ap.add_argument("--openswmm-python", help="Python with the openswmm wheel")
    ap.add_argument("--hydra-exe", help="the hydra CLI (NEER AI Hydra)")
    ap.add_argument("--events", nargs="*", help="only these event ids (default: all in the manifest)")
    ap.add_argument("--timeout", type=float, default=5400)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    m = load_manifest(TEST, repo=REPO)
    sim = m["simulation"]
    epoch = datetime.fromisoformat(sim["epoch"])
    step_s = int(sim["output_interval"])
    probes = {p["id"]: p["element"] for p in sim["probes"]}
    events = [e for e in sim["events"] if not args.events or e["id"] in args.events]
    model_dir = args.model_dir.resolve()
    nodes = node_table(next(model_dir.glob("*.inp")).read_text(encoding="latin-1"))
    for engine in args.engines:
        cand = args.hydra_exe if engine == "hydra-uds" else args.openswmm_python
        if ENGINES[engine]["engine"] != "toolkit" and not cand:
            print(f"skip {engine}: no {'--hydra-exe' if engine == 'hydra-uds' else '--openswmm-python'}")
            continue
        cols: dict[str, list] = {k: [] for k in ("t", "x", "y", "h", "u", "v", "p", "z", "element_id", "element_type")}
        version, runs = "", []
        try:
            for ev in events:
                series, version, secs = run_event(engine, model_dir, ev, epoch, step_s, probes, cand, args.timeout)
                runs.append({"event": ev["id"], "seconds": round(secs, 1)})
                print(f"  {engine} {ev['id']}: {secs:.0f} s", flush=True)
                for node, (t, h) in series.items():
                    n = len(t)
                    nd = nodes.get(node, {})
                    cols["t"].append(t); cols["h"].append(h)
                    cols["x"].append(np.full(n, nd.get("x", np.nan))); cols["y"].append(np.full(n, nd.get("y", np.nan)))
                    cols["z"].append(np.full(n, nd.get("z", np.nan)))
                    for c in ("u", "v", "p"):
                        cols[c].append(np.full(n, np.nan))
                    cols["element_id"].append([node] * n); cols["element_type"].append(["node"] * n)
        except Exception as exc:  # noqa: BLE001 - an engine that cannot run the model is a finding
            print(f"  {engine}: did not run: {str(exc)[-600:]}")
            continue
        out = args.out / engine
        out.mkdir(parents=True, exist_ok=True)
        flat = {k: np.concatenate([np.asarray(a, dtype=object if k.startswith("element") else float) for a in v]) for k, v in cols.items()}
        path = write_results_parquet(out / f"{m['test_id']}.parquet", flat)
        ver = (version or "").replace("openswmm", "").strip()
        solver = {"name": ENGINES[engine]["label"] + (f" ({ver})" if engine != "swmm524" else ""), "version": ver,
                  "adapter": "swmm (the published Bellinge model, run dates set per event)"}
        card = score_case(m, path, timestamp=TS, private_key=key, solver=solver)
        (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        (out / "runs.json").write_text(json.dumps(runs, indent=1) + "\n", encoding="utf-8")
        print(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}  {r.get('detail', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
