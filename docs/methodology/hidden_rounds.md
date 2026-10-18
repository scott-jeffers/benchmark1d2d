# Hidden rounds (planned)

A fixed test can be tuned to: its answer is published, and a results file can
be built from the reference code without running a solver (review F4: a forged
A1F-011 file ranked first). The site therefore holds submitted results
unranked until a maintainer has re-run them, and ranks results the suite's CI
produced itself. Hidden rounds add tests nobody has seen before they run.

## How a round works

1. **Commit.** Before the round, the maintainers choose seeds and publish only
   their commitments, `sha256("<seed>:<salt>")` with a random 128-bit salt per
   seed (`references.macdonald_random.commitment`), in a commit to this
   repository. The salt keeps a small seed from being found by trying them all.
2. **Run.** CI draws each case from its seed (`references.macdonald_random.draw`:
   a seeded random-bed MacDonald channel with a chosen Froude cap; more
   generators to follow), writes the inputs for every engine, runs and scores
   them. Models that take part in a round run inside CI, from the same pinned
   install as every other result.
3. **Reveal.** After the round the seeds and salts are published. Anyone can check them
   against the commitments, regenerate the cases and rerun any result.

## What is in place

* `references/macdonald_random.py`: the generator (exact steady solutions,
  same case on every machine from the same seed; tested in
  `references/tests/test_macdonald_random.py`).
* `scripts/macdonald_family_swmm.py`: the first family run, on EPA SWMM 5.2.4
  under each `NORMAL_FLOW_LIMITED` option (results in
  `docs/review/macdonald_family_swmm524.json`). It already shows what the fixed
  A1F-001 cannot: with the default BOTH, SWMM is held away from the steady
  profile on 200 conduits (up to 0.026 ft), with FROUDE it is not
  (0.0002 ft or better).

## Still to do

A catalog entry for the family (a manifest whose inputs are a seed list, not
files), the runners' support for it, and a round's own board.
