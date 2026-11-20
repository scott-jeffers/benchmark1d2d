# Evidence protocol 4.0

Adopted 20 November 2026 ([ADR-0004](../adr/ADR-0004-evidence-not-rankings.md)).
This is the single description of what the suite measures and how it reports
results. Where another document disagrees with this one, this one wins.

The suite reports **evidence**: whether a tool, set up a stated way, is fit
for a stated use. It does not say which model is best. It has no leaderboard,
no rating, no rank on a test, and no number combined across tests.

## 1. Three kinds of evidence

Every case states its kind in its manifest (`evidence`). The kind follows from
`test_class`, and `tools/validate_catalog.py` checks that the two agree. The
kinds answer different questions, are shown in separate columns, and are never
averaged together.

| Kind | The truth | A difference means | `test_class` |
| --- | --- | --- | --- |
| **Verification** | An exact or manufactured solution | The code, or its numerics as configured, is wrong | `verification_analytic`, `verification_manufactured` |
| **Validation** | A measurement, with its uncertainty | Something is wrong: the code, the set-up, the data or the equations | `validation_lab`, `validation_field`, `validation_coupled` |
| **Comparison** | Nothing independent: a pinned reference engine, or states that follow from the inputs | Only that two codes differ | `parity`, `intercomparison`, `regression`, `stress` |

The EA Tests 1–5 are comparison evidence. The original exercise compared
packages with each other, and the suite scores them only on states derived
from the inputs, such as conservation in a closed domain and settled pond
levels. Parity with EPA SWMM 5.2.4 or EPANET 2.2 is comparison evidence: it
shows a code is *different* from the reference, never that either is right.

## 2. Capabilities

Every case also lists the capability groups it gives evidence on
(`capabilities`). The groups are defined, each with a one-line statement of
what it tells a practising engineer, in
[`runner/python/benchmark1d2d/evidence.py`](../../runner/python/benchmark1d2d/evidence.py).
Examples are wetting and drying, shocks and hydraulic jumps, partly full and
surcharged pipes, and sewer–surface exchange. The capability groups are the
rows of every evidence profile.

## 3. Configuration tiers

Every published model has a configuration record,
`configurations/<key>.json`, defined by
[`schemas/v1/configuration.schema.json`](../../schemas/v1/configuration.schema.json).
The record names the engine build, the tier, and every setting that differs
from the engine's default, with the reason for each change.

| Tier | Who sets it up | Rules |
| --- | --- | --- |
| **T0 · Out of the box** | The suite's runners | The engine's defaults, plus only what the case defines: geometry, boundaries, friction, grid. |
| **T1 · Documented guidance** | The suite or anyone | Only changes the developer's *own published* guidance recommends for this kind of flow, each citing its source. The schema refuses a T1 change without a source. |
| **T2 · Expert** | A named person or group | Any setting the engine exposes. One configuration per capability group, unless `per_case_tuning` is declared. Submitted results default to T2. |

A result is always shown with its tier. Results of different tiers were set
up under different rules and are never compared as if alike. The gap between
a model's T0 and T2 results is itself evidence: it shows how much an
engineer's set-up choices matter for that kind of flow.

`defaults_audit` states how far the "changed from default" list has been
checked:

- `automatic`: the written model is compared with the engine's defaults on every run.
- `manual`: the list was checked by hand against the documentation.
- `pending`: only the changes the runner makes on purpose are listed.

The goal is `automatic` for every engine.

## 4. A result's measures

These are unchanged from scoring method 3.0, sections 1–2
([scoring_v3.md](scoring_v3.md)):

- **Accuracy.** Each check is reported as a percent difference from the right
  answer, using the scale in `test_catalog/difference_scales.json`, and also
  in its own units.
- **The result's headline value.** This is the largest percent difference
  over the counted accuracy checks, taken on the finest grid.
- **Reported beside it, never folded in:**
    - conservation errors (%)
    - timing errors (s)
    - NSE
    - the error on every grid and the observed convergence rate with its 90 % range
- **Engine flags.** A run the engine itself flags (more than 10 % of routing
  steps unconverged, or a continuity error above 10 %) is shown with that flag.

The shading of a percent difference on the site exists only to make tables
easier to read; it is not a verdict. A later protocol version replaces it with
per-check *engineering-significance* values, each with a citation (for
example, WaPUG/CIWEM ±0.1 m for sewer levels), reported as "within / beyond".

## 5. What the site shows

- **Evidence profiles** (`profiles.html`, `data/profiles.{json,csv}`). One
  profile per model: one row per capability and one column per kind of
  evidence, with every result and its percent difference. Capabilities with no
  evidence are named, because "not tested" is information too.
- **Each test's page.** Results are listed by tier, then in the model
  registry's order, never by result.
- **Each model's page.** Its configuration (tier, engine pin, settings changed
  from default) and every result.
- **Side by side.** Two models on the tests both ran, each with its tier.
  Nothing is counted or added up.

## 6. Running without people

The suite runs, scores and publishes on its own. People contribute by
*adding* things: a case, a dataset, an adapter or a better configuration. CI
takes it from there.

1. **Watch.** Scheduled jobs check upstream releases against the pins
   (`check-versions.yml`, weekly) and rerun the solver workflows on a schedule.
2. **Run.** The runners write the native models for each configuration and run
   every grid.
3. **Score and check.** Cards are scored by the frozen scorer and hashed. A
   reference that no longer reproduces itself fails the build
   (`make_reference.py --check`).
4. **Publish.** The site and its data exports are rebuilt from the cards, with
   no manual publishing step.
5. **Challenge.** Anyone may submit a configuration. CI reruns it from the
   pinned install. If it does better across its whole capability group, with no
   per-case tuning, it becomes the T2 shown, and the history is kept. Results
   files that CI has not reproduced are shown with that label. There is no
   notice period and no embargo.

Only three decisions are left to people. None of them is on the publishing
path. They are listed in [GOVERNANCE.md](../../GOVERNANCE.md).

## Change log

* **4.0** (20 November 2026). Evidence, not standings:
    - Retires scoring method 3.0 §3–4 (ranks on a test, the OpenHydro rating, head-to-head comparison).
    - Adds the three kinds of evidence, capability groups and configuration tiers.
    - Keeps method 3.0 §1–2 (the measures) unchanged, so existing score cards keep their values.
* **3.0** (18 October 2026). Measurements instead of verdicts ([scoring_v3.md](scoring_v3.md)).
* **2.1** (16 October 2026). Accuracy and convergence judged separately ([scoring_v2.md](scoring_v2.md)).
