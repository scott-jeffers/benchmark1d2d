# Pollutant spreading in a pipe: what to build

Clean water flows steadily at 0.1 m/s. From t = 0 the water entering at x = 0 carries a tracer at concentration 1. The tracer is carried along and spreads (dispersion coefficient 0.01 m²/s).

## Build
- A 1D pipe or channel 1,000 m long with a uniform velocity of 0.1 m/s.
- Longitudinal dispersion coefficient D = 0.01 m²/s. No decay.

## Start
- Concentration 0 everywhere.

## Boundaries
- Inflow (x = 0): concentration held at 1 from t = 0.
- Outflow (x = 1,000 m): free (zero gradient).

## Run
3,600 s of simulated time, on four grids: cells of 4, 2, 1 and 0.5 m.
