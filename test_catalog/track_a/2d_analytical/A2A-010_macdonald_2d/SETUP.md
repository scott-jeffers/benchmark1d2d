# Steady flow over a shaped bed: what to build

Steady flow with friction down a 1 km × 100 m channel whose bed is shaped so the depth profile is known exactly (the 2D version of A1F-001).

## Build
- A rectangle 1,000 m long (x) and 100 m wide (y). Walls along both long sides (no friction on the walls).
- Bed: `model/bed_dx<size>.asc` for each grid (the bed varies along x only; `model/bed.csv` gives it every metre).
- Manning's n = 0.03.

## Start
- Depth 0.748 m everywhere, velocity 0.2 / 0.748 = 0.267 m/s along the channel.

## Boundaries
- Upstream (x = 0): inflow of 0.2 m³/s per metre width (20 m³/s in all), across the whole width.
- Downstream (x = 1,000 m): depth held at 0.748 m.

## Run
1 hour (3,600 s), on four grids: square cells of 50, 25, 12.5 and 6.25 m.
