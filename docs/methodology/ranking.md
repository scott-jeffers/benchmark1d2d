# Scores and rankings

OpenHydro Bench reports measurements, not verdicts. Every result is reported
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

The largest percent difference over the test's counted checks. Checks the
catalogue marks informational (the 1 mm leading edge on the Ritter dam break,
say) are shown and not counted. Lower is better. How fast the error shrinks on
finer grids (the convergence rate, with its 90 % range) is reported beside the
score, not counted in it.

## Rank within a test

Results are sorted by percent difference. Two results tie when they differ by
less than 10 % of the larger, or when both are under 0.01 % (the solvers' own
precision). A result's rank is 1 + the number of results clearly better than it
(a tie shares the rank), the rule Chatbot Arena uses for overlapping intervals.

## Overall ranking

* **Head-to-head wins.** For each pair of models and each test both ran,
  the lower score wins and a tie counts half. A model's win rate is its
  share of those comparisons (HELM's mean win rate). Models are never
  compared on tests they did not both run.
* **Error against the field.** On each test, a model's percent difference divided
  by the median model's (differences under 0.01 % count as 0.01 %); the geometric mean
  over its tests. 0.5 means half the typical error (SPEC's geometric mean;
  the PCMDI metrics' median-relative error).
* **Coverage.** A model needs 5 tests in the current view to be ranked;
  others are listed without a rank. Ranks are given overall and per group
  (1D channels, 2D surface, drainage networks, water networks, coupled 1D/2D,
  field data, parity with the reference engines), and for any mix of model
  kinds (production defaults, research codes, submitted results, worked
  examples, previous releases).

Models are ranked by win rate; two models within 2 percentage points share
a rank.

## Run time and machine

Runners record the wall time of each grid's run (writing the model, running
the engine, reading its results back; installing or building the engine is
not timed) in the results file. `score_case` copies it into the score card's
`run` record with the machine: processor, physical and logical cores, memory,
operating system, the runner and the Python version
(`benchmark1d2d.machine`). Times compare models on the same kind of machine
only; GitHub's shared runners also vary from run to run, so the suite shows
time beside accuracy, never as a ranking on its own.
