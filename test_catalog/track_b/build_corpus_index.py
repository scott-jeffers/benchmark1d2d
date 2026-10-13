#!/usr/bin/env python3
"""Build the Track B corpus index and tier selections from HydroCouple.

Reads a checkout of HydroCouple ``openswmm.engine.benchmarks`` (tags from each
case's ``metadata.yaml``, licence and source from ``provenance.yaml``), hashes
every ``model.inp``, joins the SWMM 5.2.4 census
(``scripts/corpus_census.py``), and writes:

- ``corpus_index.parquet`` — one row per model, pinned to the upstream commit
- ``tier_pr/selection.json`` — fast PR gate
- ``tier_nightly/selection.json`` — ~500 models, balanced across tags
- ``tier_release/selection.json`` — every model that runs on SWMM 5.2.4 and
  has a verified licence

Models are never forked: rows record the upstream URL at the pinned commit
plus the SHA-256, and ``scripts/fetch_track_b_models.py`` downloads by hash.

Usage::

    python test_catalog/track_b/build_corpus_index.py --hydrocouple ../hc \\
        --census test_catalog/track_b/corpus_census.parquet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
UPSTREAM = "HydroCouple/openswmm.engine.benchmarks"
RAW = "https://raw.githubusercontent.com/" + UPSTREAM + "/{commit}/corpus/{model_id}/model.inp"
LICENSE_MAP = {"public-domain": "Unlicense", "unverified": "TBD-confirm"}
NIGHTLY_TARGET = 500
NIGHTLY_MAX_RUNTIME_S = 10.0
PR_MAX_RUNTIME_S = 5.0
# Catalog-level Track B cases (in this repo) that always gate PRs.
CATALOG_PR_CASES = ["B-EXTRAN-001", "B-RTC-001", "B-EPANET-001"]


def upstream_commit(checkout: Path) -> str:
    return subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()


def scan(checkout: Path, commit: str) -> pd.DataFrame:
    rows = []
    for inp in sorted((checkout / "corpus").glob("*/*/model.inp")):
        case = inp.parent
        if case.parent.name.startswith("_"):
            continue
        meta = yaml.safe_load((case / "metadata.yaml").read_text(encoding="utf-8")) or {}
        prov = yaml.safe_load((case / "provenance.yaml").read_text(encoding="utf-8")) or {}
        model_id = f"{case.parent.name}/{case.name}"
        rows.append(
            {
                "model_id": model_id,
                "collection": case.parent.name,
                "title": str(meta.get("title") or "").strip(),
                "hash": hashlib.sha256(inp.read_bytes()).hexdigest(),
                "tags": sorted(meta.get("tags") or []),
                "units": meta.get("units"),
                "routing": meta.get("routing"),
                "size_class": meta.get("size_class"),
                "upstream_runtime_class": meta.get("runtime_class"),
                "license": LICENSE_MAP.get(str(prov.get("license")), str(prov.get("license"))),
                "upstream_license": str(prov.get("license")),
                "provenance_source": str(prov.get("source") or ""),
                "url": RAW.format(commit=commit, model_id=model_id),
                "upstream_commit": commit,
                "path": f"corpus/{model_id}/model.inp",
            }
        )
    return pd.DataFrame(rows)


def balanced_pick(df: pd.DataFrame, target: int, must: list[str]) -> list[str]:
    """Greedy tag-coverage pick: take models that add the rarest uncovered tags first."""
    chosen = list(dict.fromkeys(m for m in must if m in set(df["model_id"])))
    counts: Counter[str] = Counter()
    for tags in df[df["model_id"].isin(chosen)]["tags"]:
        counts.update(tags)
    pool = df[~df["model_id"].isin(chosen)].sort_values(["runtime_s", "model_id"])
    tag_freq = Counter(t for tags in df["tags"] for t in tags)
    while len(chosen) < target and not pool.empty:
        scores = pool["tags"].apply(lambda ts: sum(1.0 / (1 + counts[t]) / tag_freq[t] ** 0.5 for t in ts))
        best = scores.idxmax()
        row = pool.loc[best]
        chosen.append(row["model_id"])
        counts.update(row["tags"])
        pool = pool.drop(index=best)
    return chosen


def write_selection(tier: str, payload: dict) -> None:
    path = HERE / f"tier_{tier}" / "selection.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hydrocouple", type=Path, required=True, help="checkout of openswmm.engine.benchmarks")
    ap.add_argument("--census", type=Path, default=HERE / "corpus_census.parquet")
    args = ap.parse_args()

    commit = upstream_commit(args.hydrocouple)
    df = scan(args.hydrocouple, commit)
    census = pd.read_parquet(args.census)
    df = df.merge(
        census[["model_id", "status", "runtime_s", "error_codes", "continuity_runoff_pct", "continuity_routing_pct", "engine_version"]],
        on="model_id",
        how="left",
    )
    df["status"] = df["status"].fillna("not_run")
    runnable = df[(df["status"] == "ran") & (df["license"] != "TBD-confirm")]

    old_pr = json.loads((HERE / "tier_pr" / "selection.json").read_text(encoding="utf-8")).get("model_ids", [])
    seed = [m for m in old_pr if "/" in m]
    fast = runnable[runnable["runtime_s"] <= PR_MAX_RUNTIME_S]
    pr_corpus = [m for m in seed if m in set(fast["model_id"])]
    rtc_fast = fast[fast["tags"].apply(lambda t: "controls" in t)].sort_values("runtime_s")["model_id"].tolist()
    for m in rtc_fast:
        if sum(1 for x in pr_corpus if x in set(rtc_fast)) >= 5:
            break
        if m not in pr_corpus:
            pr_corpus.append(m)
    dropped = [m for m in seed if m not in pr_corpus]

    nightly_pool = runnable[runnable["runtime_s"] <= NIGHTLY_MAX_RUNTIME_S]
    nightly = balanced_pick(nightly_pool, NIGHTLY_TARGET, pr_corpus)
    release = runnable["model_id"].tolist()

    df["tier"] = "none"
    df.loc[df["model_id"].isin(release), "tier"] = "tier_release"
    df.loc[df["model_id"].isin(nightly), "tier"] = "tier_nightly"
    df.loc[df["model_id"].isin(pr_corpus), "tier"] = "tier_pr"
    df.to_parquet(HERE / "corpus_index.parquet", index=False)

    common = {"upstream": f"https://github.com/{UPSTREAM}", "upstream_commit": commit,
              "engine": "EPA SWMM", "engine_version": str(census["engine_version"].iloc[0])}
    write_selection("pr", {"tier": "pr", **common,
                           "description": "Fast PR gate: catalog Track B cases plus corpus models that run on SWMM 5.2.4 in ≤ 5 s, including ≥ 5 control-rule (RTC) models.",
                           "catalog_cases": CATALOG_PR_CASES, "count": len(pr_corpus), "model_ids": pr_corpus,
                           "dropped_from_previous": dropped})
    write_selection("nightly", {"tier": "nightly", **common,
                                "description": f"~{NIGHTLY_TARGET} corpus models, ≤ {NIGHTLY_MAX_RUNTIME_S:g} s each on SWMM 5.2.4, picked greedily to cover every tag.",
                                "count": len(nightly), "model_ids": nightly})
    write_selection("release", {"tier": "release", **common,
                                "description": "Every corpus model that runs on SWMM 5.2.4 and carries a verified licence.",
                                "count": len(release), "model_ids": release})
    tag_cov = Counter(t for tags in df[df["model_id"].isin(nightly)]["tags"] for t in tags)
    all_tags = Counter(t for tags in df["tags"] for t in tags)
    print(json.dumps({
        "commit": commit, "models": len(df), "status": df["status"].value_counts().to_dict(),
        "licence": df["license"].value_counts().to_dict(),
        "pr": len(pr_corpus), "pr_dropped": dropped, "nightly": len(nightly), "release": len(release),
        "nightly_tags_missing": sorted(set(all_tags) - set(tag_cov)),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
