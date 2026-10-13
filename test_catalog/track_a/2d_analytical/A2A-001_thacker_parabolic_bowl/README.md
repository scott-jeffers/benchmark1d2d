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

## Reference correction (case v2.0.0)

The v1 reference used \(\omega=\sqrt{8gh_0}/L\) and a free surface without the
\(-\eta^2 h_0 \cos^2\omega t / L^2\) term. It satisfied momentum but not mass
conservation (continuity residual ≈ 83 % of \(\partial h/\partial t\)), so every correct solver
would have failed. The corrected solution is

$$z_s = \frac{\eta h_0}{L^2}\left(2x\cos\omega t - \eta\cos^2\omega t\right),\qquad u = -\eta\,\omega\sin\omega t,\qquad \omega=\frac{\sqrt{2gh_0}}{L},$$

verified pointwise against both equations in `references/tests/test_thacker.py`.

## Status

**candidate.** Scored end to end by the first-order finite-volume demo solver
(`examples/demo_solver/swe2d.py`, run by `scripts/run_demo_2d.py`): it passes with
observed order ≈ 0.9. `examples/demo_solver/solve_2d.py` only *samples* the
analytical solution; it is a scorer fixture, and the convergence check rejects it.
