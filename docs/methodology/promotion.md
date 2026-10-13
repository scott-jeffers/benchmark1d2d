# Promoting a case: draft → candidate → frozen

Only `frozen` cases count toward certification claims (see `GOVERNANCE.md`).
A case moves up when it meets every rule for the next status. Rules 1–7 are
computed from the manifest and the published score cards
(`benchmark1d2d.catalog.promotion`), so each case page shows exactly what
blocks it. Rule 8 is a person's sign-off.

## draft → candidate

| # | Rule | Why |
|---|------|-----|
| 1 | Data licence verified (not `TBD-confirm`) | We cannot redistribute or publish scores on data we have no right to use. |
| 2 | Every input committed, or fetchable by SHA-256 (nothing `pending`) | Anyone must be able to run the case byte-for-byte. |
| 3 | A reference exists: analytic generator, objective expected states, committed measured data, or pinned-engine results | Without truth there is nothing to score against; such a case is *not scored*, never passed. |
| 4 | Every gating criterion states why its tolerance is what it is | A tolerance without a reason cannot be reviewed or defended. |

## candidate → frozen

| # | Rule | Why |
|---|------|-----|
| 5 | A published run passes the case | Shows the case is passable as specified. |
| 6 | Verification cases: that run's observed order of accuracy meets the minimum (or the manifest explains why order does not apply) | Pointwise agreement at one grid can be luck; convergence cannot. |
| 7 | Two independently written codes pass. For parity cases: a second build of the reference engine (the official EPA binaries, scored by the cross-build job) reproduces the reference | A case that only one code passes may be tuned to that code; a parity reference that depends on the compiler is not a stable target. |
| 8 | A maintainer review is recorded in the manifest (`review: {by, date, notes}`) | Someone other than the author has checked the physics, the reference and the tolerances. |

A frozen case is never edited in place. Any change to its inputs, reference or
tolerances bumps `case_version`, returns it to `candidate`, and is listed in
the case README's history, because scores across versions are not comparable.

## Where the catalog stands

Most candidates are blocked only by rules 7 and 8: each has one passing code
(the demo solvers, EPA EPANET 2.2, or SWMM 5.1.15 for parity) and no review yet.
Drafts are blocked by data licences or by measurements still to be obtained
from their authors. B-RTC-001 additionally fails rule 7: the official SWMM
5.2.4 build and the `swmm-toolkit` build disagree on it beyond tolerance.
