# Overflow and return: what to build

A storm hydrograph overwhelms a small outgoing pipe; the manhole surcharges onto a shallow hollow, and the water returns down the manhole when the storm passes.

## Build
- **Hollow (2D surface):** 20 × 20 m, walls all round, falling 1 % towards its centre (lowest point z = 0 at x = 10, y = 10 m). Manning's n = 0.02. `model/surface.asc` is the hollow as 1 m cells.
- **Sewer (1D):** `model/network.inp` (EPA SWMM). Inflow pipe J0 → M1 (50 m, 0.5 m), outgoing pipe M1 → free outfall (100 m, 0.25 m). Manhole M1 at the hollow's centre, rim at 0 m.

## Boundaries
- Inflow at J0: 0 at t = 0, rising linearly to 0.3 m³/s at 10 min, back to 0 at 20 min (180 m³ in all).

## Run
3 hours (10,800 s).
