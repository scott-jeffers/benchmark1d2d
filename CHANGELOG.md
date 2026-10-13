# Changelog

All notable changes to this suite are documented here.
Suite releases are independent of schema semver (`schemas/v1`).

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

### Notes

- Placeholder SHA-256 hashes remain where real binaries/datasets are not yet vendored.
- EA / CADAM / Malpasset licenses are `TBD-confirm` and blocked from promotion past `draft`.
