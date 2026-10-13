# Get started

benchmark1d2d is an open V&V suite for free-surface and pressurized water
solvers. You score a solver against catalog cases; Track A checks physics,
Track B checks parity with a pinned industry engine.

## Install

```bash
git clone https://github.com/scott-jeffers/benchmark1d2d.git
cd benchmark1d2d
python -m pip install -e ".[dev,engines]"   # engines = EPA SWMM 5.2.4 and EPANET 2.2
python scripts/fetch_inputs.py              # large inputs (DEMs), each checked by SHA-256
```

Confirm the CLI:

```bash
benchmark1d2d catalog list
benchmark1d2d engines
```

## What your solver must write

One Parquet file per run with columns `t, x, y, h, u, v, p` (SI units), plus
`Q`, `c` and bed elevation `z` where they apply. Network solvers add
`element_id` (node or link name) and `element_type`. Each case's page lists the
variables, output times and probe points it needs.

## Score a Track A case

The repository ships simple demo solvers you can copy:

```bash
python scripts/run_vertical_slice.py    # 1D: Ritter, Stoker, MacDonald, Joukowsky on every mesh level
python scripts/run_demo_2d.py A2A-001   # 2D: Thacker bowl with a first-order finite-volume scheme
```

To score your own results, pass every refinement level so the observed order of
accuracy can be measured:

```bash
benchmark1d2d score A1F-010 --results out/mine_dx1.25.parquet \
  --refinement out/mine_dx10.parquet out/mine_dx5.parquet out/mine_dx2.5.parquet out/mine_dx1.25.parquet \
  --solver-name my-solver --solver-version 1.0
```

A **pass** needs every gating criterion and the convergence check. A **fail**
on a verification case means the equations are not being solved to the stated
tolerance: Track A can prove a solver wrong.

## Score a Track B case

Run your solver on the case's `inputs/network.inp` and write per-element results
(the `swmm5` and `epanet22` adapters show the format), then:

```bash
benchmark1d2d score B-RTC-001 --results my_rtc.parquet --solver-name my-solver
```

The score card names the worst node or link for each criterion. Reference
results come from the pinned engine (`scripts/make_reference.py`); if a case's
reference is missing the CLI prints `NOT SCORED` rather than a pass.

