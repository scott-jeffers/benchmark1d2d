# Getting every model to work well: expert set-ups

November 2026. Every result over 5 % on the site was looked at with one question: is the error
the software, or the way the suite set the model up? Where a better set-up exists it is now a
proposed set-up in `setups/`, re-run by the suite and shown **beside** the suite's own result
(nothing is replaced). Where no setting helps, the reason is given below.

The numbers are the score: the largest error over a test's checks, as a percentage of its
accuracy band (100 % = at the edge of the band). "Before" is the published suite result;
"after" is the set-up re-run by `setups.yml` in CI, with the same runners and the same engine
versions. The CI runs gave the same numbers as the local runs.

## What was changed, and why it works

### SWMM 5.2.4, SWMM 5.1.15, OpenSWMM dynamic wave: converge the iteration

**Problem.** The channel tests model a 1D channel as one SWMM conduit per grid cell, down to
5 cm long. SWMM's dynamic-wave solver iterates every time step until the head at each node
changes by less than `HEAD_TOLERANCE`, and gives up after `MAX_TRIALS`. The harness used 8 trials
and 0.5 mm. On short conduits that is not enough: on the subcritical bump (A1F-040, finest grid)
46 % of time steps ended unconverged, continuity drifted, and the water level was 0.8 m off.
The suite's existing "converged" variants use 20 trials, still too few on the finest grid.

**Fix.** `MAX_TRIALS 30`, `HEAD_TOLERANCE 0.00001` (set-ups `*-thirty-trials`), and a tighter
`MAX_TRIALS 50`, `HEAD_TOLERANCE 0.000001` (`*-fifty-trials`). Unconverged steps fell from 46 %
to 0.15 %.

| Test | Published | 30 trials | 50 trials |
|---|---|---|---|
| A1F-040 subcritical bump | 174 (SWMM 5.2.4) / 236 (OpenSWMM) | **0.08** / **0.08** | **0.07** / **0.07** |
| A1F-020 hydraulic jump | 102 / 99 | 70 / 25 | 41 / 41 |
| A1F-011 wet-bed dam break | 6.7 / 6.7 | 5.9 / 5.9 | **2.3** / **2.3** |
| A1F-010 dry-bed dam break | 11.0 / 11.0 | **6.6** / **6.6** | 10.3 / 10.3 |
| A1F-041 transcritical bump | 189 / 165 | 93 / 110 | 165 / 142 |
| A1F-042 bump with jump | 322 / 194 | 204 / 150 | 127 / 153 |
| A1D-003 | 0.33 / 0.33 | 0.33 | **0.04** |

The subcritical bump goes from a large failure to an essentially exact answer. Neither set-up
wins everywhere, so both are published. SWMM 5.1.15 gets the same two set-ups and, in CI, gives the same numbers as SWMM 5.2.4.

**What does not get fixed.** The transcritical bumps (A1F-041, A1F-042) improve but stay well
outside the band at every setting tried, including a free outfall, variable steps and damping.
SWMM's link-node scheme has no way to represent a supercritical reach followed by a jump on a
frictionless bed. That is a limit of the method, not a setting.

### OpenSWMM v6 1D/2D (sewer and street): put the grate's lip in the surface

**Problem.** In A12-011 a walled yard drains through a gully whose crest is 5 cm above the floor,
so 5 cm of water must stay. OpenSWMM couples each manhole to one mesh vertex. With that vertex at
floor level, its orifice law kept draining below the crest. The yard ended 1.2 cm too low and
4 % more water left than physically could (score 23.7 on two triangles per square, 29.0 on four).

**Fix.** Raise the single coupling vertex to the grate's crest (`crest_at_vertex true`, set-ups
`openswmm-2d-grate-crest` and `openswmm-2d-x-grate-crest`). The lip is then part of the surface,
as it is in a real gully.

| Test | Two triangles: before → after | Four triangles: before → after |
|---|---|---|
| A12-010 surcharge onto street | 0.5 → 0.5 | 11.5 → 11.5 |
| A12-011 yard draining into pipe | 23.7 → **11.4** (all checks pass) | 29.0 → 14.9 |
| A12-012 surcharge and return | 0.2 → 0.2 | 0.25 → 0.25 |

On two triangles per square, every check of all three tests now passes. On four triangles the
street depth in A12-010 stays 8 mm high: that comes from the mesh, not the coupling.

### Landlab OverlandFlow: a thinner wet film

**Problem.** OverlandFlow puts a film of `h_init` (default 1 mm) on every cell so its flux
formula never divides by zero. In the lake at rest over an emerged bump (A1F-043), the dry crest
carries that 1 mm film, which drives a spurious flow that never settles (score 13.3).

**Fix.** `h_init 0.000001`, i.e. 1 µm (set-up `landlab-lake-at-rest`). Score **13.3 → 0.001**.
On the dam breaks it makes no difference. The `steep_slopes` option was also tried and made them
slightly worse.

### LISFLOOD-FP ACC: diffusion and a smaller step on the bumps

**Problem.** ACC (local inertia) drops the momentum equation's advection term. Flow over a bump
is outside what it is built for, and the developers point to FV1 or DG2 for such flow (both pass
these tests in the suite).

