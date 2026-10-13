# Track B federation with HydroCouple / openswmm.engine.benchmarks

Hydrobench **federates** the HydroCouple corpus — it does not fork the `.inp`
library. Model files stay in the upstream repo (or a hash-addressed cache);
this suite records tags, provenance, and tier membership.

## Upstream

- Repo: https://github.com/HydroCouple/openswmm.engine.benchmarks (`dev` branch)
- License: Unlicense
- Layout: `corpus/<collection>/<case>/{model.inp,metadata.yaml,provenance.yaml}`
- Tag vocabulary (canonical): `harness/schemas/tags.yaml`
- Provenance schema: `harness/schemas/provenance.schema.yaml`
- Metadata schema: `harness/schemas/metadata.schema.yaml`

## Tag vocabulary (mirrored)

See [`hydrocouple_tags.yaml`](hydrocouple_tags.yaml) — a verbatim mirror of
HydroCouple's controlled vocabulary as of 2026-10-13. Unknown tags must not
be invented in `corpus_index.parquet`; extend the mirror via PR after upstream
accepts the tag.

Groups (documentation only; tags are flat):

| Group | Examples |
|-------|----------|
| domain | `hydrology`, `hydraulics`, `quality`, `lid`, `controls`, `2d` |
| purpose | `regression`, `analytical`, `stability`, `performance` |
| features | `dynamic_wave`, `kinematic_wave`, `pump`, `weir`, `rtc`, … |
| provenance | `real_world`, `synthetic`, `textbook`, `contributed`, `anonymized` |

## Provenance fields mapped into `corpus_index.parquet`

| HydroCouple `provenance.yaml` | hydrobench column |
|-------------------------------|-------------------|
| `license` | `license` |
| `source` / `origin` | `provenance_source` |
| case id / path | `model_id`, `path` |
| content hash of `model.inp` | `hash` |
| tags from `metadata.yaml` | `tags` |
| tier assignment (hydrobench) | `tier` (`pr` / `nightly` / `release`) |

## PR tier (~50 models)

[`tier_pr/selection.json`](tier_pr/selection.json) lists model IDs drawn from
HydroCouple collections that are Unlicense and tagged for fast CI
(`regression` + `hydraulics`, preferring `owa-extran` / `epa` textbook cases).
Files are **not** vendored; `scripts/fetch_track_b_models.py` resolves each
ID to an upstream raw URL and verifies SHA-256 before use.

Verified against openswmm.engine.benchmarks on 2026-10-13 (tag vocabulary +
corpus layout). Engine runs through HydroCouple harness remain upstream work.
