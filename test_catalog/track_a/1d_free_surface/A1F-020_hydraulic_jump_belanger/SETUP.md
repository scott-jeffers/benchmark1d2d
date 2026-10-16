# Standing hydraulic jump: what to build

Fast, shallow water enters a flat channel and jumps up to a slow, deep flow. On a flat frictionless bed the jump should stay where it starts.

## Build
- A 1D channel 100 m long and 1 m wide, flat bed at z = 0, no friction.

## Start
- For x < 50 m: depth 0.2 m, velocity 3.502 m/s (flow 0.7004 m³/s).
- For x > 50 m: depth 0.6141 m, velocity 1.140 m/s (the same flow).

## Boundaries
- Upstream (x = 0): fast inflow, both depth 0.2 m and flow 0.7004 m³/s held (the inflow is supercritical, so both are set).
- Downstream (x = 100 m): depth held at 0.6141 m.

## Run
200 s of simulated time, on four grids: cells of 2, 1, 0.5 and 0.25 m.
