# Changelog

All notable changes to this suite are documented here.
Suite releases are independent of schema semver (`schemas/v1`).

## [Unreleased]

### Changed

- **The website is rebuilt as OpenHydro Bench**, in plain language: a home
  page that asks one question, a *Tests & results* matrix of every test
  against every model with a detail panel, a story page per test (what
  happens, why it matters, an exact-answer replay with each model's result,
  every model's checks in words and numbers, technical details folded away),
  *Score your model* with results templates and an in-browser check that
  mirrors the scorer, and *How it works*. Old `catalog.html` redirects.
- The scorer reads CSV results as well as Parquet, so a filled-in template
  can be scored directly.

### Added

- **HEC-RAS 6.6 scored** (`scripts/run_hecras.py`, `.github/workflows/hecras.yml`):
  installed silently on a Windows runner from HEC's GitHub release (installer
  SHA-256 pinned), Terms and Conditions for Use recorded for the runner user,
  plain-text projects generated per grid level and run headless through
  `ras-commander`. A1F-001: depth error 0.1 mm (limit 1 cm, passes) but no grid
  convergence (fails), because HEC-RAS stores input elevations to 0.001 ft.
- A1F-001 v1.1.0: inputs now match the reference (10 m, n = 0.03, wide-channel
  hydraulic radius, exact outlet depth).

- **openTELEMAC-2D 9.1.1 scored** on the dam-break cases (`scripts/run_telemac.py`,
  CI job installs it from conda-forge). Run as a black box on a 2D strip mesh
  with its default finite-volume settings. Results: A1F-010 (Ritter) fails —
  the wet front lags the exact one by 39 m after 60 s (allowed 2.5 m) and the
  observed order is 0.71; HLLC and second-order variants leave the lag at about
  50 m. A1F-011 (Stoker) passes its depth and mass checks but converges at 0.77
  (minimum 0.8). Mass is conserved to 0.0006 % in both.

- **ANUGA 4.0.1, GeoClaw 5.9.2 and LISFLOOD-FP 8.3 scored**
  (`scripts/run_anuga.py`, `run_geoclaw.py`, `run_lisflood.py`; weekly
  `.github/workflows/open-solvers.yml`). Each is installed from its official
  source and run with its own defaults on every grid level.
  - ANUGA passes Stoker, Thacker and MacDonald 2D; fails Ritter (front 12 m
    behind) and the oblique jump's mass check (−0.13 %, limit 0.1 %).
  - GeoClaw passes Stoker and Thacker; fails Ritter (front 61 m behind).
  - LISFLOOD-FP FV1 and DG2 pass MacDonald 2D; FV1 and DG2 converge below
    order 0.8 on the dam breaks and the bowl, and DG2 lags the Ritter front by
    66 m. The local-inertia solver (ACC) does not converge on any case — as
    expected for a scheme without advection, and worth knowing because it is
    LISFLOOD-FP's default for flood mapping.
  - Every production code fails the Ritter front check (1 mm contour within
    2.5 m). Flagged for maintainers: with a 1 mm contour on a front whose depth
    goes to zero, 1 mm of depth error moves the contour ~10 m, and production
    codes treat depths under 1 mm as dry.

## [0.4.0] — 2026-10-14

A second review. Every scored Track A case now has a run that passes it, and
the corpus can score any SWMM engine against 5.2.4.

### Fixed

- **MacDonald 2D reference was not a shallow-water solution** (flat free surface
  with flow and no friction). Rebuilt by MacDonald's method with Manning
  friction; A2A-010 v2.0.0.
- **Oblique-jump reference** used the gas-dynamics θ–β–M relation (34.0° instead
  of 39.6°) and put the upstream state on the wrong side. Rewritten from the
  exact shallow-water jump conditions; A2A-020 v2.0.0.
- **Joukowsky "continuity"** measured front smearing. Replaced by the exact
  storage balance ∫Δp dx = ρa²V₀t; A1P-020 v3.0.0.
- **Pipe and transport cases were unmeetable templates**: grid convergence on
  steady closed-form flow, "%" tolerances compared with absolute norms.
  Relative norms for "%" thresholds, a `relative_head_loss` metric,
  element-keyed analytic references (node and link namespaces kept apart), and
  `convergence.not_applicable` in schema v1.1.
- **PR corpus tier covered one collection** (38 legacy EXTRAN examples, on which
  SWMM 5.1.15 and 5.2.4 are bit-identical). Now 40 models picked for tag
  coverage across 9 collections.
- **Site:** LaTeX shown raw (Markdown ate the backslashes), test pages wider
  than a phone, EA 4 depth map hidden behind the floodplain patch, GitHub links
  to a non-existent `main` branch, axis titles overlapping tick labels.

### Added

- First scores for A1P-001 and A1P-010 (EPA EPANET 2.2), A1P-030 and A1F-020
  (new 1D demo solvers), A2A-010 and A2A-020 (2D demo solver with ghost-cell
  boundaries). The Track A demo job now gates CI.
- `scripts/corpus_parity.py`: SWMM 5.2.4 vs any SWMM build across a tier, with a
  self-check (exactly zero against itself) on every PR; SWMM 5.1.15 results
  published on the corpus page.
- Cross-build finding: the official win64 SWMM 5.2.4 differs from the
  `swmm-toolkit` build on B-RTC-001 (reported, not gating).
- Promotion rules (`docs/methodology/promotion.md`,
  `benchmark1d2d.catalog.promotion`) and a `review` field in manifests.
- Site: at-a-glance panel, section menu and promotion checklist on every case
  page; "still needs" column in the catalog; start-here paths and headline
  numbers on the overview; mobile menu; copy buttons for commands and hashes;
  score-card filter; "which file do I need" guide.

