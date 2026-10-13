# Data license register

Every dataset in the catalog **must** have an entry here. CI refuses manifests
whose `provenance.license` is missing or not listed in this register.
Datasets marked `TBD-confirm` may only appear with `status: draft` and cannot
be promoted to `candidate` or `frozen` until a real license is recorded.

| License ID | Dataset / corpus | Terms summary | Source |
|---|---|---|---|
| `Apache-2.0` | hydrobench code & schemas | Apache Software License 2.0 | [LICENSE](LICENSE) |
| `Unlicense` | 1729-SWMM5-Models (SWMMEnablement) | Public domain dedication | https://github.com/SWMMEnablement/1729-SWMM5-Models |
| `Unlicense` | 1729-SWMM5-Models-2030 (Dickinson) | Public domain dedication | https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030 |
| `Unlicense` | openswmm.engine.benchmarks (HydroCouple) | Public domain dedication | https://github.com/HydroCouple/openswmm.engine.benchmarks |
| `CC-BY-4.0` | Bellinge urban drainage dataset | Creative Commons Attribution 4.0 | https://doi.org/10.11583/DTU.c.5029124 |
| `analytic-public` | Analytic reference solutions (Ritter, Stoker, Thacker, MacDonald, Joukowsky, …) | Equations from published literature; generators under Apache-2.0 | See per-test README |
| `TBD-confirm` | Environment Agency 2D benchmarks (EA1–EA5) | **Blocked pending license confirmation** | https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm |
| `TBD-confirm` | CADAM / IMPACT laboratory cases (Toce, idealised city, triangular sill) | **Blocked pending license confirmation** | CADAM / IMPACT project reports |
| `TBD-confirm` | Malpasset 1959 field case | **Blocked pending license confirmation** | Goutal (1999); Hervouet & Petitjean (1999) |
| `synthetic-internal` | Synthetic Track B fixtures used in unit tests | Internal test data; not for certification | `schemas/v1/tests/` |

## Rules

1. A new test case PR must add or reference a row in this table.
2. `TBD-confirm` licenses are rejected by CI for any status other than `draft`.
3. Track B corpus entries inherit the license of their source repository and must
   record it in `corpus_index.parquet`.
