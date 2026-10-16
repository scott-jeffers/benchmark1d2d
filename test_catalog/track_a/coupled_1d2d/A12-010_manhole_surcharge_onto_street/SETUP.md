# Manhole overflowing onto a street: what to build

A pipe brings 0.5 m³/s to a manhole that has no way out except up. The water spills onto a sloping street and runs down it.

## Build
- **Street (2D surface):** 200 m long and 10 m wide, falling 0.5 % along its length (bed level 1.0 m at x = 0). Manning's n = 0.02. Walls on three sides; the far end (x = 200 m) lets water leave at normal depth. `model/surface.asc` is the street as a grid of 1 m cells.
- **Sewer (1D):** `model/network.inp` (EPA SWMM). A 50 m, 0.6 m pipe from J0 to manhole M1; M1 has no outgoing pipe that carries flow.
- **Link:** manhole M1 sits at x = 25 m, y = 5 m on the street; its rim is at 0.875 m. Use your usual manhole exchange (weir/orifice) with the manhole's plan area 0.283 m².

## Start
Everything empty.

## Boundaries
- 0.5 m³/s into J0, constant.

## Run
30 minutes (1,800 s).
