# Get started

benchmark1d2d is an open V&V suite for free-surface and pressurized water
solvers. You score a solver against catalog cases; Track A checks physics,
Track B checks parity with a pinned industry engine.

## Install

```bash
git clone https://github.com/scott-jeffers/benchmark1d2d.git
cd benchmark1d2d
python -m pip install -e ".[dev]"
```

Confirm the CLI:

```bash
benchmark1d2d catalog list
benchmark1d2d engines
```

`engines` prints the pinned EPA SWMM version and binary hashes used for Track B.

## Score a Track A demo case

Run the bundled demo solver on an analytic free-surface case, then score:

```bash
benchmark1d2d run A1F-010_ritter_dry_bed_dambreak \
  --solver examples/demo_solver/solve.py \
  --out out/demo

benchmark1d2d score A1F-010_ritter_dry_bed_dambreak \
  --results out/demo/A1F-010_ritter_dry_bed_dambreak.parquet \
  --solver-name demo --solver-version 0.1.0
```

A **PASS** means gating criteria and (when required) observed convergence order
are satisfied. A **FAIL** means the equations are not solved to the published
tolerance — Track A can prove a solver wrong.

## Track B parity (SWMM)

Track B compares your solver to pinned **SWMM 5.2.4** output (never hand-edited
references). Fetch the official win64 binaries into
`reference_engines/swmm-5.2.4/bin/` (see that folder’s README), then:

```bash
python scripts/run_swmm_self_parity.py
```

That gate proves the pin is self-consistent on `B-EXTRAN-001`. To score your own
adapter, adapt SWMM report output with `--adapter swmm5` and compare against the
case reference.

## Build the local site

```bash
python scripts/run_vertical_slice.py || true
python site/build.py --scorecards out --scorecards site/fixtures/scorecards
```

Open `site/dist/index.html` in a browser.

## What to read next

- [Catalog](catalog.html) — every published case
- [Engines](engines.html) — SWMM pin details
- [Methodology](methodology.html) — tolerances and V&V plan
