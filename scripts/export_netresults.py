#!/usr/bin/env python3
"""Export each model's per-element results on the SWMM and EPANET tests, for the network viewer.

For every score card of a network test under the result folders, the model's
results file next to it is cut down by ``site/netresults.py`` (node and link
series, at most 288 times) and written to
``out/netres/<model>/<test>.netres.json`` with the test's case version. The
solver workflows run this after scoring and upload ``out/netres``; the result
collector files the extracts under ``site/fixtures/netres/<test>/<model>.json``.

Usage::

    python scripts/export_netresults.py            # write out/netres/
    python scripts/export_netresults.py --local    # also file them in site/fixtures/netres/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "site")]

OUT = REPO / "out" / "netres"
FIXTURES = REPO / "site" / "fixtures" / "netres"
FOLDERS = ["out/track_b", "out/hydra", "out/openswmm", "out/networks", "out/hydra_networks",
           "out/swmm_track_a/swmm524", "out/swmm_track_a/openswmm-dw", "out/swmm_track_a/openswmm-fv", "out/swmm_track_a/hydra-uds"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--local", action="store_true", help="also file the extracts in site/fixtures/netres/")
    ap.add_argument("--folders", nargs="*", default=FOLDERS)
    args = ap.parse_args()

    import netresults
    import pages
    from build import load_manifests  # type: ignore

    ms = {netresults.sid_of(m["test_id"]): m for m in load_manifests() if netresults.sid_of(m["test_id"]) in netresults.NETWORK_TESTS}
    n = 0
    for d in args.folders:
        folder = REPO / d
        if not folder.is_dir():
            continue
        for card_path in sorted(folder.glob("*.scorecard.json")):
            card = json.loads(card_path.read_text(encoding="utf-8"))
            sid = netresults.sid_of(card["test_id"])
            m = ms.get(sid)
            if m is None or card.get("case_version") != m["case_version"]:
                continue
            key = pages.solver_key(card["solver"]["name"])
            tid = card["test_id"]
            pq = folder / f"{tid}.parquet"
            if not pq.is_file():
                pq = next(iter(sorted(folder.glob(f"{tid}.*.parquet"))), None)
            if key is None or pq is None:
                continue
            case_inp = next((Path(m["_case_dir"]) / e["path"] for e in m.get("inputs", []) if str(e.get("path", "")).endswith(".inp")), None)
            text = case_inp.read_text(encoding="latin-1") if case_inp and case_inp.is_file() else ""
            try:
                rec = netresults.extract(m, pq, folder / f"{tid}.series.json", text)
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the export
                print(f"  {sid} {key}: skipped ({exc})", file=sys.stderr)
                continue
            if not rec:
                continue
            doc = {"test_id": tid, "case_version": m["case_version"], "key": key, **rec}
            text_out = json.dumps(doc, separators=(",", ":")) + "\n"
            dest = OUT / key / f"{sid}.netres.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text_out, encoding="utf-8")
            if args.local:
                fx = FIXTURES / sid / f"{key}.json"
                fx.parent.mkdir(parents=True, exist_ok=True)
                fx.write_text(text_out, encoding="utf-8")
            n += 1
            print(f"  {sid} {key}: {len(rec['t'])} times, {len(rec['nodes'])} nodes, {len(rec['links'])} links ({len(text_out) // 1024} KB)")
    print(f"exported {n} network extracts to {OUT.relative_to(REPO)}" + (" and site/fixtures/netres" if args.local else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
