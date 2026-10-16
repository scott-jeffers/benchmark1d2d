# Filling floodplain hollows: what to build

A 2 × 2 km floodplain with sixteen shallow hollows. A flood enters at one corner and fills them.

Environment Agency 2D benchmark (Néelz and Pender, 2013). Everything is in `inputs/`: the terrain as an ASCII grid (`terrain.asc`, metres), the boundary time series as CSV, the output points (`output_points.csv`) and `case.json` with the settings below.

## Build
- Terrain `inputs/terrain.asc`, the active area in `inputs/active_area.shp`; Manning's n = 0.03; 20 m cells.

## Start
- Dry.

## Boundaries
- Inflow along the 100 m of the west edge between y = 1,900 and 2,000 m, from `inputs/inflow.csv` (minutes, m³/s): 20 m³/s from 10 to 86 min, ramping in 5 min.
- All other edges closed.

## Run
48 hours (172,800 s). Report the depth at the output points every 300 s, and the volume of water in the model at the end.
