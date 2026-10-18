# Benchmark1d2d — Open V&V Benchmarks for Hydraulic Solvers

[![Track A](https://img.shields.io/badge/Track%20A-verification-0A7-blue)](#the-two-tracks)
[![Track B](https://img.shields.io/badge/Track%20B-parity-6B4-purple)](#the-two-tracks)
[![catalog](https://img.shields.io/badge/catalog-v0.3.0-lightgrey)](CHANGELOG.md)
[![schema](https://img.shields.io/badge/schema-v1.1.0-green)](schemas/v1/)
[![DOI](https://img.shields.io/badge/DOI-pending-lightgrey)](CITATION.cff)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

> An open, engine-agnostic suite for verifying and validating 1D, 2D and coupled
> 1D/2D hydraulic solvers — C++, Rust, WebAssembly or neural surrogate — against
> exact solutions, laboratory measurements and the EPA SWMM / EPANET reference engines.


## Why this exists

- No shared, citable "standard of care" for proving a water solver is correct.
- Vendor validation reports are not reproducible by third parties.
- New solver classes (GPU, WASM, ML surrogates) need the same yardstick as SWMM.

## The two tracks

| | Track A — Physics & Verification | Track B — Industry Parity |
|---|---|---|
| Question | Does it solve the equations correctly? | Does it behave like SWMM 5.2.4 / EPANET 2.2? |
| Ground truth | Exact solutions; lab & field measurements | Pinned reference-engine output |
| Can prove | The solver is **wrong** | The solver **differs** |
| Metrics | L1/L2/L∞, observed order, mass error, NSE, arrival time | ±% peak, volume, timing; continuity error |
| Example | Thacker bowl, Ritter dam break, EA Test 1–5 | HydroCouple corpus, EXTRAN cases, RTC rules, EPANET Net1 |

> **Track A results can prove a solver wrong. Track B results can only prove it different from the reference engine.** Every badge and table keeps the two apart.

### Scores, not certificates

There are no pass marks. Every check is reported as a percent difference from
the right answer (Track A) or from the reference engine (Track B); a result's
score on a test is its largest accuracy difference, with mass error, timing
(in seconds) and NSE shown beside it, and the error on every grid. Models are
ranked on each test and rated head to head on the tests they share
([scoring method 3.0](docs/methodology/scoring_v3.md)). Track A and Track B
stay separate: a parity score says how far a solver is from SWMM or EPANET,
not whether either is right.

## Quickstart

```bash
python -m pip install -e ".[dev,engines,site]"   # engines: EPA SWMM 5.2.4 + EPANET 2.2 for Track B
python scripts/fetch_inputs.py                    # DEMs and other large inputs, verified by SHA-256
benchmark1d2d catalog list --track A
benchmark1d2d engines
benchmark1d2d run A1F-010 --solver examples/demo_solver/solve.py --adapter generic_parquet
benchmark1d2d score A1F-010 --results out/A1F-010.parquet
python scripts/run_vertical_slice.py     # 1D demo solvers on every refinement level
python scripts/run_network_cases.py      # EPA EPANET 2.2 on the pipe-network cases
python scripts/run_demo_2d.py            # 2D finite-volume demo on every 2D analytic and EA case
python scripts/corpus_parity.py --corpus hc/corpus --tier pr --candidate-python <py> --label <name>
python site/build.py                     # open site/dist/index.html
```

Public site: [scott-jeffers.github.io/benchmark1d2d](https://scott-jeffers.github.io/benchmark1d2d/) —
catalog with a page per case (reference, tolerances, latest run, promotion
checklist), SWMM corpus and parity results, reports and audit log, downloads.

## How a benchmark run works

```
manifest → fetch & hash inputs → execute solver (sandboxed)
        → adapt outputs to [t, x, y, h, u, v, p] Parquet
        → score against reference → signed score card
```

1. Load `manifest.json` and validate against `schemas/v1/test_manifest.schema.json`.
2. Fetch inputs; verify each SHA-256.
3. Execute the solver as a black box (binary | container | WASM).
4. Adapt native output to the results contract.
5. Score metrics / convergence; emit a signed, reproducible score card.

## The output contract

See [`schemas/v1/results.schema.json`](schemas/v1/results.schema.json).
Columns: `t, x, y, h, u, v, p`, optional `Q`, `c` and bed elevation `z`.
Network solvers add `element_id` / `element_type` so Track B parity is computed
per node and link, never by row order.

## Test catalog

39 cases across eight components; the [site](https://scott-jeffers.github.io/benchmark1d2d/catalog.html)
shows each one with its reference, checks and latest scores. Highlights:

| ID | Physics | Ground truth | Scored on (convergence rate reported beside) |
|---|---|---|---|
| A1F-010 / 011 | 1D dam break, dry and wet bed | Ritter (1892), Stoker (1957) | front position or L1(h) |
| A1F-001 | 1D steady backwater | MacDonald et al. (1997) manufactured bed | L1(h) |
| A1F-020 | Stationary hydraulic jump | Bélanger sequent depths | L1(h), no drift |
| A1P-001 | Single pipe, Colebrook friction | Darcy–Weisbach, Colebrook–White | head loss |
| A1P-010 | Two-loop pipe network | Todini–Pilati solve to 1e-12 m | nodal head, link flow |
| A1P-020 | Instant valve closure | Joukowsky (1900) | peak pressure, exact storage balance |
| A1P-030 | Tracer advection–dispersion | Ogata & Banks (1961) | relative L1(c), mass |
| A2A-001 | 2D bowl with moving shoreline | Thacker (1981), corrected in v0.3 | L1(h), mass |
| A2A-010 | 2D steady channel with friction | MacDonald construction on a 2D grid | L1(h), mass |
| A2A-020 | Oblique hydraulic jump | Exact shallow-water jump conditions | L1(h), mass |
| A2C-EA1…EA5 | EA 2D inter-comparison tests | Settled pond level, mass conservation | from the official EA archive, fetched by hash |
| B-EXTRAN-001, B-RTC-001 | Sewer routing, control rules | EPA SWMM 5.2.4 | peak, volume, timing at every element |
| B-EPANET-001 | Water distribution (Net1) | EPANET 2.2 | peak pressure, volume at every element |

Full catalog: `benchmark1d2d catalog list`.

## Adding your solver

Adapters live under `runner/adapters/`. Implement a shim that writes the results
contract, then:

```bash
benchmark1d2d run <TEST_ID> --solver ./my_solver --adapter generic_parquet
```

Container and WASM modes are supported by the exec layer (stubs in v0.1).

## Promoting a case

Only `frozen` cases have fixed inputs and answers. A case moves from `draft` to
`candidate` to `frozen` by meeting the rules in
[`docs/methodology/promotion.md`](docs/methodology/promotion.md): verified
licence, available inputs and reference, a stated reason and scale for every
check, a published run with convergence evidence, two independent
codes scored (for parity cases, a second build of the reference engine), and a
recorded maintainer review. Seven of the eight rules are computed; each case
page shows its checklist.

## Adding a test case

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Every case needs a manifest, reference,
citation and a license registered in [`DATA_LICENSES.md`](DATA_LICENSES.md).

## How tolerances are set

Documented in [`docs/methodology/`](docs/methodology/). Tolerances are never
edited ad hoc — every threshold carries a `rationale` string that appears on
the public test page. Verification uses observed order / GCI (ASME V&V 20 /
Roache), not a single-mesh error threshold.

## Reproducibility & provenance

- Input files are pinned by SHA-256.
- Track B references a pinned engine build (version + binary hash), never
  "SWMM" in general. `scripts/make_reference.py --check` re-runs SWMM 5.2.4 and
  EPANET 2.2 in CI and fails if a committed reference drifts; a Windows job scores
  the official EPA binaries against the same references (cross-build parity).
  EXTRAN Example 1 agrees to 0.0 % across the two builds; the control-rule case
  B-RTC-001 does not (−3.7 % peak depth, a pump-cycle peak moved by 92,400 s), so
  it is reported there as build-sensitive rather than gating.
- A case whose reference is missing is **not scored** — never passed.
- Score cards are canonical JSON with a SHA-256 content hash and byte-identical across reruns; check one with `benchmark1d2d verify-card`. Demo cards are signed with a development key published in the repo, so their signatures show integrity, not authorship.
- Releases mint a Zenodo DOI (pending for v0.1).

## Governance & review

See [`GOVERNANCE.md`](GOVERNANCE.md). ASCE/EPA reviewer packet: `docs/submission/`.

## Citing Benchmark1d2d

See [`CITATION.cff`](CITATION.cff). Each test case also cites its original source;
do not drop those citations when you publish a score.

## Related projects

- [HydroCouple / openswmm.engine.benchmarks](https://github.com/HydroCouple/openswmm.engine.benchmarks) — Track B federates this corpus
- [SWASHES](https://www.idpoisson.fr/swashes/) — shallow-water analytic solutions
- Environment Agency 2D benchmarks (Néelz & Pender)
- [1729-SWMM5-Models](https://github.com/SWMMEnablement/1729-SWMM5-Models) — the library the HydroCouple corpus was built from; repaired and extended by R. E. Dickinson as [1729-SWMM5-Models-2030](https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030)

## License

- **Code & schemas:** Apache-2.0 — see [`LICENSE`](LICENSE)
- **Datasets:** per-entry terms in [`DATA_LICENSES.md`](DATA_LICENSES.md)
