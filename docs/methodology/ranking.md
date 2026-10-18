# Scores and rankings

OpenHydro Bench reports measurements, not verdicts. This is scoring method
3.0, frozen on 18 October 2026; [scoring_v3.md](scoring_v3.md) is the short
specification and its change log. Every result is reported
as a percent difference from the right answer, models are ranked on each test
by that number, and an overall ranking compares models head to head on the
tests they share. There is no limit to pass and no pass or fail. The code is
`site/difference.py` and `site/ranking.py` (and its browser twin,
`site/static/rankings.js`).

## Why not limits

Until October 2026 each check had a limit (an "allowance") and a result was
scored by how much of it it used. Of the 84 checks in the catalogue, four take
their number from outside the suite: the Moriasi et al. (2007) NSE band and
the WaPUG/CIWEM ±0.1 m sewer-verification criterion (A1F-100), the accuracy
Swamee & Jain give for their friction formula (A1P-001), and EPANET's default
convergence criterion (A1P-010). The rest were set by the suite: physical
reasoning, a multiple of the suite's own reference scheme's error (A1F-010),
or a round number. A limit chosen that way turns two nearly equal results into
opposites when they fall either side of it, so the site no longer uses them.
They stay in the catalogue and in every signed score card as the record of
what each check was written against.

## A check's percent difference

Each check measures an error in its own units. It is reported as a percentage
of the quantity it is an error in, from `test_catalog/difference_scales.json`:

| Check measured as | Percent difference |
| --- | --- |
| a percentage already (mass, relative profile error, parity with a reference engine) | as is |
| an NSE | 100 × (1 − NSE): the share of the measured variance the model misses |
| a depth, level, flow or position error | the error over the quantity named for that check: the exact solution's mean depth over the domain (the average the error is taken over), the distance a front travels, a pipe diameter, a normal depth, a storm volume |

The scale for each check, with what it is, is in the scales file and on each
test's technical page.

## A result's score

Checks are of four kinds, and only one is the score:

* **accuracy** (depth, level, velocity, peak, front, parity with a reference
  engine): the score is the largest percent difference over the test's
  counted accuracy checks;
* **conservation** (global mass, continuity, storage balance errors, in %):
  shown in its own column, not folded into the score;
* **timing** (arrival and peak-time errors): shown in seconds, never as a
  percentage of the run length;
* **skill** (NSE): shown as the NSE.

A test with no accuracy check (A2L-EA6A) is scored on its NSE as
100 × (1 − NSE). Checks the catalogue marks informational (the 1 mm leading
edge on the Ritter dam break, say) are shown and not counted. Lower is better.

Each test is scored on its finest grid (`run.scored_dx` in the score card).
Every card also lists the error on each grid and how fast it shrinks (the
convergence rate, with its 90 % range) beside the score, not counted in it.

A relative peak difference is taken against a reference peak of at least 1 cm
for depths (and at least 1 % of the largest peak in the model), so a
millimetre's difference at a nearly dry node is not read as thousands of
percent.

A run the engine itself flags (more than 10 % of routing steps not
converging, or a continuity error above 10 %, from its own report) is shown
and not ranked. Submitted results are shown and not ranked until a maintainer
has re-run them.

## Rank within a test

Results are sorted by percent difference. Two results tie when they differ by
less than 10 % of the larger, or when both are under 0.01 % (the solvers' own
precision). A result's rank is 1 + the number of results clearly better than it
(a tie shares the rank), the rule Chatbot Arena uses for overlapping intervals.

## The OpenHydro rating (the leaderboard)

The leaderboard follows LMArena, the chat-model arena: one rating per model
from head-to-head results, shown with its uncertainty.

* **Every shared test is a match.** On each test two models both ran, the one
  with the smaller percent difference wins; a tie (above) is half a win each.
  Models are never compared on tests they did not both run. On a parity test
  two results also tie when both are within the difference between two
  builds of the reference engine on that test (the cross-build cards), since
  a smaller difference is build noise.
* **Each test counts once.** A test with n models gives n(n − 1)/2 matches;
  each is weighted 2/(n(n − 1)), so a test with twelve models weighs no more
  than one with three.
* **Bradley–Terry fit.** All the matches are fitted with the Bradley–Terry
  model (Hunter's MM algorithm), each model also playing a twentieth of a
  test as a draw against an average model so a model with no wins keeps a
  finite rating. The strengths are shown on the Elo scale: 1000 is the average
  model (geometric mean strength), and 400 points more is ten times the odds
  of being closer on a test.
* **One connected field.** Only models joined to the largest group by shared
  tests are rated; a model that shares no test with it is listed without a
  rating ("no test shared with the rated models").
* **95 % interval.** The tests are redrawn with replacement 200 times (a fixed
  seed, so the page and the build agree to the digit) and the rating refitted
  each time; the interval covers the middle 95 % of those fits.
* **Rank.** 1 + the number of models whose whole interval lies above the
  model's own (LMArena's rule), so models that cannot be told apart share a
  rank. Rows are in rank order, then rating.
* **Coverage.** A model needs 5 tests in the current board to be ranked;
  others are listed without a rank. The overall board rates the physics
  groups (1D channels, 2D surface, drainage networks, water networks, coupled
  1D/2D); parity with a reference engine and field data have boards of their
  own but are not in the overall rating. There is a board for every test group
  (1D channels, 2D surface, drainage networks, water networks, coupled 1D/2D,
  field data, parity with the reference engines) and any mix of model kinds
  (production defaults, research codes, submitted results, worked examples,
  previous releases); by default the leaderboard shows production software,
  research codes.
* **Beside the rating**, as AI benchmark boards show category scores: the
  median percent difference in each test group, the median run time, the
  organisation and the licence. The board is downloadable as
  `data/leaderboard.csv` and `data/leaderboard.json`.

The code is `ranking.rating_board` in `site/ranking.py`, repeated in
`site/static/rankings.js` with the same random numbers and arithmetic.

## Run time and machine

Runners record the wall time of each grid's run (writing the model, running
the engine, reading its results back; installing or building the engine is
not timed) in the results file. `score_case` copies it into the score card's
`run` record with the machine: processor, physical and logical cores, memory,
operating system, the runner and the Python version
(`benchmark1d2d.machine`). Times compare models on the same kind of machine
only; GitHub's shared runners also vary from run to run, so the suite shows
time beside accuracy, never as a ranking on its own.
