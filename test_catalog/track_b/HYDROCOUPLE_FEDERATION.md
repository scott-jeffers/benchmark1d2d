# Track B federation with HydroCouple / openswmm.engine.benchmarks

Benchmark1d2d **federates** the HydroCouple corpus — it does not fork the `.inp`
library. Model files stay in the upstream repo (or a hash-addressed cache);
this suite records tags, provenance, and tier membership.

## Upstream

- Repo: https://github.com/HydroCouple/openswmm.engine.benchmarks, pinned to commit `63eb8bc5b4e741c82195ed65c4d7d146b86da1cc` (2026-10-03). Every index row records the raw URL at that commit and the file's SHA-256; moving to a newer commit means re-running the census and rebuilding the index.
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

| HydroCouple `provenance.yaml` | benchmark1d2d column |
|-------------------------------|-------------------|
| `license` | `license` |
| `source` / `origin` | `provenance_source` |
| case id / path | `model_id`, `path` |
| content hash of `model.inp` | `hash` |
| tags from `metadata.yaml` | `tags` |
| tier assignment (benchmark1d2d) | `tier` (`pr` / `nightly` / `release`) |

## PR tier (~50 models)

[`tier_pr/selection.json`](tier_pr/selection.json) lists model IDs drawn from
HydroCouple collections that are Unlicense and tagged for fast CI
(`regression` + `hydraulics`, preferring `owa-extran` / `epa` textbook cases).
Files are **not** vendored; `scripts/fetch_track_b_models.py` resolves each
ID to an upstream raw URL and verifies SHA-256 before use.

Verified against openswmm.engine.benchmarks on 2026-10-13 (tag vocabulary +
corpus layout). Engine runs through HydroCouple harness remain upstream work.

## Census on EPA SWMM 5.2.4 (13 Oct 2026)

`scripts/corpus_census.py` runs every model on the pinned engine. Of 1,396 models, 941 run
cleanly, 296 stop with input errors (mostly older-version syntax: ERROR 205, 207, 209, 211, 235;
32 reference rainfall files that are not in the repository, ERROR 317), 157 exceed the 60 s
limit, and 2 fail in the engine or harness. Of the 941 that run, 98 report continuity errors
beyond ±5 % and are excluded from tiers, because a non-conserving reference cannot anchor
parity. These lists are worth sending upstream; the index (`corpus_index.parquet`, `status`,
`error_codes`, `continuity_*`) has every row.
