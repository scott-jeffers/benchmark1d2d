# A1F-100 — Bellinge urban drainage (field validation, draft)

Real combined sewer system in Bellinge, Odense (Denmark): 1.7 km², 13 level meters, 1 flow meter, 4 pump-power sensors, up to 10 years of data, plus published MIKE URBAN and EPA SWMM models (Pedersen et al., 2021, *ESSD* 13, 4779–4798).

## Licence — read before using

| DTU item | Content | Licence |
|---|---|---|
| 2 | Sensor data | CC BY 4.0 |
| 3a | Rain gauge data | **CC BY-NC 4.0 (non-commercial)** — not used |
| 3b | Radar and meteorological station | CC BY 4.0 |
| 7 | Models (SWMM, MIKE URBAN) | CC BY 4.0 |

The case uses only CC BY items so commercial vendors can run it.

## What remains (why this is a draft)

1. Fetch the SWMM model (file 30592830, MD5 `fea9026c…`) and record its SHA-256.
2. Choose validation events and extract level-meter series into `reference/levels.parquet`.
3. Set tolerances from an uncalibrated-model baseline and the level-meter accuracy.
