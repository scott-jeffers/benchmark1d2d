# Flood spreading over a floodplain: what to build

A flood enters the middle of one edge of a flat, rough floodplain and spreads out.

Environment Agency 2D benchmark (Néelz and Pender, 2013). Everything is in `inputs/`: the terrain as an ASCII grid (`terrain.asc`, metres), the boundary time series as CSV, the output points (`output_points.csv`) and `case.json` with the settings below.

## Build
- A flat area 1,000 m × 2,000 m at z = 0 m; Manning's n = 0.05; 5 m cells.

## Start
- Dry.

## Boundaries
- Inflow along the 20 m of the west edge between y = 990 and 1,010 m, from `inputs/inflow.csv` (minutes, m³/s): ramp to 20 m³/s at 60 min, held to 240 min, back to 0 at 300 min.
- All other edges closed.

## Run
5 hours (18,000 s). Report the depth and velocity at the output points every 20 s, and the volume of water in the model at the end.
