# Supercritical flow turned by a wall: what to build

Fast flow meets a straight wall at 15° and is turned along it through an oblique hydraulic jump, a straight shock at 39.6° to the incoming flow.

## Build
- A rectangle 40 m (x) by 30 m (y), flat bed z = 0, no friction.
- A straight wall along the bottom edge (y = 0).

## Start
- Depth 1 m and the incoming velocity everywhere: u = 7.563 m/s, v = −2.027 m/s (7.83 m/s heading 15° towards the wall; Froude number 2.5).

## Boundaries
- Bottom (y = 0): the wall (slip).
- Left (x = 0) and top (y = 30 m): the incoming state held (depth 1 m, u = 7.563, v = −2.027 m/s).
- Right (x = 40 m): free outflow.

## Run
50 s of simulated time (steady by then), on four grids: square cells of 2, 1, 0.5 and 0.25 m.
