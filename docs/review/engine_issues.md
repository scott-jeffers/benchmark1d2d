# Engine issues found by the suite (drafts, not sent)

Two findings from Bob Dickinson's review (17 October 2026, F13 and F14) are about
the engines, not the benchmark. Both were rerun here before drafting. Neither has
been filed; each is written to be pasted as an issue by the maintainer.

---

## 1. HydroCouple/openswmm.engine: dynamic wave does not settle on 5 cm conduits

**Title:** DYNWAVE does not converge on 5 cm conduits where EPA SWMM 5.2.4 does
(HEAD_TOLERANCE 0.00001, MAX_TRIALS 20)

**Engine:** `openswmm==6.0.0a4.dev1` (PyPI wheel), Linux x86-64, Python 3.13.
**Compared with:** EPA SWMM 5.2.4 (`swmm-toolkit` 0.17.0).

**Input.** The SWASHES subcritical bump (benchmark1d2d test A1F-040): a 25 m
frictionless rectangular channel (n = 0.0001) written as a chain of conduits,
one per grid cell, constant inflow upstream, fixed stage downstream, run to
steady state. The three grids give 20, 10 and 5 cm conduits. Input files:
`site/fixtures/inputs/A1F-040/openswmm-dw.zip` (identical to the EPA input),
attached. Reproduce with `python scripts/repro_openswmm_5cm.py WORK
/path/to/python-with-openswmm`.

**What happens.** With the input's own options (`HEAD_TOLERANCE 0.0005`,
`MAX_TRIALS 8`) neither engine converges on the 10 and 5 cm grids. With
`HEAD_TOLERANCE 0.00001` and `MAX_TRIALS 20`, EPA SWMM 5.2.4 converges on all
three grids and OpenSWMM does not on 5 cm:

| Conduits | Options | EPA 5.2.4: steps not converging / routing continuity | OpenSWMM 6 DW | Final depth, mean \|EPA − OpenSWMM\| |
| --- | --- | --- | --- | --- |
| 20 cm | tight | 0.12 % / 0.000 % | 0.12 % / −0.002 % | 0.25 mm |
| 10 cm | tight | 0.36 % / −0.001 % | 0.49 % / −0.002 % | 0.56 mm |
| 5 cm | tight | 0.24 % / −0.008 % | **43.65 % / −12.856 %** | **1.06 m** |
| 5 cm | published | 98.64 % / −39.339 % | 98.56 % / −38.358 % | 1.83 m |

Bob Dickinson measured the same independently: on 5 cm conduits with the tight
options, EPA 1.54 mm from the exact depth and OpenSWMM DW 1.03 m; on 20 and 10
cm the two agree within 0.1 mm.

**Expected.** With the same options, the same iteration as EPA SWMM 5.2.4
(dynwave.c: up to MaxTrials passes until every node is within HeadTol), so the
5 cm run converges as EPA's does. The difference appears only on the shortest
conduits, which suggests the time-step or node surface-area handling for very
short links differs from 5.2.4's.

---

## 2. EPA SWMM (USEPA/Stormwater-Management-Model): documentation of NORMAL_FLOW_LIMITED SLOPE

**Title:** NORMAL_FLOW_LIMITED SLOPE (and the default BOTH) holds flow at
upstream normal flow on short conduits over an undulating bed

**Engine:** EPA SWMM 5.2.4 (`swmm-toolkit` 0.17.0); source `src/solver/dwflow.c`
lines 658–686 at commit 7952ca8.

**What the code does.** With SLOPE or BOTH, a conduit is checked whenever the
depth at its upstream end is below the depth at its downstream end
(`y1 < y2`), and its flow is capped at the upstream normal flow if that is
smaller than the dynamic-wave flow. With FROUDE only, the cap applies when the
upstream Froude number reaches 1.

**Input.** Exact steady subcritical cases (MacDonald et al. 1997 construction):
a 1 km channel 100 km wide (so the hydraulic radius is the depth, as the construction assumes), Manning n = 0.03, constant discharge, the bed
built so a smooth random depth profile is the exact steady solution. Seeds 1–4,
largest Froude number 0.5 and 0.9, 100 and 200 conduits, 12 h of constant
inflow. Generator: `references/macdonald_random.py`; runs:
`python scripts/macdonald_family_swmm.py --dx 10 5`; results:
`docs/review/macdonald_family_swmm524.json`.

**What happens** (mean |depth error| at the interior nodes against the exact
profile, after 12 h):

| Froude cap | Conduits | BOTH (default) and SLOPE | FROUDE |
| --- | --- | --- | --- |
| 0.5 | 100 | 0.0003–0.0021 ft, still moving by up to 1.3 mm in the last hour | 0.0003–0.0005 ft, steady |
| 0.5 | 200 | 0.0091–0.0256 ft, still moving by up to 12 mm in the last hour; up to 10.5 % of steps not converging | 0.0001–0.0002 ft, steady |
| 0.9 | 100 and 200 | 0.0011–0.0021 ft | 0.0011–0.0020 ft |

BOTH and SLOPE give the same numbers in every run, so the SLOPE criterion is
what matters; turning inertial damping off (NONE instead of PARTIAL) does not remove the difference. Bob
Dickinson's runs of the same kind of family (4 seeds × 2 Froude caps × 3 grids
× 4 option sets) found mean errors of 0.005 to 0.37 ft with BOTH and 0.0006 ft
or better with FROUDE.

**Suggested.** Document in the user's manual that SLOPE caps the flow at
upstream normal flow whenever the depth rises downstream, which on short
conduits over an undulating bed holds the model away from the steady solution,
and that FROUDE alone avoids it. Whether the default should change is EPA's
call; the suite will report both.
