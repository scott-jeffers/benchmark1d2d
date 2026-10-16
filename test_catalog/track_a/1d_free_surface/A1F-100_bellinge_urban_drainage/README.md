# A1F-100 — Bellinge urban drainage (field validation)

The real combined sewer system of Bellinge, Odense (Denmark). It covers 1.7 km² and has about 1,000 nodes and 1,000 links, with basins, pumps, weirs and control rules. Pedersen et al. (2021, *ESSD* 13, 4779–4798) published it with an EPA SWMM model and years of level-meter records.

## Licence: read before using

| DTU item | Content | Licence | Used |
|---|---|---|---|
| 2 | Sensor data | CC BY 4.0 | the measured levels (`reference/levels.parquet`) |
| 3a | Rain gauge data | **CC BY-NC 4.0 (non-commercial)** | no |
| 3b | Radar and meteorological station | CC BY 4.0 | no (not needed) |
| 7 | Models (SWMM, MIKE URBAN) | CC BY 4.0 | the SWMM model and its rain-gauge file |

The case uses only CC BY items so commercial vendors can run it.

## The test

- **Model.** `BellingeSWMM_v021_nopervious.inp` from item 7 (SHA-256 of the zip in the manifest), run unchanged except for its run dates. `scripts/run_bellinge.py` writes each event's dates and a one-minute report step into a copy. The model's own rain-gauge file, `rg_bellinge_Jun2010_Aug2021.dat`, drives every run.
- **Storms.** There are eight. Each is the most intense 10-minute rainfall or one of the largest daily totals in the model's gauge series after the level meters start in August 2010, and the list includes the model's own event of 29 June 2012. Each run starts 12 hours before the storm's day as a warm-up, and its levels are scored over the next 48 hours.
- **Level meters.** There are seven, each read at the model node it sits in.

  | Meter | Model node |
  |---|---|
  | G71F04R_Level2 | G71F04R |
  | G71F05R_LevelBasin | G71F05R |
  | G71F05R_LevelInlet | G71F05R_skyl |
  | G71F06R_LevelInlet | G71F06R |
  | G71F68Y_LevelPS | G71F68Y |
  | G73F010 | G73F010 |
  | G80F13P_LevelPS | G80F13P |

  Not used: G71F04R Level1 (the same basin as Level2, with fewer records), G71F05R_position (a gate) and G71F68Yp1 (a pump).
- **Reference.** `reference/levels.parquet` holds 138,154 one-minute levels, in m above DVR90, for each meter and storm with a whole record (90 % or more). Build it with `scripts/bellinge.py extract` and then `scripts/bellinge.py reference`.
- **Floor.** A meter does not read below its own floor, taken as the lowest level it recorded in any of the storms. The scorer reads the model's level the same way, as max(model, floor).

## Criteria

Both criteria were set before any run, from published standards rather than from a baseline. Both are judged on the median gauge record (one meter on one storm).

- **Level NSE ≥ 0.5.** This is the "satisfactory" band of Moriasi et al. (2007). A record where the meter moved less than three times its accuracy (0.06 m) is not scored for NSE.
- **Peak level within ±0.1 m.** This is the depth criterion for verifying sewer models against measurements (WaPUG 2002; CIWEM UDG 2017 Code of Practice).

The published model is uncalibrated (ESSD paper §4), so this case judges the model and the engine together. A failure here can come from the model's set-up as much as from the engine; the parity comparison on the same model (the Bellinge tier on the parity page) isolates the engine.

## History

- 1.0.0: first scored version. The rainfall is the model's own gauge file rather than the radar. Peak levels are judged in metres, not per cent.
- 0.1.0: draft.
