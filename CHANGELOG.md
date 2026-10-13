# Changelog

All notable changes to this suite are documented here.
Suite releases are independent of schema semver (`schemas/v1`).

## [Unreleased]

### Added

- Phase 5 (2D analytical): terrain I/O (GeoTIFF / numpy.savez / UGRID-lite),
  `references.macdonald_2d` and `references.oblique_jump`, Thacker alias
  `planar_oscillation`, demo 2D exact + O(dx)-perturbed writers, scorer support
  for `(x,y,t)` analytic grids, and `scripts/run_phase5_2d.py`.
- Promoted A2A-001, A2A-010, A2A-020 manifests from `draft` to `candidate`.

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
- Python `hydrobench` CLI: `catalog`, `run`, `score`, `verify`, `report`.
- Metrics (L1/L2/L∞, mass error, NSE, KGE, peak, arrival/front time, CSI) and GCI convergence.
- Deterministic Ed25519-signed score cards.
- Track B scaffolding: SWMM 5.2.4 Dockerfile placeholder, `.rpt` adapter, corpus index builder.
- Static site generator from manifests and score cards.
- Draft catalog folders for Phases 5–9.
