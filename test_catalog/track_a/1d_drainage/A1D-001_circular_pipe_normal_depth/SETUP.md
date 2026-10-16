# Sewer pipes running part full: what to build

Three separate lines of ten 1 m pipes on a 0.2 % slope carry steady flows that fill them to about a quarter, a half and three quarters.

## Build
- The network in `inputs/network.json`, also given as an EPA SWMM file: `model/A1D-001.inp`.
- Circular pipes, Manning's n = 0.013, each line ends at a free (normal-depth) outfall.

## Run
6 hours (21,600 s); the flow is steady well before the end.
