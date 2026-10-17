# Scores and rankings

OpenHydro Bench reports measurements, not verdicts. Every result is scored
by how much of the test's error allowance it uses, models are ranked on each
test by that score, and an overall ranking compares models head to head on
the tests they share. The code is `site/ranking.py` (and its browser twin,
`site/static/rankings.js`).

## A result's score: allowance used

Each test defines checks, each with a limit and the reason for it. A check's
*margin* is the observed error divided by its limit (method 2 already stores
it in every score card). A result's score is the largest margin over the
test's accuracy checks:

| Score | Read as |
| --- | --- |
| 0.005 | under 1 % of the allowance (the solver's own precision) |
| 0.34 | uses 34 % of the allowance |
| 2.1 | 2.1 times the allowance |

Lower is better. The allowance is a reference line, not a stamp: 0.99 and
1.01 are nearly the same result. How fast the error shrinks on finer grids
(the convergence rate, with its 90 % range) is reported beside the score on
each test page.

## Rank within a test

Results are sorted by score. Two results tie when they differ by less than
10 % of the larger, or when both are under 1 % of the allowance. A result's
rank is 1 + the number of results clearly better than it (a tie shares the
rank), the rule Chatbot Arena uses for overlapping intervals.

## Overall ranking

* **Head-to-head wins.** For each pair of models and each test both ran,
  the lower score wins and a tie counts half. A model's win rate is its
  share of those comparisons (HELM's mean win rate). Models are never
  compared on tests they did not both run.
* **Error against the field.** On each test, a model's score divided by the
  median model's score (scores under 1 % count as 1 %); the geometric mean
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
