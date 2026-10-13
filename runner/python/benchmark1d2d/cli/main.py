"""benchmark1d2d CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from benchmark1d2d.adapters import REGISTRY
from benchmark1d2d.catalog import find_repo_root, list_catalog, load_manifest
from benchmark1d2d.engines import assert_pin_matches_sha256sums, list_pinned_engines
from benchmark1d2d.exec.runner import run_solver
from benchmark1d2d.scoring.scorer import score_case


def _cmd_catalog_list(args: argparse.Namespace) -> int:
    rows = list_catalog(track=args.track)
    if not rows:
        print("No catalog cases found.")
        return 0
    print(f"{'TEST_ID':<42} {'TRACK':<6} {'STATUS':<12} TITLE")
    for r in rows:
        print(
            f"{r['test_id']:<42} {r['track']:<6} {str(r.get('status', '')):<12} {r.get('title', '')}"
        )
    return 0


def _solver_argv(solver: str, manifest_path: Path, out_path: Path, dx: float | None) -> list[str]:
    """Build argv for a demo Python solver or a generic executable."""
    solver_path = Path(solver)
    if solver_path.suffix == ".py" or solver_path.name == "solve.py":
        argv = [sys.executable, str(solver_path.resolve()), "--manifest", str(manifest_path), "--out", str(out_path)]
        if dx is not None:
            argv.extend(["--dx", str(dx)])
        return argv
    return [str(solver_path), "--manifest", str(manifest_path), "--out", str(out_path)]


def _cmd_run(args: argparse.Namespace) -> int:
    repo = find_repo_root()
    manifest = load_manifest(args.test_id, repo=repo)
    case_dir = Path(manifest["_case_dir"])
    out_dir = Path(args.out) if args.out else repo / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_out = out_dir / f"{manifest['test_id']}.raw.parquet"
    final_out = out_dir / f"{manifest['test_id']}.parquet"

    # Default dx from coarsest mesh_refinement level when present.
    dx = None
    levels = (manifest.get("simulation") or {}).get("mesh_refinement", {}).get("levels")
    if levels:
        dx = float(levels[0])

    argv = _solver_argv(args.solver, Path(manifest["_manifest_path"]), raw_out, dx)
    work_dir = out_dir / "work" / manifest["test_id"]
    work_dir.mkdir(parents=True, exist_ok=True)
    proc = run_solver(argv, case_dir, raw_out, work_dir)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

    adapter_name = args.adapter
    if adapter_name not in REGISTRY:
        raise SystemExit(f"Unknown adapter {adapter_name!r}; known: {sorted(REGISTRY)}")
    REGISTRY[adapter_name].adapt(raw_out, final_out)
    print(f"Wrote {final_out}")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    repo = find_repo_root()
    manifest = load_manifest(args.test_id, repo=repo)
    private_key = None
    if args.key_file:
        private_key = Path(args.key_file).read_bytes()

    refinement = None
    if args.refinement:
        refinement = list(args.refinement)

    from benchmark1d2d.scoring.scorer import ReferenceUnavailable

    try:
        card = score_case(
            manifest,
            args.results,
            refinement_results=refinement,
            timestamp=args.timestamp,
            private_key=private_key,
            solver={
                "name": args.solver_name or "demo",
                "version": args.solver_version or "0.1.0",
                "adapter": args.adapter or "generic_parquet",
            },
        )
    except ReferenceUnavailable as exc:
        print(f"NOT SCORED: {exc}")
        return 3
    out_path = Path(args.out) if args.out else Path(args.results).with_suffix(".scorecard.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"passed={card['passed']}  wrote {out_path}")
    for c in card["criteria_results"]:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"  [{mark}] {c['id']}: {c['metric']}={c['observed']} ({c['threshold']})")
    if card.get("convergence_result"):
        cr = card["convergence_result"]
        mark = "PASS" if cr["passed"] else "FAIL"
        print(f"  [{mark}] convergence p={cr['observed_order']:.4f}")
    return 0 if card["passed"] else 1


def _cmd_verify(args: argparse.Namespace) -> int:
    import jsonschema

    repo = find_repo_root()
    manifest = load_manifest(args.test_id, repo=repo)
    schema_path = repo / "schemas" / "v1" / "test_manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # Strip private helper keys before schema validation.
    public = {k: v for k, v in manifest.items() if not k.startswith("_")}
    jsonschema.validate(instance=public, schema=schema)

    # Hash-check inputs when files exist (placeholder empty SHA allowed for stubs).
    case_dir = Path(manifest["_case_dir"])
    for inp in public.get("inputs", []):
        rel = inp.get("path")
        if not rel:
            continue
        fpath = case_dir / rel
        if not fpath.is_file():
            print(f"WARN: missing input {fpath}")
            continue
        import hashlib

        digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
        expected = inp.get("sha256")
        if expected and digest != expected:
            # Allow empty-file placeholder hash used in catalog stubs.
            empty = hashlib.sha256(b"").hexdigest()
            if expected == empty and fpath.stat().st_size == 0:
                pass
            elif expected == empty:
                print(f"WARN: stub sha256 for non-empty {fpath}")
            else:
                raise SystemExit(f"SHA-256 mismatch for {fpath}: {digest} != {expected}")
    print(f"OK  {public['test_id']}  schema+hash validation passed")
    return 0


def _cmd_engines(args: argparse.Namespace) -> int:
    repo = find_repo_root()
    assert_pin_matches_sha256sums(repo)
    engines = list_pinned_engines(repo)
    if not engines:
        print("No pinned reference engines found.")
        return 0
    for pin in engines:
        binaries = pin.get("binaries") or {}
        dll = binaries.get("swmm5.dll") or next(iter(binaries.values()), "")
        short = dll[:16] + "…" if len(dll) > 16 else dll
        print(
            f"{pin.get('engine')} {pin.get('version')}  "
            f"build={pin.get('build', '—')}  "
            f"swmm5.dll={short}  "
            f"dir={pin.get('_engine_dir')}"
        )
        if args.verbose:
            print(f"  upstream: {pin.get('upstream_url')}")
            print(f"  asset:    {pin.get('asset')}")
            for name, digest in binaries.items():
                print(f"  {name}: {digest}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    repo = find_repo_root()
    score_dir = Path(args.scorecards) if args.scorecards else repo / "out"
    cards = sorted(score_dir.glob("**/*.scorecard.json"))
    if not cards:
        cards = sorted(score_dir.glob("**/*scorecard*.json"))
    rows = []
    for path in cards:
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(
            {
                "test_id": card.get("test_id", path.stem),
                "track": card.get("track", ""),
                "passed": card.get("passed"),
                "path": str(path),
            }
        )

    print(f"{'TEST_ID':<42} {'TRACK':<6} PASSED")
    for r in rows:
        print(f"{r['test_id']:<42} {r['track']:<6} {r['passed']}")

    if args.open:
        html_path = score_dir / "report.html"
        lines = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>benchmark1d2d report</title>",
            "<style>body{font-family:system-ui,sans-serif;margin:2rem}table{border-collapse:collapse}",
            "td,th{border:1px solid #ccc;padding:.4rem .8rem}</style></head><body>",
            "<h1>benchmark1d2d score summary</h1><table><tr><th>Test</th><th>Track</th><th>Passed</th></tr>",
        ]
        for r in rows:
            lines.append(
                f"<tr><td>{r['test_id']}</td><td>{r['track']}</td><td>{r['passed']}</td></tr>"
            )
        lines.append("</table></body></html>")
        html_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {html_path}")
        webbrowser.open(html_path.resolve().as_uri())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark1d2d", description="Open V&V benchmarks for water solvers")
    sub = parser.add_subparsers(dest="command", required=True)

    cat = sub.add_parser("catalog", help="Browse the test catalog")
    cat_sub = cat.add_subparsers(dest="catalog_cmd", required=True)
    cat_list = cat_sub.add_parser("list", help="List catalog cases")
    cat_list.add_argument("--track", choices=["A", "B"], default=None)
    cat_list.set_defaults(func=_cmd_catalog_list)

    run = sub.add_parser("run", help="Execute a solver on a catalog case")
    run.add_argument("test_id")
    run.add_argument("--solver", required=True, help="Path to solver binary or Python script")
    run.add_argument("--adapter", default="generic_parquet")
    run.add_argument("--out", default=None, help="Output directory")
    run.set_defaults(func=_cmd_run)

    score = sub.add_parser("score", help="Score results against the case reference")
    score.add_argument("test_id")
    score.add_argument("--results", required=True)
    score.add_argument("--timestamp", default=None, help="ISO-8601 timestamp for deterministic cards")
    score.add_argument("--key-file", default=None, dest="key_file")
    score.add_argument("--refinement", nargs="*", default=None, help="Extra refinement result Parquets")
    score.add_argument("--out", default=None)
    score.add_argument("--solver-name", default=None)
    score.add_argument("--solver-version", default=None)
    score.add_argument("--adapter", default="generic_parquet")
    score.set_defaults(func=_cmd_score)

    verify = sub.add_parser("verify", help="Validate manifest schema and input hashes")
    verify.add_argument("test_id")
    verify.set_defaults(func=_cmd_verify)

    report = sub.add_parser("report", help="Summarize score cards")
    report.add_argument("--open", action="store_true", help="Write HTML stub and open it")
    report.add_argument("--scorecards", default=None, help="Directory of scorecard JSON files")
    report.set_defaults(func=_cmd_report)

    engines = sub.add_parser("engines", help="Show pinned reference engines (SWMM, …)")
    engines.add_argument("-v", "--verbose", action="store_true", help="Print full hashes and URLs")
    engines.set_defaults(func=_cmd_engines)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
