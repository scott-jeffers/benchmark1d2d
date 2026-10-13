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
| `OGL-UK-3.0` | Environment Agency 2D benchmarks (EA1–EA5 / SC120002) | UK Open Government Licence v3.0 — reuse with attribution | https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ ; data ZIP on GOV.UK SC120002 page |
| `TBD-confirm` | CADAM / IMPACT laboratory cases (Toce, idealised city, triangular sill) | CADAM final report: public use only at original researchers' discretion; IMPACT JHR 2007 DVD disseminated data without a clear open-license grant — **blocked** | Morris (2000) CADAM SR 571; Zech & Soares-Frazão (2007) JHR |
| `TBD-confirm` | Malpasset 1959 field case (CADAM/EDF topography) | Original CADAM/EDF DEM redistribution restricted; USACE hosts a derivative dataset without an explicit SPDX license on the download page — **blocked** until terms confirmed | Goutal (1999); Hervouet & Petitjean (1999); USACE LifeSim Malpasset page |
| `synthetic-internal` | Synthetic Track B fixtures used in unit tests | Internal test data; not for certification | `schemas/v1/tests/` |
| `public-domain-EPA` | EPA SWMM 5.2.4 engine binaries | Public domain (US government work) | https://github.com/USEPA/Stormwater-Management-Model/releases/tag/v5.2.4 |

## Confirmation notes (2026-10-13)

- **EA SC120002:** GOV.UK research materials and the FHWA SRH-2D benchmarking report state the UK Environment Agency benchmarking package (Report SC120002 and associated model data) is available under the Open Government Licence. License ID `OGL-UK-3.0`.
- **CADAM / IMPACT lab / Malpasset:** Not promoted past `draft`. Revisit when rights holders publish an SPDX-compatible grant.

## Rules

1. A new test case PR must add or reference a row in this table.
2. `TBD-confirm` licenses are rejected by CI for any status other than `draft`.
3. Track B corpus entries inherit the license of their source repository and must
   record it in `corpus_index.parquet`.
