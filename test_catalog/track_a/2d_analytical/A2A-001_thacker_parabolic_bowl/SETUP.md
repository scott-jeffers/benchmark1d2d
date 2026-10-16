# Water sloshing in a bowl: what to build

A planar water surface rocks back and forth in a round, bowl-shaped basin (Thacker, 1981); the shoreline moves up and down the sides.

## Build
- A square area from −1.1 to +1.1 m in both directions, no friction.
- Bed: a paraboloid z = 0.1 (x² + y²) − 0.1 (lowest point −0.1 m at the centre, z = 0 at radius 1 m). `model/bed_dx<size>.asc` gives it on each grid.

## Start
- Water level z_s = 0.005 (2x − 0.05) m where it is above the bed (depth = level − bed, dry elsewhere), at rest. The surface is tilted, so it starts moving at once. `model/initial_depth_dx<size>.asc` gives the starting depth on each grid.

## Boundaries
- Walls all round (the water never reaches them).

## Run
1 s of simulated time, on four grids: square cells of 0.1, 0.05, 0.025 and 0.0125 m.
