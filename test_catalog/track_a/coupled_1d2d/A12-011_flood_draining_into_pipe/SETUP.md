# Flooded yard draining into a pipe: what to build

A walled yard holds 0.3 m of water that drains down a gully into a pipe. The water above the gully crest drains away; the 5 cm below it stays.

## Build
- **Yard (2D surface):** 30 × 30 m, flat at z = 0, walls all round, Manning's n = 0.02. `model/surface.asc` is the yard as 1 m cells.
- **Sewer (1D):** `model/network.inp` (EPA SWMM). Gully M1 at the centre (x = 15, y = 15 m), crest 0.05 m, connected by a 100 m, 0.3 m pipe to a free outfall.

## Start
- Water level 0.3 m over the whole yard (270 m³). Pipe empty.

## Run
2 hours (7,200 s).
