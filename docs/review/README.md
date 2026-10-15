# Outside review

Every test in this suite is meant to be checkable by someone who did not
write it. Before a case is **frozen** (counted towards certification) it
needs a recorded review. This folder is what a reviewer needs.

* [`packet.md`](packet.md) — every candidate case: its exact answer and
  source, each check with its limit and the stated reason, which models pass
  and fail, and what still blocks freezing. It is generated from the catalog
  (`python scripts/review_packet.py`) so it always matches it.
* Each case folder (`test_catalog/…/<case>/`) has the manifest, a README with
  the physics, and the inputs; `references/` has the code that computes each
  exact answer, with its tests in `references/tests/`.

## What we ask a reviewer to check

For each case you take on:

1. **The truth.** Is the reference the right answer to the problem as posed
   (equations, boundary conditions, the source cited)? For generated
   references, does the code compute it to the accuracy claimed?
2. **The inputs.** Do the inputs pose that problem, and only that problem?
   Could a reasonable model set-up from these inputs differ from what the
   reference assumes?
3. **The limits.** Is each limit defensible for its stated reason — tight
   enough that a wrong model fails, loose enough that a right one passes on
   the grids given? Is anything gating that should not be, or the reverse?
4. **The results.** Do the published passes and fails look right to you, and
   do the notes on the site describe them fairly?

Points where outside judgment is most wanted now:

* **A1F-010** scores the flood front by volume (the point beyond which the last
  5 % of the released water lies) rather than by the 1 mm depth contour; is
  2.5 m after 60 s the right limit for that measure?
* **A2C-EA tests**: the expected states are derived from the Environment
  Agency specification; the published package results are not used as truth.
* **A1D drainage tests**: the 1 cm depth limits are set from engineering
  relevance, not from the engines' accuracy (the SWMM engines are within
  0.3 mm); should they be tighter?
* **A12 coupled tests**: the water balance is scored at the end of the run
  because SWMM's reported storage disagrees with its own balance while pipes
  are surcharged; is that the right choice?
* **Track B**: whether a 1 % worst-element difference is the right line for
  "matches EPA SWMM 5.2.4" across the corpus.

## How to send a review

Open an issue with the **Case review** template (one issue per case, or one
for a group), or email the maintainers. A review can be short: "checked the
reference and limits of A1D-001 to 005; agree" is useful. Disagreements are
more useful still.

The maintainers record each completed review in the case's manifest
(`"review": {"by": "...", "date": "YYYY-MM-DD", "notes": "..."}`) with a
link to the issue, and the site then shows the case as reviewed. A reviewer
can ask to be named or not.
