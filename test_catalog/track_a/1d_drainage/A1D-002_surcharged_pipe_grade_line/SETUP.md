# Sewer pipes running full: what to build

Five 0.6 m pipes carry 0.3 m³/s to an outfall held 1.5 m above its invert, so every pipe runs full.

## Build
- The network in `inputs/network.json`, also given as an EPA SWMM file: `model/A1D-002.inp`.
- Circular pipes 100 m long, Manning's n = 0.013; outfall water level fixed at 101.5 m.

## Run
2 hours (7,200 s); the flow is steady well before the end.
