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

## Lineage

The HydroCouple corpus is the **1729 SWMM5 models** library before its repairs:
its collection and model names match
[SWMMEnablement/1729-SWMM5-Models](https://github.com/SWMMEnablement/1729-SWMM5-Models)
(compiled during the February 2026 Fixathon, Unlicense). Robert E. Dickinson's
[SWMMBobSWMM6/1729-SWMM5-Models-2030](https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030)
(Unlicense, about 3,800 models; commit `70b8f6e`, 24 August 2026) works through
the input-error chains this census stops on (ERROR 209, 205, 211, 317, 361),
restores shared rainfall files under `DataFiles/` with a path manifest, and
adds a summary per model. Many ERROR 317 models need client rainfall that was
never published, and ERROR 235 was not repaired, so some models stay out of
both libraries' runs.

Planned (review F9): rebuild the census from the -2030 library at a pinned
commit, keep the HydroCouple tiers as they are until the two are reconciled,
and add XL models to the release tier with the longer timeout
(`corpus_parity.py --xl-timeout`, 1,800 s by default). Every run works on a
scratch copy of the model's folder: 124 models carry `[FILES] SAVE`, which
used to overwrite files next to the input.

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
limit (all 78 XL models fail: 42 input errors, 35 timeouts, 1 engine error), and 2 fail in the engine or harness. Of the 941 that run, 98 report continuity errors
beyond ±5 % and are excluded from tiers, because a non-conserving reference cannot anchor
parity. These lists are worth sending upstream; the index (`corpus_index.parquet`, `status`,
`error_codes`, `continuity_*`) has every row.
