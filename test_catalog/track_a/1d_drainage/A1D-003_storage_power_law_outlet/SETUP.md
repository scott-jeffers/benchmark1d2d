# Tank emptying through an outlet: what to build

A 100 m² tank 2 m deep empties through an outlet rated Q = 0.5 h^0.5 to a free outfall. Its depth falls along an exact curve.

## Build
- The network in `inputs/network.json`, also given as an EPA SWMM file: `model/A1D-003.inp`.
- Tank: constant plan area 100 m², invert 10 m, starting depth 2 m. Outlet: Q = 0.5 × depth^0.5 (m³/s, depth in m).

## Run
300 s.
