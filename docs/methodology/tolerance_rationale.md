# How tolerances are set

Every scoring criterion carries a `rationale` string. That string appears on
the public test page. A threshold is never a bare number.

## Principles

1. **Verification:** thresholds are in physical units (metres, %, Pa) and are
   justified by mesh spacing, truncation error estimates, or published
   acceptance criteria. Convergence order is always required.
2. **Validation:** thresholds absorb stated measurement uncertainty when
   `include_measurement_uncertainty` is true.
3. **Parity:** thresholds are relative to the pinned reference engine's own
   round-off / continuity behaviour (typically ±0.5–2 % on peak and volume).
4. **Change control:** editing a tolerance requires updating the rationale and
   a reviewer sign-off before the case can return to `frozen`.

## Examples

| Criterion | Threshold | Rationale |
|---|---|---|
| Ritter front position | abs ≤ 2.5 m | Two finest cells; exact front at 1375.8 m for h0=1, x0=1000, t=60, g=9.81 |
| Global mass error | abs ≤ 0.1 % | Conservation property of the continuous equations |
| Track B peak depth | abs ≤ 1 % | Within SWMM 5.2.4 self-consistency band on EXTRAN cases |
