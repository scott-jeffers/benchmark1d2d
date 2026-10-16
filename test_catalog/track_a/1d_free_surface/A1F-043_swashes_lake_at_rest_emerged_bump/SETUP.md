# Still lake around an island: what to build

Still water 0.1 m deep around the same hump, whose top sticks out of the water. Nothing should move.

## Build
- A 1D channel 25 m long (x from 0 to 25 m), unit width, no friction.
- Bed: a smooth hump 0.2 m high between x = 8 and 12 m, z = 0.2 − 0.05 (x − 10)², and z = 0 elsewhere. Bed levels are in `model/bed.csv` and, per grid, `model/bed_dx<size>.csv`.

## Start
- Water level 0.1 m (depth = 0.1 − z where positive, dry on top of the hump), at rest.

## Boundaries
- Walls at both ends.

## Run
100 s of simulated time, on three grids: cells of 0.2, 0.1 and 0.05 m.
