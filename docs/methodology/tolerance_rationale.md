# How tolerances are set

> **Scoring method 2.1 (16 October 2026)** decides every verdict: a result
> passes when every check is within its limit, each check shows its share of
> the limit, and the convergence rate, fitted through every grid with its
> 90 % range, decides the separate *verified* label. See [scoring method 2](scoring_v2.md) and the
> [page that shows every result both ways](https://scott-jeffers.github.io/benchmark1d2d/scoring-review.html).
> The limits below are unchanged, except A1F-010's front (9.8 m since v3.0.0).

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
| Joukowsky observed order | ≥ 0.4 (design 0.5) | A discontinuity in a linear wave equation: a p-th order fixed-grid scheme converges in L1 only as dx^(p/(p+1)), so 0.5 for first-order schemes |
| EA Test 2/4/5 mass | abs ≤ 0.1 % | Closed domain, dry start: stored volume must equal the inflow integral |
| EA Test 1 pond level | abs ≤ 0.02 m | Hydrostatics: the pond settles at the 10.25 m sill crest |

## Expectations come from theory, not from results

A tolerance or expected order is set from analysis of the problem (regularity of
the solution, design order of a reasonable scheme), never tuned to a particular
solver's output. When an expectation is found to be wrong, the case's major
version is bumped and the reason is written into its description, because
scores before and after are not comparable (example: A1P-020 v2.0.0).

## Cross-build sensitivity (Track B)

Two builds of the same engine version are not guaranteed to agree. For EPA SWMM
5.2.4 the official win64 build and the `swmm-toolkit` 0.17.0 build agree exactly
on EXTRAN Example 1, but differ on the control-rule case B-RTC-001 by −3.7 %
peak depth and a 92,400 s peak-timing shift. A tolerance tighter than the
spread between reference builds cannot separate a correct candidate from a
wrong one, so B-RTC-001's ±2 % / ±120 s criteria are under review (see the
case README).

