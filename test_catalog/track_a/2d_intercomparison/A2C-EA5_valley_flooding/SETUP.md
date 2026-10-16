# Valley flooding: what to build

A dam-break-like flood of 3,000 m³/s pours into a real valley and runs down it.

Environment Agency 2D benchmark (Néelz and Pender, 2013). Everything is in `inputs/`: the terrain as an ASCII grid (`terrain.asc`, metres), the boundary time series as CSV, the output points (`output_points.csv`) and `case.json` with the settings below.

## Build
- Terrain `inputs/terrain.asc` (British National Grid, metres), the active area in `inputs/active_area.shp`; Manning's n = 0.04; 50 m cells.

## Start
- Dry.

## Boundaries
- Inflow along the short line from (232595, 830480) to (232785, 830290), from `inputs/inflow.csv` (minutes, m³/s): 3,000 m³/s from 10 to 20 min, falling to 0 at 100 min.
- All other edges closed.

## Run
30 hours (108,000 s). Report the depth at the output points every 60 s, and the volume of water in the model at the end.
