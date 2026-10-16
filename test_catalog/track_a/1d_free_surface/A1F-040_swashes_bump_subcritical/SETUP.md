# Calm flow over a hump: what to build

Steady, slow (subcritical) flow over a small hump in the bed; the water dips over the crest.

## Build
- A 1D channel 25 m long (x from 0 to 25 m), unit width, no friction.
- Bed: a smooth hump 0.2 m high between x = 8 and 12 m, z = 0.2 − 0.05 (x − 10)², and z = 0 elsewhere. Bed levels are in `model/bed.csv` and, per grid, `model/bed_dx<size>.csv`.

## Start
- Water level 2.0 m everywhere, at rest.

## Boundaries
- Upstream (x = 0): constant inflow of 4.42 m³/s per metre width.
- Downstream (x = 25 m): depth held at 2.0 m.

## Run
300 s of simulated time (the flow is steady by then), on three grids: cells of 0.2, 0.1 and 0.05 m.
