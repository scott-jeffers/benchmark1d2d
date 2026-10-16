# V&V plan

## Track A — Verification (analytic)

Per ASME V&V 20 and Roache GCI:

1. Run the solver on ≥ 3 systematically refined meshes (fixed Courant).
2. Compute domain-normalised L1 / L2 / L∞ norms against the exact solution
   (L1 = mean |e|, so a scheme of order p gives L1 ∝ dx^p).
3. Estimate the observed order of accuracy `p` from successive levels.
4. Compute the Grid Convergence Index (GCI).
5. Judge with [scoring method 2](scoring_v2.md): *accurate* if every gating
   criterion passes; *converges* if the order fitted through every grid has its
   whole 90 % range at or above `min_observed_order`, fails if the whole range
   is below it, and is *inconclusive* otherwise. The result **passes** only if
   both pass, **fails** if either fails, and is **inconclusive** if it is
   accurate and the grids cannot settle the rate.

A solver that hits 1 % L1 on a fine grid but converges at order 0.4 **fails**.
Errors at round-off on every mesh are **rejected**: a discretisation always
leaves truncation error, so such results are the reference itself.

Every exact solution in `references/` is tested pointwise against the governing
equations, not only against its own initial state.

## Track A — Code inter-comparison

Some widely used benchmarks (Environment Agency Tests 1–5) have neither an exact
solution nor measurements; the original exercise compared packages with each
other. These cases (`A2C-`) gate only on states that follow from the inputs:
mass conservation in a closed domain, and levels fixed by hydrostatics (a pond
settling at its sill crest). Published package results are context, never truth.

## Track A — Validation (lab / field)

Metrics: NSE, KGE, peak error, arrival-time error, CSI (inundation).
Thresholds may set `include_measurement_uncertainty: true` so a model is not
failed for disagreeing with a gauge by less than the gauge's own error.

## Track B — Industry parity

Compare against a pinned reference engine (EPA SWMM 5.2.4, EPANET 2.2; build
and binary SHA-256 recorded). Metrics are computed **per element** (every node
and link) and the worst element is reported: relative peak, conveyed volume,
peak timing. Reference results are produced by `scripts/make_reference.py` and
checked in CI — never hand-edited.
