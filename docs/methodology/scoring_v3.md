# Scoring method 3.0

Frozen on 18 October 2026. Every page of the site prints the method version in
its footer and on each result. A change to anything below is a new version,
listed in the change log at the end, and the site is rebuilt under it; old
score cards keep their measured values, which do not depend on the method.

The full explanation, with the reasons, is [ranking.md](ranking.md). The code
is `site/difference.py` (the score) and `site/ranking.py` (ranks and the
rating), with a browser twin in `site/static/rankings.js`.

## 1. A check's value

Each check in a test manifest measures one error. The score card stores the
measured value (`criteria_results[].observed`). The manifest's `threshold` is
kept as the record of what the check was first written against; it is not
used.

| Kind | Metrics | Reported as |
| --- | --- | --- |
| accuracy | L1, L2, Linf, peak_error, relative_peak, relative_volume, relative_head_loss, front_position_error, volume_front_error, expected_state_error | percent difference: as is when already in %, else 100 × \|error\| ÷ the scale in `test_catalog/difference_scales.json` |
| conservation | global_mass_error, continuity_error, storage_balance_error | % (as measured) |
| timing | timing_error, arrival_time_error | seconds |
| skill | NSE | the NSE |

`relative_peak` on depths divides by max(reference peak, 1 % of the largest
reference peak, 1 cm).

## 2. A result's score on a test

The largest accuracy percent difference over the counted checks (`gating`
true). With no accuracy check, 100 × (1 − NSE); with neither, the largest
conservation error. Scored on the finest grid (`run.scored_dx`).

Bands, for colour only: under 0.1, 1, 3, 10, 30 %, and over 30 %.

## 3. Rank on a test

Sorted by score. Two results tie when they differ by less than 10 % of the
larger, or both are under 0.01 %; on a parity test, also when both are within
the difference between two builds of the reference engine (its noise floor). Rank = 1 + the
number of results clearly better.

Not ranked (shown): a run the engine flags (over 10 % of routing steps not
converging, or a continuity error over 10 %), and submitted results not yet
re-run by a maintainer.

## 4. The OpenHydro rating

| Setting | Value |
| --- | --- |
| model | Bradley–Terry, Hunter's MM algorithm, Elo scale (1000 = geometric mean strength, 400 points = 10× odds) |
| a match | every pair of models on a test both ran; tie as in §3 = half a win each |
| weight | 2 / (n(n − 1)) per match on a test with n models (each test counts once) |
| prior | 0.05 of a test drawn against an average model |
| groups rated overall | 1D channels, 2D surface, drainage, water networks, coupled 1D/2D |
| field | the largest set of models connected by shared tests |
| minimum | 5 tests |
| interval | 95 %, 200 bootstrap redraws of the tests, mulberry32 seed 20261017 |
| rank | 1 + the number of models whose interval lies wholly above |

## Change log

* **3.0** (18 October 2026, after Bob Dickinson's review): measurements
  instead of verdicts; percent difference with no limit; conservation,
  timing and NSE reported beside the score; 1 cm floor on relative peak
  depths; each test weighted once in the rating; parity and field data out
  of the overall rating; engine-flagged runs and unverified submissions not
  ranked; parity ties at the cross-build spread.
* **2.1** (16 October 2026): accuracy and convergence judged separately; a
  result passed when every check was within its limit, and was verified when
  it also converged at the design order ([scoring_v2.md](scoring_v2.md)).
* **1** (until 16 October 2026): one verdict per result, accuracy and
  convergence together.
