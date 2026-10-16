# Backwater up a sewer: what to build

Twenty 1.2 m pipes carry 0.6 m³/s to an outfall held 1 m above its invert, so the water backs up through the manholes.

## Build
- The network in `inputs/network.json`, also given as an EPA SWMM file: `model/A1D-005.inp`.
- Circular pipes 50 m long, slope 0.1 %, Manning's n = 0.013; outfall water level fixed at 21.0 m.

## Run
6 hours (21,600 s); the flow is steady well before the end.
