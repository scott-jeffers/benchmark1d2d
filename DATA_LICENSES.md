# Data license register

Every dataset in the catalog **must** have an entry here. CI refuses manifests
whose `provenance.license` is missing or not listed in this register.
Datasets marked `TBD-confirm` may only appear with `status: draft` and cannot
be promoted to `candidate` or `frozen` until a real license is recorded.

| License ID | Dataset / corpus | Terms summary | Source |
|---|---|---|---|
| `Apache-2.0` | benchmark1d2d code & schemas | Apache Software License 2.0 | [LICENSE](LICENSE) |
| `Unlicense` | 1729-SWMM5-Models (SWMMEnablement) | Public domain dedication | https://github.com/SWMMEnablement/1729-SWMM5-Models |
| `Unlicense` | 1729-SWMM5-Models-2030 (Dickinson) | Public domain dedication | https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030 |
| `Unlicense` | openswmm.engine.benchmarks (HydroCouple) | Public domain dedication | https://github.com/HydroCouple/openswmm.engine.benchmarks |
| `CC-BY-4.0` | Bellinge urban drainage dataset — items 1, 2, 3b, 4–9 (assets, sensors, radar/met rainfall, drawings, CCTV, terrain, models, scripts) | Creative Commons Attribution 4.0 | https://doi.org/10.11583/DTU.c.5029124 |
| `CC-BY-NC-4.0` | Bellinge item 3a — rain gauge data | Creative Commons Attribution-NonCommercial 4.0 — **not used by any case** (would bar commercial vendors) | https://doi.org/10.11583/DTU.12509774 |
| `analytic-public` | Analytic reference solutions (Ritter, Stoker, Thacker, MacDonald, Joukowsky, …) | Equations from published literature; generators under Apache-2.0 | See per-test README |
| `OGL-UK-3.0` | Environment Agency benchmark **input data** (`Benchmarking_Model_Data.zip`, Tests 1–7, 2010 specifications) | UK Open Government Licence v3.0 — reuse with attribution. Covers the archive only: the SC120002 report text and its figures are "All rights reserved … reproduced with prior permission" | https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ ; https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm |
| `TBD-confirm` | CADAM / IMPACT laboratory cases (Toce, idealised city, triangular sill) | CADAM final report: public use only at original researchers' discretion; IMPACT JHR 2007 DVD disseminated data without a clear open-license grant — **blocked** | Morris (2000) CADAM SR 571; Zech & Soares-Frazão (2007) JHR |
| `TBD-confirm` | Malpasset 1959 field case (CADAM/EDF topography) | Original CADAM/EDF DEM redistribution restricted; USACE hosts a derivative dataset without an explicit SPDX license on the download page — **blocked** until terms confirmed | Goutal (1999); Hervouet & Petitjean (1999); USACE LifeSim Malpasset page |
| `synthetic-internal` | Synthetic Track B fixtures used in unit tests | Internal test data; not for certification | `schemas/v1/tests/` |
| `public-domain-EPA` | EPA SWMM 5.2.4 / EPANET 2.2 engines and EPA example networks (e.g. EPANET Net1) | Public domain (US government work) | https://github.com/USEPA/Stormwater-Management-Model/releases/tag/v5.2.4 |

## Confirmation notes (2026-10-13)

- **EA SC120002 (checked 2026-10-13):** the GOV.UK page states "All content is available under the Open Government Licence v3.0, except where otherwise stated". The data archive (SHA-256 `388c2789…`) and its 2010 test-specification PDFs carry no other terms, so the inputs are `OGL-UK-3.0`. The SC120002 report PDF *does* state otherwise ("All rights reserved. This document may be reproduced with prior permission of the Environment Agency"), so package results digitised from its figures need EA permission before they are published here.
- **Bellinge (checked 2026-10-13 via the figshare API):** every item is CC BY 4.0 except 3a (rain gauges), which is CC BY-NC 4.0.
- **Journal-only laboratory data (Weber 2001, Bergant 1999, Rubinato 2017):** no open data licence found; cases stay `draft` under `TBD-confirm` until the authors grant terms.
- **CADAM / IMPACT lab / Malpasset:** Not promoted past `draft`. Revisit when rights holders publish an SPDX-compatible grant.

## Rules

1. A new test case PR must add or reference a row in this table.
2. `TBD-confirm` licenses are rejected by CI for any status other than `draft`.
3. Track B corpus entries inherit the license of their source repository and must
   record it in `corpus_index.parquet`.
