#!/usr/bin/env python3
"""Report solver releases newer than the versions the suite pins.

Every solver the suite runs is pinned (a package version, a release asset with
a checksum, or a commit). This script asks each upstream for its latest
release and prints a Markdown table of pinned against latest; the
check-versions workflow keeps one open issue up to date with it, so a new
release is rerun on purpose rather than picked up silently.

Usage::

    python scripts/check_versions.py [--out out/versions.md]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# name, pinned version, where it is pinned, how to ask for the latest
PINS = [
    ("EPA SWMM (swmm-toolkit)", "0.17.0", "pyproject.toml", ("pypi", "swmm-toolkit")),
    ("EPANET (WNTR)", "1.5.0", "pyproject.toml", ("pypi", "wntr")),
    ("OpenSWMM Engine (openswmm)", "6.0.0a4.dev1", "workflows", ("pypi-pre", "openswmm")),
    ("ANUGA", "4.0.1", "open-solvers.yml", ("conda", "anuga")),
    ("openTELEMAC", "v9.1.1", "track-a.yml", ("conda", "opentelemac")),
    ("GeoClaw (Clawpack)", "v5.9.2", "open-solvers.yml", ("github-tags", "clawpack/clawpack")),
    ("LISFLOOD-FP", "8.3", "open-solvers.yml (Zenodo 13121119)", ("zenodo", "13121119")),
    ("HEC-RAS 6.6 (hec-downloads release)", "1.0.33", "hecras.yml", ("github-release", "HydrologicEngineeringCenter/hec-downloads")),
    ("Hydra CLI", "cli-v4.1.1", "scripts/fetch_hydra.py", ("github-tags-prefix", "neeraip/hydra", "cli-v")),
    ("HydroNet", "0d98ff5", "open-solvers.yml, slow-runs.yml", ("git-head", "https://github.com/psu-efd/HydroNet")),
    ("pyHMT2D", "57645ff", "open-solvers.yml, slow-runs.yml", ("git-head", "https://github.com/psu-efd/pyHMT2D")),
]


def _json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d-check-versions", "Accept": "application/json"})
    import os

    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _vkey(v: str):
    from packaging.version import InvalidVersion, Version

    try:
        return (1, Version(v.lstrip("v")))
    except InvalidVersion:
        return (0, v)


def latest(kind: tuple) -> str:
    k = kind[0]
    if k == "pypi":
        return _json(f"https://pypi.org/pypi/{kind[1]}/json")["info"]["version"]
    if k == "pypi-pre":
        rel = _json(f"https://pypi.org/pypi/{kind[1]}/json")["releases"]
        return max((v for v, files in rel.items() if files), key=_vkey)
    if k == "conda":
        return _json(f"https://api.anaconda.org/package/conda-forge/{kind[1]}")["latest_version"]
    if k == "zenodo":
        rec = _json(f"https://zenodo.org/api/records/{kind[1]}/versions/latest")
        return str(rec.get("metadata", {}).get("version") or rec.get("id"))
    if k == "github-release":
        return _json(f"https://api.github.com/repos/{kind[1]}/releases/latest")["tag_name"]
    if k in ("github-tags", "github-tags-prefix"):
        tags = [t["name"] for t in _json(f"https://api.github.com/repos/{kind[1]}/tags?per_page=100")]
        if k == "github-tags-prefix":
            tags = [t for t in tags if t.startswith(kind[2])]
        else:
            tags = [t for t in tags if re.match(r"^v?\d+(\.\d+)+$", t)]
        return max(tags, key=lambda t: _vkey(t.split("-v")[-1])) if tags else "?"
    if k == "git-head":
        out = subprocess.run(["git", "ls-remote", kind[1], "HEAD"], capture_output=True, text=True, timeout=60).stdout
        return out.split()[0][:7] if out else "?"
    raise ValueError(k)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=REPO / "out" / "versions.md")
    args = ap.parse_args()
    rows, newer = [], 0
    for name, pinned, where, kind in PINS:
        try:
            lat = latest(kind)
        except Exception as exc:  # noqa: BLE001 — report and continue
            lat = f"? ({type(exc).__name__})"
        p, l = pinned.split(" ")[0], lat
        same = p.lstrip("v").removeprefix("cli-v") == l.lstrip("v").removeprefix("cli-v") or l.startswith("?")
        newer += not same
        rows.append(f"| {name} | `{pinned}` | `{lat}` | {'' if same else '**newer**'} | {where} |")
    md = ["# Solver versions", "", "| Solver | Pinned | Latest upstream | | Pinned in |", "|---|---|---|---|---|", *rows, "",
          f"{newer} solver(s) have a newer upstream release. Update the pin, rerun the solver's workflow and review "
          "the collected results before publishing."]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(md) + "\n", encoding="utf-8")
    args.out.with_suffix(".newer").write_text(str(newer), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
