#!/usr/bin/env python3
"""Export the numbers the site's charts need from each model's results.

The site does not re-run the models, so every chart needs a small extract of
each model's results: a profile along the chart line (``site/profiles.py``),
or for the drainage, coupled and flood-gauge tests the few series their charts
use (``site/netcharts.py``). This script cuts those extracts from the results
under ``out/`` and writes one file per model and test,
``out/curves/<model>/<test>.curve.json``, holding the test's case version so an
extract from an older version of a test is never shown.

Every solver workflow runs it after scoring and uploads ``out/curves`` with
the score cards; the result collector files the extracts under
``site/fixtures/curves/<test>/<model>.json``, so the charts change when the
scores do.

Usage::

    python scripts/export_curves.py [--only KEY ...]    # write out/curves/
    python scripts/export_curves.py --local             # also file them in site/fixtures/curves/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "site")]

OUT = REPO / "out" / "curves"
FIXTURES = REPO / "site" / "fixtures" / "curves"

# results folder -> model key on the site (several folders may feed one key)
SOURCES = [
    ("telemac", "out/telemac"), ("anuga", "out/anuga"), ("geoclaw", "out/geoclaw"),
    ("lisflood-fv1", "out/lisflood/fv1"), ("lisflood-dg2", "out/lisflood/dg2"), ("lisflood-acc", "out/lisflood/acc"),
    ("swmm524", "out/swmm_track_a/swmm524"), ("openswmm-dw", "out/swmm_track_a/openswmm-dw"),
    ("openswmm-fv", "out/swmm_track_a/openswmm-fv"), ("hydra-uds", "out/swmm_track_a/hydra-uds"),
    ("hydronet-fvm", "out/hydronet/fvm"), ("hydronet-pinn", "out/hydronet/pinn"),
    ("hecras", "out/hecras"), ("hecras", "out/hecras2d/elm"), ("hecras-em", "out/hecras2d/em"),
    ("swmm-anuga", "out/coupled/swmm-anuga"),
    ("openswmm-2d", "out/coupled/openswmm-2d"), ("openswmm-2d-x", "out/coupled/openswmm-2d-x"),
]


def extracts_for(m: dict, folder: Path) -> dict | None:
    import netcharts
    import profiles

    sid = m["test_id"].split("_")[0]
    rec: dict = {}
    if sid in profiles.CHART:
        p = profiles.finest(folder, m["test_id"])
        if p is not None:
            try:
                c = profiles.model_curve(m, p)
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the export
                print(f"  {sid} {folder}: profile skipped ({exc})", file=sys.stderr)
                c = None
            if c:
                rec["profile"] = c
    if sid in netcharts.SIDS:
        try:
            d = netcharts.extract(m, folder)
        except Exception as exc:  # noqa: BLE001
            print(f"  {sid} {folder}: extract skipped ({exc})", file=sys.stderr)
            d = None
        if d:
            rec["net"] = d
    return rec or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="model keys to export (default: every folder that exists)")
    ap.add_argument("--local", action="store_true", help="also file the extracts in site/fixtures/curves/")
    args = ap.parse_args()

    from build import load_manifests  # type: ignore

    manifests = [m for m in load_manifests() if m["status"] != "draft"]
    n = 0
    for key, d in SOURCES:
        if args.only and key not in args.only:
            continue
        folder = REPO / d
        if not folder.is_dir():
            continue
        for m in manifests:
            rec = extracts_for(m, folder)
            if not rec:
                continue
            sid = m["test_id"].split("_")[0]
            doc = {"test_id": m["test_id"], "case_version": m["case_version"], "key": key, **rec}
            text = json.dumps(doc, separators=(",", ":")) + "\n"
            dest = OUT / key / f"{sid}.curve.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            if args.local:
                fx = FIXTURES / sid / f"{key}.json"
                fx.parent.mkdir(parents=True, exist_ok=True)
                fx.write_text(text, encoding="utf-8")
            n += 1
    print(f"exported {n} chart extracts to {OUT.relative_to(REPO)}" + (" and site/fixtures/curves" if args.local else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
