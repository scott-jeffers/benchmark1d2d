# Scoring method 2

**Status:** adopted on 16 October 2026 for rules R1–R3, R5 and R6. Every
verdict on the site and in every new score card follows them. R4 (five grids)
and R7 (limits set by a stated rule) are the next step. They change the
tests' inputs, so they will come with new major versions of the tests and a
re-run of every solver.

* Code: `runner/python/benchmark1d2d/scoring/method_v2.py`, tested in
  `runner/python/tests/test_method_v2.py`.
* The scorer writes `scoring_method: "2"`, `verdict`
  (`pass`, `fail`, `inconclusive`), `judgement` (the two verdicts and the
  worst margin) and a `margin` on every criterion into each new score card.
  `passed` is true only for `pass`.
* A card scored under method 1 is re-judged when the site reads it. Its
  inputs are in the card (criterion values, errors per grid), so nothing is
  re-run, and the signed file itself is not altered.
* The [scoring page](https://scott-jeffers.github.io/benchmark1d2d/scoring-review.html)
  keeps the record: every result under both methods, the convergence rate of
  each with its range, the results whose verdict changed and the near misses.

The numbers below are from the 154 results published on 16 October 2026
(Track A and Track B).

## Why change

Method 1 gave each result one verdict, pass or fail. A result
passes when every gating check is within its limit **and**, where the test
has a grid study, the observed order of convergence reaches the test's
minimum (0.8 where a first-order scheme gives 1). The approach follows
ASME V&V 20 and Roache's grid convergence practice, and it is right for what
it was built to answer: does the code solve its equations correctly?
Applying it to the results exposed five problems.

1. **The accuracy limits seldom decide; the convergence rate does.**
   16 of the 55 failures are *convergence only*: every check is within its
   limit on every grid. On A1F-011 (Stoker), the limit is 50 mm, while the
   models that converge are within 0.3–1.4 mm. Eight models fail it on the
   rate alone.
2. **The convergence rate is one noisy number, cut at a cliff.** The rate is
   the mean of the two finest pairwise orders. On A1F-011, ANUGA's errors run
   1.38, 1.38, 0.42 and 0.39 mm, coarse to fine. Its pairwise orders are 0.11
   and 1.72, which average to 0.92, so it passes. LISFLOOD-FP FV1 converges
   steadily at 0.76–0.81, averages 0.78, and fails. A least-squares fit
   through every grid, with its 90 % interval, shows the 0.8 line inside the
   interval for 27 of the 75 results with a grid study. Three or four grids
   cannot pin a rate to ±0.1.
3. **A solver's own precision reads as non-convergence.** HEC-RAS 1D stores
   cross-section elevations to 0.001 ft (0.3 mm)
   ([HEC-RAS notes](../hecras.md)). Its A1F-001 error is 0.1 mm on every
   grid, a hundredth of the 1 cm limit, and it fails because that error
   cannot fall.
4. **A verdict says which side of the line, not how far.** Among the Track A
   failures, six are within twice their limit: SWMM + ANUGA fails A12-010 on 0.56 % against
   0.5 %. Another 22 are more than ten times over: SWMM is 1.5 m out on the
   SWASHES bump, against a 5 mm limit. Both show the same "Fails".
5. **One word answers two questions.** An engineer asks whether the model is
   accurate enough at the resolution they would use. Code verification asks
   whether it converges the way a correct scheme must. A model can be 1 mm
   from the exact answer and converge slowly, or converge cleanly to the
   wrong answer.

## The rules

**R1. Two verdicts.**
* *Accurate*: every gating check within its limit.
* *Converges*: the grid study, judged as in R3.
  * Tests without a grid study (conservation states, networks, parity) show
    "not studied".

**R2. Margins.** Every check reports |observed| / limit. A results table can
then be sorted by how close each check came, and a near miss can be told
from a gross failure. The pass/fail label is derived from the margin, so it
stays.

**R3. The convergence rate with its uncertainty.**
* *p* is the least-squares slope of log error against log grid spacing,
  over all levels.
* Its two-sided 90 % interval uses Student's t with n − 2 degrees of
  freedom.
* Verdict:
  * **pass** if the whole interval is at or above the minimum order;
  * **fail** if the whole interval is below it;
  * **inconclusive** otherwise.
* Errors at round-off on every grid still fail, as now: such results are
  the reference itself.

**R4. Five grids per grid study.** With three grids the fit has one degree
of freedom and t = 6.3; ANUGA's A1F-042 interval runs from −1.2 to 3.1.
With five grids, t falls to 2.4. Nine of the inconclusive rates today come
from tests run on three grids (the SWASHES set).

**R5. Declared precision floors.**
* A solver may declare the precision to which it stores or reports a
  quantity, with evidence.
* When the finest grid's error is within 3× that precision, the rate is
  reported but does not decide the verdict ("at its precision").
* The only declaration today is HEC-RAS 1D, at 0.3 mm on levels. HEC-RAS 2D
  is left out because there is no evidence for it yet.

**R6. Overall verdict.**
* **Fails** if *Accurate* fails or *Converges* fails.
* **Inconclusive** if *Accurate* passes and *Converges* is inconclusive.
* **Passes** otherwise.

**R7 (separate decision). Accuracy limits by a stated rule.**
* The current error limits are round numbers, 10–400× looser than the error
  of a plain first-order scheme on the finest grid. A1F-011: 50 mm against
  the suite's demo solver's 0.31 mm. A2A-001: 20 mm against 0.05 mm.
* So *Accurate* tests little beyond "not broken".
* Candidate rule: limit = k × the finest-grid error of a first-order
  reference scheme, k = 5. Front positions keep the two-cell rule they
  already use.
* On today's results, k = 5 would newly fail at most one current pass
  (A1F-001: the reference there converges at second order, see below).
* The rule needs a genuinely first-order reference for every test.
  * The demo solver is first order on the dam breaks and the 2D analytic
    cases.
  * On A1F-001 the demo integrates the backwater equation at second order,
    so it cannot serve there.
  * The SWASHES tests have no reference run yet.

## What moved

Method 2 against method 1:

| Method 1 | → Passes | → Inconclusive | → Fails |
|---|---|---|---|
| Passes (99) | 87 | 12 | 0 |
| Fails (55) | 1 | 8 | 46 |

* No result went from pass to fail, or from fail to pass, except HEC-RAS 1D
  on A1F-001 (R5).
* The twelve passes that became inconclusive are rates whose interval
  straddles the minimum. Examples: ANUGA on A1F-011 (0.03–1.42), and five
  SWASHES results on three grids.
* The eight fails that became inconclusive have steady rates just under the
  minimum, or erratic ones. Examples: LISFLOOD-FP FV1 on A1F-011
  (0.77–0.80), and OpenSWMM 6 finite volume on A1F-001 (0.73–0.85).
* The full list, with the reason for each, is on the scoring page.

## Decisions taken (16 October 2026)

1. R1–R3, R5 and R6 adopted as one change. The tests' inputs, exact answers
   and limits are unchanged, so no test changed version. The method is
   recorded on each score card instead (`scoring_method`), and method-1 cards
   are re-judged when read.
2. Confidence: 90 % two-sided.
3. *Inconclusive* is a third, grey state on badges, in counts and in the
   results table. It is not counted with passes.
4. Precision floors (R5) may be declared with a published statement by the
   developer or a reproducible test in this repository. The only one today is
   HEC-RAS 1D, at 0.3 mm on levels.
5. Next step, as a separate versioned change: five grids per grid study (R4),
   and R7 limits where a first-order reference exists. Extra coarse levels
   cost little; an extra fine level costs about 4× the current finest run in
   1D and 8× in 2D. Every Track A test with a grid study gets a new major
   version, and every solver re-runs.
