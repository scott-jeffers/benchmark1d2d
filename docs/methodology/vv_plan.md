# V&V plan

The suite gathers three kinds of evidence ([evidence protocol 4.0](evidence.md)).
Each kind has its own truth and its own rules, and they are never averaged.

## Verification (exact or manufactured truth)

Per ASME V&V 20 and Roache's GCI:

1. Run the solver on ≥ 3 systematically refined meshes (fixed Courant).
2. Compute domain-normalised L1 / L2 / L∞ norms against the exact solution
   (L1 = mean |e|, so a scheme of order p gives L1 ∝ dx^p).
3. Estimate the observed order of accuracy `p`, fitted through every grid with
   its 90 % range.
4. Compute the Grid Convergence Index (GCI).
5. Report the error on every grid and the observed order beside the result's
   percent difference. A low error on one grid with an observed order well
   below the scheme's design order is shown as such: pointwise agreement at
   one grid can be luck; convergence cannot.

Errors at round-off on every mesh are flagged: a discretisation always leaves
truncation error, so such results are the reference itself.

Every exact solution in `references/` is tested pointwise against the
governing equations, not only against its own initial state.

## Validation (measured truth, with uncertainty)

Metrics: NSE, KGE, peak error, arrival-time error, CSI (inundation), and the
fraction of observations matched within their uncertainty. Bias and scatter
are reported separately.

- A model is not read as missing an observation by less than that
  observation's own uncertainty (`include_measurement_uncertainty: true`).
- **Engine validation** runs a fixed, published model unchanged (Bellinge's
  SWMM file). It isolates the engine but mostly measures the model.
  **Practice validation**, where teams build their own model from raw data,
  is planned.
- Field cases split events into calibration and scored sets, declared before
  any run. Where a long record exists, the most recent data is held back
  until a round closes.
- Every field case reports the spread between engines beside the miss against
  the observations. Engines that agree with each other but not with the
  gauges point at the model or the data, not the engine.

## Comparison (no independent truth)

- **Reference-engine parity.** Results are compared with a pinned engine
  (EPA SWMM 5.2.4, EPANET 2.2; build and binary SHA-256 recorded). Metrics
  are computed **per element** (every node and link) and the worst element
  is reported: relative peak, conveyed volume, peak timing. References come
  from `scripts/make_reference.py` and are checked in CI, never hand-edited.
  The difference between two builds of the reference engine itself (the
  cross-build job) is reported as each parity test's noise floor.
- **Code inter-comparison** (Environment Agency Tests 1–5). Results are
  scored only on states that follow from the inputs: mass conservation in a
  closed domain, and levels fixed by hydrostatics. Published package results
  are context, never truth.
