# A2A-001 — Thacker parabolic bowl

## Physics

Nonlinear 2D shallow-water planar oscillation in a frictionless parabolic
basin. The free surface remains planar; the shoreline is an exact moving
wet/dry boundary (Thacker 1981).

Analytic generator: `references.thacker.depth_velocity` (alias
`planar_oscillation`).

## Citation

Thacker, W. C. (1981). "Some exact solutions to the nonlinear shallow-water
wave equations." *J. Fluid Mech.*, 107, 499–508.
https://doi.org/10.1017/S0022112081001882

## Status

**candidate** — Phase 5. Demo writers in `examples/demo_solver/solve_2d.py`
(exact + O(dx)-perturbed). Scored by `scripts/run_phase5_2d.py`.