**Fix within ACC.** `theta 0.7` (the q-centred weighting of de Almeida et al. 2012; the default 1
adds no diffusion) and `cfl 0.3` instead of 0.7 (set-up `lisflood-acc-bump-diffusion`).

| Test | Published | Set-up |
|---|---|---|
| A1F-040 | 58.7 | 31.8 |
| A1F-041 | 51.5 | 41.6 |
| A1F-042 | 64.2 | 42.9 |

The error falls by a fifth to a half but stays outside the band, because the missing term is
structural. On the dry-bed dam break (A1F-010), `theta 0.7` made things worse (28 → 33) and
`cfl 0.3` made no difference, so the set-up leaves that test alone.

### HEC-RAS 7.0.1 2D: dam-break time step and tolerances

**Problem.** On the dry-bed dam break (A1F-010) the front lags 58–97 m. The open finite-volume
codes are within 2–6 m (score 15.4 with SWE-EM, 25.9 with SWE-ELM).

**Fix to test.** HEC's guidance for sudden dam breaks is the full-momentum SWE-EM equations with
a Courant number at or below 1. The set-ups `hecras-em-dam-break` and `hecras-elm-dam-break` cap
the adaptive step at Courant 0.5 (minimum 0.2) and tighten the 2D water-surface and volume
tolerances from 0.01 to 0.001, with up to 40 iterations. HEC-RAS runs only on Windows, so these
run in the new `hecras` job of `setups.yml`.

| Test | SWE-EM: before → after | SWE-ELM: before → after |
|---|---|---|
| A1F-010 dry-bed dam break | 15.4 → **7.2** (front lag 58 m → 27 m) | 25.9 → 26.0 (lag 97 m → 98 m) |
| A1F-011 wet-bed dam break | 1.4 → 1.0 | 0.9 → 1.0 |

With full momentum (SWE-EM), the smaller step and tighter tolerances halve the front's lag.
With the default SWE-ELM equations, nothing changes, so that error comes from the equation set,
not the step. A set-up cannot change the equation set (the suite already scores both). An expert
modelling a dam break in HEC-RAS should choose SWE-EM, as HEC advises.

A further set-up, `hecras-em-dam-break-fine-step`, halves the Courant cap again (0.25, never
below 0.1). The lag keeps shrinking: 27 m → **10 m**, score 7.2 → **2.7**. That leaves the front
just outside the 9.8 m band; the mass and the wet-bed dam break stay exact. For a dry-bed dam
break in HEC-RAS, the step matters more than the tolerances: use SWE-EM and keep the Courant
number near 0.25.

## What no setting fixes, and why

| Model | Tests | Why |
|---|---|---|
| HydroNet finite volume (Roe) | A1F-010 dry-bed dam break | The dam never breaks. At a face between a wet cell and a dry one, HydroNet's Roe flux passes only the wet side's physical flux, `hu`, which is zero for still water. The dry cell's momentum is zeroed every stage, so no water ever crosses. Changing `h_dry` (1e-2, 1e-3, 1e-4) gives identical results. This is a defect in the solver's wet/dry treatment. The same solver passes the wet-bed dam break (0.26). The set-up path for `cfl` and `h_dry` is in place for anyone who finds a fix. |
| HydroNet FVM-PINN | A1F-010, A1F-011 | The network is trained without data, using HydroNet's own example recipe. Its errors come from the training, not from a solver setting. |
| Hydra urban drainage (17.0.0/4.1.1) | A1F-0xx channel tests, A1F-100 | Its command line has no solver controls. `MAX_TRIALS`, damping, variable step and the routing step in the input file make no difference. |
| OpenSWMM finite volume | A1D-002, A1F-020 | `FV_ORDER 2` with MINMOD or VANLEER limiters, and `FV_RIEMANN HLLC`, give the same answer to three figures (A1F-020 stays at 50.2; A1D-002 23.4 → 23.7). The error is in the engine's scheme for these cases, not its options. |
| Landlab OverlandFlow | A1F-010, A1F-040–042 | Local-inertia equations without advection: the dam-break front and transcritical flow over the bumps are outside the method. `alpha`, `theta`, `h_init` and `steep_slopes` were tried. |
| OpenSWMM, Hydra | B-RTC-001 pump-station rules | A parity test: it checks that an engine reproduces EPA SWMM 5's own result on the same model. The difference is in how each engine evaluates the control rules, so tuning the solver to hide it would defeat the test. |
| HEC-RAS pipe networks | A12-010, A12-011 | Not re-tested in this pass. The pipe-network model is Windows-only and has no set-up path yet. |
| SWMM + ANUGA | A12-011 (5.8) | Just over 5 % (the yard ends 3 mm high). This is the suite's own reference coupling, so it is left as published. |

## How to check or improve on any of this

Each set-up is a small file in `setups/<slug>/setup.json`, with its settings and the reason for
them. The site shows its results beside the suite's own, with the model files to download.
Anyone can propose a better one (issue form or pull request, see
[the set-ups page](https://scott-jeffers.github.io/benchmark1d2d/setups.html)), and it is run on
the same machines.

New in this pass: set-ups for HEC-RAS 2D (plan-file keys), Landlab (`alpha`, `theta`, `h_init`,
`steep_slopes`), OpenSWMM 1D/2D (`crest_at_vertex`) and HydroNet's finite-volume solver (`cfl`,
`h_dry`).