## [0.3.0] — 2026-10-13

An end-to-end audit found defects that affected published results. All are fixed,
covered by regression tests, and listed on the site's Reports page.

### Fixed

- **Track B parity compared results with themselves.** Non-analytic cases were
  scored by a stub that compared a solver's output with itself, so any output
  passed (and earned `B-1%`). Parity is now per element against pinned-engine
  reference results; a missing reference raises `ReferenceUnavailable` (not scored).
- **Error norms inflated observed orders by +1.** `L1 = mean(|e|)·dx` added a
  power of dx. Norms are domain-normalised; true demo orders are Ritter 0.95,
  Stoker 0.95, MacDonald 1.99, Joukowsky 0.49.
- **Fake 1D solvers.** The demo MacDonald and Joukowsky "solvers" returned the
  analytical solution. Replaced by a Heun GVF integration and a method-of-
  characteristics solver; convergence now rejects round-off errors on every mesh.
- **Thacker reference violated mass conservation** (wrong ω, missing cos² term).
  Corrected with pointwise PDE-residual tests; case A2A-001 v2.0.0.
- **Joukowsky convergence target** set from theory (0.5, min 0.4); case v2.0.0.
- **Probe lookup** mixed depth and bed from different cells for gauges on cell faces.
- **Certification claims** follow class and tolerance (A-V, A-C, A-L, A-F, B-x%).

### Added

- Schema v1.1.0: `intercomparison` class and reference kind, inputs fetched by
  hash from an archive (`committed: false` + `source`), explicit `pending`
  inputs (draft only), results columns `z`, `element_id`, `element_type`.
- EA Tests 1, 2, 4, 5 rebuilt as `A2C-` code inter-comparison cases from the
  official archive (`scripts/build_ea_cases.py`), plus EA Test 6A lab draft.
- Real inputs for every analytic case; four new generators (Darcy–Weisbach,
  Ogata–Banks, Bélanger, Todini–Pilati, the last cross-checked against EPANET 2.2).
- Demo 2D finite-volume solver (`examples/demo_solver/swe2d.py`) passing Thacker
  and EA Tests 1, 2, 4.
- SWMM binary-output and EPANET 2.2 adapters; `scripts/make_reference.py`;
  Track B cases B-RTC-001 (control rules) and B-EPANET-001 (Net1).
- Track B corpus census on SWMM 5.2.4 and a full corpus index pinned to a
  HydroCouple commit; tiers built from measured runtimes.
- Bellinge field-validation draft (CC BY items only).
- Redesigned GitHub Pages site: test pages with charts, coverage matrix,
  corpus explorer, reports and audit log, downloads with hashes.

### Changed

- Licences corrected: Weber, Bergant, Rubinato data → `TBD-confirm`; Bellinge
  rain gauges are CC BY-NC (excluded); EA OGL scope limited to the data archive.
- CI: no placeholder hashes; engines run in Track B CI; Pages builds on Linux.

## [0.2.1] — 2026-10-13

### Added

- `reference_engines/swmm-5.2.4/pin.json` + `benchmark1d2d engines` CLI; site Engines page.
- Public site IA: Home, Catalog, Get started, Engines, Methodology (cool slate/teal redesign).
- Fixture scorecards + Windows SWMM self-parity job feeding GitHub Pages.

### Changed

- Renamed project from `hydrobench` to **Benchmark1d2d** (`benchmark1d2d` package/CLI)
  to avoid collision with the EMScience HydroBench catchment diagnostic toolkit.
  GitHub repo and Pages move to `scott-jeffers/benchmark1d2d`.

## [0.2.0] — 2026-10-13

### Added

- Multi-mesh vertical slice gate: all four Track A 1D cases PASS with observed order / GCI.
- Demo solver: MUSCL–HLL with exact wet–dry Riemann flux (Toro); Ritter iso-contour scoring.
- Real EPA SWMM 5.2.4 win64 pin (`SHA256SUMS`) and `scripts/run_swmm_self_parity.py` (100% self-parity).
- HydroCouple federation: mirrored `tags.yaml` / provenance schema, 50-model PR tier, fetch-by-hash script.
- Phase 5 2D analytical: terrain I/O, Thacker / MacDonald 2D / oblique jump, two-solver gate.
- EA benchmarks licensed `OGL-UK-3.0` and promoted to `candidate`.
- GitHub Pages workflow; Crossref DOI checks green on catalog citations.

### Notes

- CADAM / IMPACT lab cases and Malpasset remain `TBD-confirm` / `draft`.
- SWMM binaries are gitignored; CI/local fetch from the USEPA v5.2.4 release.

## [0.1.0] — 2026-10-13

### Added

- Foundation Pack: dual-track architecture (Track A physics V&V, Track B industry parity).
- `schemas/v1` contract: test manifest, results, scorecard, network_1d, terrain_2d, coupling_1d2d.
- Catalog validator (schema, SHA-256, license register, optional Crossref DOI).
- Track A 1D vertical slice: Ritter, Stoker, MacDonald, Joukowsky reference generators.
- Python `benchmark1d2d` CLI: `catalog`, `run`, `score`, `verify`, `report`.
- Metrics (L1/L2/L∞, mass error, NSE, KGE, peak, arrival/front time, CSI) and GCI convergence.
- Deterministic Ed25519-signed score cards.
- Track B scaffolding: SWMM 5.2.4 Dockerfile placeholder, `.rpt` adapter, corpus index builder.
- Static site generator from manifests and score cards.
- Draft catalog folders for Phases 5–9.
