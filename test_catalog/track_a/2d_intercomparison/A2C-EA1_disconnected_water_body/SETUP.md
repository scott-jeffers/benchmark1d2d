# Flooding a cut-off pond: what to build

A sloping strip with a hollow behind a low sill. The water level at one end rises, overtops the sill, fills the hollow and then falls back, leaving a pond at the level of the sill.

Environment Agency 2D benchmark (Néelz and Pender, 2013). Everything is in `inputs/`: the terrain as an ASCII grid (`terrain.asc`, metres), the boundary time series as CSV, the output points (`output_points.csv`) and `case.json` with the settings below.

## Build
- Area 700 m × 100 m on `inputs/terrain.asc`; Manning's n = 0.03; 10 m cells (or your usual mesh of similar size).

## Start
- Water level 9.7 m (water only where the ground is below it).

## Boundaries
- West edge (x = 0): water level from `inputs/boundary_level.csv` (minutes, metres): 9.7 m, rising to 10.35 m at 60 min, held until 660 min, back to 9.7 m at 720 min.
- All other edges closed.

## Run
20 hours (72,000 s). Report the depth at the two output points every 60 s, and the volume of water in the model at the end.
