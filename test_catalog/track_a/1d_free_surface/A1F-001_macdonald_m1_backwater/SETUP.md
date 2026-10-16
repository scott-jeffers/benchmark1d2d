# Gentle backwater in a channel: what to build

Steady flow down a 1 km channel over a gently curving bed, chosen so that the water depth along it is known exactly.

## Build
- A straight rectangular channel, 1,000 m long and 10 m wide.
- Treat it as wide: friction acts on the bed only, not the side walls (hydraulic radius = depth).
- Bed level: `model/bed.csv` (x, z every metre; z = 0 m at the upstream end). The bed for each grid is in `model/bed_dx<size>.csv`.
- Manning's n = 0.03 everywhere. No other losses.

## Start
Any starting state; run until the flow is steady.

## Boundaries
- Upstream (x = 0): a constant inflow of 2.0 m³/s.
- Downstream (x = 1,000 m): a fixed depth of 0.748 m (water level = bed level there + 0.748 m).

## Run
One hour (3,600 s) of simulated time, on four grids: cells of 40, 20, 10 and 5 m.
