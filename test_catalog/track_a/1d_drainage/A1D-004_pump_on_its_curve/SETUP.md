# Pump working on its curve: what to build

A wet well receives 0.1 m³/s and a pump lifts it to an outfall held at 10 m. The pump settles where its curve passes exactly the inflow.

## Build
- The network in `inputs/network.json`, also given as an EPA SWMM file: `model/A1D-004.inp`.
- Wet well: 20 m² plan area, invert 0 m, starting depth 1 m. Pump curve (head rise, flow): 12 m / 0, 10 m / 0.08, 6 m / 0.15 m³/s, straight lines between. Outfall level 10 m.

## Run
6 hours (21,600 s).
