#!/usr/bin/env python3
"""Run a test on the software owner's own machine, through the suite's workflow.

For software the suite cannot run (a commercial licence, a Windows-only
installer), the owner can register a GitHub self-hosted runner on a machine
that holds their licence and run ``owner-run.yml`` there. For each test this
script:

1. unpacks the test's download kit (the same zip the site offers: inputs,
   model files to start from, and the results sheets to fill in) into a work
   folder;
2. runs the owner's command (``OWNER_COMMAND``, with ``{test}``, ``{kit}``
   ``{results}`` and ``{repo}`` filled in; it runs in the kit folder), which builds and runs their model and fills
   in the sheets in ``{results}``;
3. scores the sheets with the suite's own scorer and writes a score card
   marked ``run_by: owner`` with the runner's name and the workflow run, so
   the site shows it as run on the owner's machine;
4. zips the model files the command left in ``{kit}/model`` and anything it
   wrote to ``{kit}/output``, so anyone with a licence can check the result.

The licence never leaves the owner's machine; the score card, the sheets and
the model files are uploaded as the workflow's artifacts and collected like any
other run. See ``docs/owner-runner.md``.

Usage::

    python scripts/run_owner.py --software NAME --version VERSION --organisation ORG TEST [TEST ...]
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO / "scripts")]
OUT = REPO / "out" / "owner"


def kit(sid: str, dest: Path) -> Path:
    """Unpack the test's download kit (built by the site, or from the catalog when the site is not built)."""
    zp = REPO / "site" / "dist" / "data" / "cases" / f"{sid}.zip"
    if not zp.is_file():
        subprocess.run([sys.executable, "site/build.py"], cwd=REPO, check=True, stdout=subprocess.DEVNULL)
    with zipfile.ZipFile(zp) as z:
        z.extractall(dest)
    return dest / sid


def zip_dir(src: Path, dest: Path) -> int:
    from export_inputs import zip_folder

    if not src.is_dir() or not any(src.rglob("*")):
        return 0
    return zip_folder(src, dest)


def main() -> int:
    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.clock import run_timestamp
    from benchmark1d2d.scoring.scorer import score_case
    from benchmark1d2d.signing import private_key

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tests", nargs="+")
    ap.add_argument("--software", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--organisation", required=True)
    ap.add_argument("--command", default=os.environ.get("OWNER_COMMAND", ""), help="defaults to OWNER_COMMAND")
    ap.add_argument("--settings", default=os.environ.get("OWNER_SETTINGS", ""), help="the settings used, in plain words")
    a = ap.parse_args()
    if not a.command:
        print("No command: set OWNER_COMMAND (or --command) to the command that runs your model on {kit} and fills in {results}.")
        return 2
    runner = f"{os.environ.get('RUNNER_NAME', 'local')} · run {os.environ.get('GITHUB_RUN_ID', '-')}"
    key = private_key()
    ts = run_timestamp()
    solver = {"name": f"{a.software} {a.version}", "version": a.version,
              "adapter": "run on the owner's machine" + (f"; settings: {a.settings}" if a.settings else ""),
              "submitted_by": a.organisation, "run_by": "owner", "runner": runner, "model_files": False}
    bad = 0
    for sid in a.tests:
        m = load_manifest(sid, repo=REPO)
        with tempfile.TemporaryDirectory() as tdn:
            k = kit(sid, Path(tdn))
            results = k / "results"
            (k / "output").mkdir(exist_ok=True)
            cmd = a.command.format(test=sid, kit=shlex.quote(str(k)), results=shlex.quote(str(results)), repo=shlex.quote(str(REPO)))
            print(f"== {sid}: {cmd}", flush=True)
            t0 = time.perf_counter()
            p = subprocess.run(cmd, shell=True, cwd=k)
            wall = time.perf_counter() - t0
            if p.returncode != 0:
                print(f"   {sid}: the command failed ({p.returncode})")
                bad += 1
                continue
            sheets = sorted(results.glob(f"{sid}_dx*.csv"), key=lambda f: -float(f.stem.split("_dx")[1])) or sorted(results.glob(f"{sid}.csv"))
            if not sheets:
                print(f"   {sid}: no results sheets in {results}")
                bad += 1
                continue
            out = OUT / sid
            out.mkdir(parents=True, exist_ok=True)
            files_in = zip_dir(k / "model", out / f"{sid}.{slug(a.software)}.inputs.zip")
            files_out = zip_dir(k / "output", out / f"{sid}.{slug(a.software)}.outputs.zip")
            try:
                card = score_case(m, sheets[-1], refinement_results=sheets if len(sheets) > 1 else None, timestamp=ts, private_key=key,
                                  solver={**solver, "model_files": bool(files_in)})
            except Exception as exc:  # noqa: BLE001 - sheets that cannot be scored are the owner's to fix
                print(f"   {sid}: could not score ({type(exc).__name__}: {exc})")
                bad += 1
                continue
            card.setdefault("run", {})["wall_seconds"] = round(wall, 3)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            for f in sheets:
                (out / f.name).write_bytes(f.read_bytes())
            print(f"   {sid}: scored ({len(sheets)} grid(s)); model files {'kept' if files_in else 'not found in model/'}; outputs {'kept' if files_out else 'none in output/'}")
    return 1 if bad else 0


def slug(s: str) -> str:
    import re

    return "owner-" + re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


if __name__ == "__main__":
    raise SystemExit(main())
