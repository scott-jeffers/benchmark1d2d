# A1D-004 — Pump operating on its head–flow curve

## Physics

A 20 m² wet well receives a constant 0.1 m³/s. A pump with a head–flow curve
(12 m at no flow, 10 m at 0.08 m³/s, 6 m at 0.15 m³/s, linear between points:
SWMM's TYPE3 pump) lifts it into an outfall held at 10 m. At steady state the
pump must pass the inflow, so its head rise is the curve read at 0.1 m³/s,
8.857 m, and the wet well stands at \(10 - 8.857 = 1.143\) m. The run lasts six
hours, about nineteen time constants of the wet well.

## What it checks

That the pump runs on its curve against the head difference between its two
nodes, and that wet-well continuity settles on the operating point.

## Citation

Rossman, L. A. (2017). *SWMM Reference Manual Volume II – Hydraulics*. EPA/600/R-17/111.
