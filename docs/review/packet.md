# Outside-review packet

Generated from the catalog (39 cases: 0 frozen, 30 candidate, 9 draft) and the published score cards. Read `docs/review/README.md` first: it says what we ask reviewers to check and how to send a review.

## A12-010 — Manhole surcharge onto a sloping street

*verification analytic, version 1.0.0, candidate.* A 0.6 m pipe delivers 0.5 m³/s to a manhole with no outlet, which surcharges onto a 10 m wide street sloping at 0.005 (Manning n = 0.02). At steady state the manhole passes the whole inflow onto the street, and downstream the street carries it as uniform sheet flow at the exact normal depth (n q / √S)^(3/5) = 77.7 mm.

**Reference:** exact states from conservation: steady_exchange = 0.5 m3/s; normal_depth = 0.07768 m.
**Sources:** Chen et al. (2007); Rubinato et al. (2017) doi:10.1016/j.jhydrol.2017.06.024.

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| exchange_flow | expected_state_error of Q | abs<= 1 % | yes | Steady manhole outflow within 1 % of the inflow. |
| street_depth | expected_state_error of h | abs<= 0.003 m | yes | Street depth 75–125 m below the manhole within 3 mm (4 %) of normal depth: the sheet must carry exactly what the manhole released. |
| water_balance | continuity_error of volume | abs<= 0.5 % | yes | By the end of the run, the water stored on the surface and in the pipes has changed by exactly what came in minus what went out. A coupling that moves water between the two models must not make or lose any; each engine's own continuity error is allowed within this limit. |

Convergence: not applicable — Scored on exact states that follow from conservation (exchanged and discharged volumes, settled levels): they do not depend on the grid.

**Passes:** none.  
**Fails:** SWMM + ANUGA coupled 1D/2D.

**Before it can be frozen:** a published run passes (no passing score card published yet); two independent codes pass (passing codes: none — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A12-011 — Flood draining into a pipe

*verification analytic, version 1.0.0, candidate.* A 30 × 30 m walled yard holds 0.3 m of water (270 m³). It drains through a gully whose crest stands 5 cm above the yard floor into a 0.3 m pipe to a free outfall. The water above the crest leaves through the pipe; the 5 cm below it cannot. After two hours the yard is ponded at the crest level (45 m³ stays), and 225 m³ has left by the outfall.

**Reference:** exact states from conservation: final_level = 0.05 m; discharged_volume = 225 m3.
**Sources:** Chen et al. (2007); Rubinato et al. (2017) doi:10.1016/j.jhydrol.2017.06.024.

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| final_level | expected_state_error of h | abs<= 0.01 m | yes | Yard level within 1 cm of the crest after two hours: the last of the water over a crest drains slowly (as a weir it slows with the head to the 3/2), so a coupling with any reasonable exchange law is within a few millimetres. |
| discharged_volume | expected_state_error of V | abs<= 2 % | yes | Outfall volume within 2 % of 225 m³: the water above the crest has gone through the pipe. |
| water_balance | continuity_error of volume | abs<= 0.5 % | yes | By the end of the run, the water stored on the surface and in the pipes has changed by exactly what came in minus what went out. A coupling that moves water between the two models must not make or lose any; each engine's own continuity error is allowed within this limit. |

Convergence: not applicable — Scored on exact states that follow from conservation (exchanged and discharged volumes, settled levels): they do not depend on the grid.

**Passes:** SWMM + ANUGA coupled 1D/2D.  
**Fails:** none.

**Before it can be frozen:** two independent codes pass (passing codes: SWMM–ANUGA coupled — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A12-012 — Surcharge onto the surface and back

*verification analytic, version 1.0.0, candidate.* A storm hydrograph (peak 0.3 m³/s at 10 min, 180 m³ in all) enters a sewer whose outgoing pipe carries only about 0.06 m³/s. The manhole surcharges onto a 20 × 20 m walled hollow that falls 1 % towards it; when the storm passes, the water returns down the manhole. After three hours every drop has left by the outfall.

**Reference:** exact states from conservation: discharged_volume = 180 m3; surface_empty = 0 m3.
**Sources:** Chen et al. (2007); Rubinato et al. (2017) doi:10.1016/j.jhydrol.2017.06.024.

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| discharged_volume | expected_state_error of V | abs<= 2 % | yes | Outfall volume within 2 % of the 180 m³ that came in. |
| surface_empty | expected_state_error of V | abs<= 1.8 m3 | yes | At most 1.8 m³ (1 % of the storm) left on the surface: a thin film on the 1 % slope drains slowly. |
| water_balance | continuity_error of volume | abs<= 0.5 % | yes | By the end of the run, the water stored on the surface and in the pipes has changed by exactly what came in minus what went out. A coupling that moves water between the two models must not make or lose any; each engine's own continuity error is allowed within this limit. |

Convergence: not applicable — Scored on exact states that follow from conservation (exchanged and discharged volumes, settled levels): they do not depend on the grid.

**Passes:** SWMM + ANUGA coupled 1D/2D.  
**Fails:** none.

**Before it can be frozen:** two independent codes pass (passing codes: SWMM–ANUGA coupled — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1D-001 — Normal depth in partly full circular pipes

*verification analytic, version 1.0.0, candidate.* Three chains of ten 1 m circular pipes (n = 0.013, slope 0.002) carry 0.15, 0.5 and 1.0 m³/s to normal-depth outfalls, filling them to about a quarter, a half and three quarters. At steady state every interior manhole and every pipe runs at Manning normal depth in the exact circular section.

**Reference:** exact solution, `references.drainage.uniform_flow`.
**Sources:** Chow (1959); Rossman (2017).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| normal_depth | Linf of h | abs<= 0.01 m | yes | Worst node or pipe depth within 1 cm (1 % of the diameter). SWMM-family engines store circular-pipe area and hydraulic radius in 51-entry tables and interpolate between them; that alone moves a normal depth by a few millimetres. |
| pipe_flow | L2 of Q | abs<= 0.5 % | yes | Pipe flows within 0.5 %: at steady state every pipe carries its chain's inflow. |

Convergence: not applicable — A link–node network with a closed-form (or 1e-11 integrated) reference at fixed elements: there is no grid to refine.

**Passes:** EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, Hydra urban drainage.  
**Fails:** OpenSWMM 6 finite volume.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1D-002 — Surcharged pipes: hydraulic grade line

*verification analytic, version 1.0.0, candidate.* Five 0.6 m pipes (100 m, n = 0.013) carry 0.3 m³/s to an outfall held 1.5 m above its invert, so every pipe runs full. The hydraulic grade line falls by n²Q²L/(A²R^(4/3)) = 0.239 m along each pipe (1.19 m in all); manhole depths follow exactly.

**Reference:** exact solution, `references.drainage.surcharged_pipe`.
**Sources:** Chow (1959); Rossman (2017).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| grade_line | Linf of h | abs<= 0.01 m | yes | Worst manhole head within 1 cm of the 1.19 m friction loss (0.8 %). Full-pipe friction is exact in every engine's geometry; the error is how surcharged heads are solved. |
| pipe_flow | L2 of Q | abs<= 0.5 % | yes | Pipe flows within 0.5 % of the inflow. |

Convergence: not applicable — A link–node network with a closed-form (or 1e-11 integrated) reference at fixed elements: there is no grid to refine.

**Passes:** EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, Hydra urban drainage.  
**Fails:** OpenSWMM 6 finite volume.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1D-003 — Storage draining through a power-law outlet

*verification analytic, version 1.0.0, candidate.* A 100 m² storage, 2 m deep, empties through an outlet rated Q = 0.5 h^0.5 to a free outfall. Its depth follows h(t) = (√h0 − C t/(2A))² exactly: 0.441 m and 0.332 m³/s at 300 s.

**Reference:** exact solution, `references.drainage.storage_drain`.
**Sources:** Rossman (2017).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| storage_depth | Linf of h | abs<= 0.005 m | yes | Storage depth within 5 mm (about 1 %) after 300 s. A first-order time integration with SWMM's default steps errs by well under a millimetre. |
| outlet_flow | Linf of Q | abs<= 0.005 m³/s | yes | Outlet flow within 5 L/s (1.5 %), the rating applied to the depth. |

Convergence: not applicable — One storage node and one outlet: there is no grid to refine; the time step is the engine's own.

**Passes:** EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, OpenSWMM 6 finite volume, Hydra urban drainage.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1D-004 — Pump operating on its head–flow curve

*verification analytic, version 1.0.0, candidate.* A 20 m² wet well receives 0.1 m³/s and is emptied by a pump (head–flow curve 12 m/0, 10 m/0.08, 6 m/0.15 m³/s) against an outfall held at 10 m. At steady state the pump passes the inflow at a head rise of 8.857 m, so the wet well stands at 1.143 m.

**Reference:** exact solution, `references.drainage.pump_curve`.
**Sources:** Rossman (2017).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| wet_well_depth | Linf of h | abs<= 0.01 m | yes | Wet-well depth within 1 cm. The operating point is the curve read at the inflow; the curve is linear between its points in every engine that accepts this input. |
| pump_flow | Linf of Q | abs<= 0.001 m³/s | yes | Pump flow within 1 L/s of the inflow (1 %). |

Convergence: not applicable — A link–node network with a closed-form (or 1e-11 integrated) reference at fixed elements: there is no grid to refine.

**Passes:** EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, OpenSWMM 6 finite volume, Hydra urban drainage.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1D-005 — Backwater through a chain of manholes

*verification analytic, version 1.0.0, candidate.* Twenty 1.2 m pipes (50 m each, n = 0.013, slope 0.001) carry 0.6 m³/s from normal depth (0.59 m) down to an outfall held 1.0 m above its invert. The M1 backwater profile through the manholes is integrated from the outfall to 1e-11 (gradually varied flow in the exact circular section).

**Reference:** exact solution, `references.drainage.backwater`.
**Sources:** Chow (1959); Rossman (2017).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| profile_depth | Linf of h | abs<= 0.02 m | yes | Worst manhole or pipe depth within 2 cm. A link–node model represents each 50 m pipe by its end heads and a mid-pipe depth, a second-order discretisation of the profile whose error here is a few millimetres; the rest is the section tables. |
| pipe_flow | L2 of Q | abs<= 0.5 % | yes | Pipe flows within 0.5 % of the inflow. |

Convergence: not applicable — A link–node network with a closed-form (or 1e-11 integrated) reference at fixed elements: there is no grid to refine.

**Passes:** EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, OpenSWMM 6 finite volume, Hydra urban drainage.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1F-001 — MacDonald M1 subcritical backwater

*verification analytic, version 1.1.0, candidate.* Steady 1D open-channel M1-like backwater with MacDonald manufactured bed so that a prescribed smooth depth profile is exact.

**Reference:** exact solution, `references.macdonald.depth_profile`.
**Sources:** MacDonald et al. (1997) doi:10.1061/(ASCE)0733-9429(1997)123:11(1041).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| L1_h | L1 of h | abs<= 0.01 m | yes | Steady depth L1 error on finest mesh against MacDonald M1 profile. |
| mass | global_mass_error of volume | abs<= 0.1 % | yes | Conservation property at steady state. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 1D suite example, EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, Hydra urban drainage.  
**Fails:** HEC-RAS 6.6 1D · 2D SWE-ELM, OpenSWMM 6 finite volume.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1F-010 — Ritter dry-bed dam break

*verification analytic, version 2.0.0, candidate.* 1D inviscid Saint-Venant dam break onto a dry bed with exact Ritter (1892) solution.

**Reference:** exact solution, `references.ritter.depth_velocity`.
**Sources:** Ritter (1892).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| volume_front | volume_front_error of h | abs<= 2.5 m | yes | Two finest cells (2×1.25 m). The front is the abscissa beyond which lies the last 5 % of the water downstream of the dam (exact: x0 + 2c0·t·(1 − 0.05^(1/3)) = 1237.4 m at 60 s). An integral of depth is well conditioned on the thin tip, where a depth contour is not; it is computed against the solver's own downstream volume, so mass errors do not leak into it. |
| front_position | front_position_error of h | abs<= 2.5 m | no | Reported, not gating (since v2.0.0). Exact iso-contour at h=0.001·h0 (~1358 m). On the thin tip a 1 mm depth error moves this contour about 10 m, and production codes treat depths under ~1 mm as dry, so it measures thin-film handling more than the front; the volume front gates instead. |
| mass | global_mass_error of volume | abs<= 0.1 % | yes | Conservation property of continuous equations. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 1D suite example, ANUGA 4.0.1.  
**Fails:** HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM, TELEMAC-2D openTELEMAC 9.1, GeoClaw Clawpack 5.9, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC, EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, OpenSWMM 6 finite volume, Hydra urban drainage, HydroNet finite volume, HydroNet FVM-PINN.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1F-011 — Stoker wet-bed dam break

*verification analytic, version 1.0.0, candidate.* 1D inviscid Saint-Venant dam break onto a wet bed (hl=1, hr=0.1) with exact Stoker (1957) Riemann solution.

**Reference:** exact solution, `references.stoker.depth_velocity`.
**Sources:** Stoker (1957).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| L1_h | L1 of h | abs<= 0.05 m | yes | L1 depth error on finest mesh; shock and rarefaction capture. |
| mass | global_mass_error of volume | abs<= 0.1 % | yes | Conservation property of continuous equations. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 1D suite example, ANUGA 4.0.1, GeoClaw Clawpack 5.9, OpenSWMM 6 finite volume.  
**Fails:** HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM, TELEMAC-2D openTELEMAC 9.1, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC, EPA SWMM 5.2.4 dynamic wave, OpenSWMM 6 dynamic wave, Hydra urban drainage, HydroNet finite volume, HydroNet FVM-PINN.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1F-020 — Bélanger hydraulic jump

*verification analytic, version 1.0.0, candidate.* A stationary hydraulic jump on a horizontal frictionless bed: supercritical inflow (h1 = 0.2 m, Fr1 = 2.5) meets the Bélanger sequent depth h2 = 0.61 m held downstream. The exact solution is a step that stays at x = 50 m; the case checks that a solver captures the jump with the right conjugate depths and does not let it drift.

**Reference:** exact solution, `references.belanger.sequent_depths`.
**Sources:** Bélanger (1828).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| jump_profile | L1 of h | abs<= 1 % | yes | Depth profile within 1 % (relative L1) of the stationary Bélanger step at x = 50 m on the finest grid. A captured jump smeared over two cells contributes Δh·2dx/L ≈ 0.5 % at dx = 0.25 m; a drifting jump or wrong sequent depth exceeds it. |
| jump_stays_put | global_mass_error of volume | abs<= 0.1 % | yes | Stored volume within 0.1 % of the exact step: a jump that drifts by half a cell (0.125 m) on the finest grid changes the volume by 0.13 %, so this fails any solver that cannot hold the Rankine–Hugoniot balance. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 1D suite example.  
**Fails:** none.

**Before it can be frozen:** two independent codes pass (passing codes: demo — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1F-040 — Subcritical flow over a bump (SWASHES)

*verification analytic, version 1.0.0, candidate.* Steady frictionless flow of q = 4.42 m²/s over a 0.2 m parabolic bump in a 25 m channel, held at 2 m downstream. The flow stays subcritical; the depth follows from constant discharge and Bernoulli head (a cubic at every point), dipping to 1.71 m over the crest.

**Reference:** exact solution, `references.swashes.steady_bump`.
**Sources:** Delestre et al. (2013) doi:10.1002/fld.3741; Goutal and Maurel (1997).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| L1_h | L1 of h | abs<= 0.005 m | yes | Average depth error under 5 mm (0.25 % of the depth) once steady. |
| L1_Q | L1 of Q | abs<= 0.044 m²/s | yes | Discharge within 1 % of q everywhere on average: a steady state must carry the inflow along the whole channel. |

Convergence: L1 of h, expected order 2.0, at least 0.8 required.

**Before it can be frozen:** a published run passes (no passing score card published yet); order of accuracy shown (no passing run with multi-grid evidence); two independent codes pass (passing codes: none — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1F-041 — Transcritical flow over a bump, no shock (SWASHES)

*verification analytic, version 1.0.0, candidate.* Steady frictionless flow of q = 1.53 m²/s over the 0.2 m bump with a free outflow. The flow passes through critical depth at the crest, subcritical upstream and supercritical downstream, with no jump: the depth falls from 1.01 m to 0.41 m.

**Reference:** exact solution, `references.swashes.steady_bump`.
**Sources:** Delestre et al. (2013) doi:10.1002/fld.3741; Goutal and Maurel (1997).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| L1_h | L1 of h | abs<= 0.005 m | yes | Average depth error under 5 mm (1 % of the downstream depth) once steady; the critical point at the crest is where schemes struggle. |
| L1_Q | L1 of Q | abs<= 0.0153 m²/s | yes | Discharge within 1 % of q on average. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Before it can be frozen:** a published run passes (no passing score card published yet); order of accuracy shown (no passing run with multi-grid evidence); two independent codes pass (passing codes: none — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1F-042 — Transcritical flow over a bump with a hydraulic jump (SWASHES)

*verification analytic, version 1.0.0, candidate.* Steady frictionless flow of q = 0.18 m²/s over the 0.2 m bump, held at 0.33 m downstream. The flow goes critical at the crest, accelerates down the bump and jumps back to subcritical at x = 11.666 m, where the Rankine–Hugoniot condition holds.

**Reference:** exact solution, `references.swashes.steady_bump`.
**Sources:** Delestre et al. (2013) doi:10.1002/fld.3741; Goutal and Maurel (1997).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| L1_h | L1 of h | abs<= 0.005 m | yes | Average depth error under 5 mm (1.5 % of the downstream depth) once steady; a jump one cell out of place costs about 0.2 m over one cell, about 1 mm of average error on the finest grid. |
| L1_Q | L1 of Q | abs<= 0.0018 m²/s | yes | Discharge within 1 % of q on average. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Before it can be frozen:** a published run passes (no passing score card published yet); order of accuracy shown (no passing run with multi-grid evidence); two independent codes pass (passing codes: none — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1F-043 — Lake at rest with an emerged bump (SWASHES)

*verification analytic, version 1.0.0, candidate.* Still water at level 0.1 m over the 0.2 m bump, whose top stands out of the water between x = 9.55 and 10.45 m. Nothing should move: the depth stays max(0.1 − z, 0) and the velocity zero. A scheme that does not balance the bed slope against the pressure gradient, or mishandles the dry shoreline on a slope, sets the lake in motion.

**Reference:** exact solution, `references.swashes.lake_at_rest`.
**Sources:** Delestre et al. (2013) doi:10.1002/fld.3741; Goutal and Maurel (1997).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| Linf_u | Linf of u | abs<= 0.001 m/s | yes | Nothing may move: worst velocity under 1 mm/s after 100 s. A scheme that does not balance the bed slope against the pressure gradient, or leaks at the dry shoreline on the bump, sets up currents of centimetres per second. |
| L1_h | L1 of h | abs<= 0.0005 m | yes | Average depth change under 0.5 mm: the lake must keep its water where it was. |
| Linf_h | Linf of h | abs<= 0.001 m | no | Informational: the worst depth difference sits in the cells cut by the shoreline, where a cell-mean depth over a sloping bed differs from the exact depth at the cell centre by up to a few millimetres on these grids even when nothing moves. |

Convergence: not applicable — The exact state is the initial state; a well-balanced scheme keeps it to rounding error on any grid, so there is no error to converge.

**Before it can be frozen:** a published run passes (no passing score card published yet); two independent codes pass (passing codes: none — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1P-001 — Darcy–Weisbach single pipe

*verification analytic, version 1.0.0, candidate.* Steady flow through a 1 km, 300 mm pipe at 1 m/s. The friction factor follows from Colebrook–White, so the exact head loss Δh = f (L/D) V²/(2g) = 3.09 m checks both the friction law a solver uses and how it applies it.

**Reference:** exact solution, `references.darcy_weisbach.head_loss`.
**Sources:** Darcy and Weisbach (1845).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| head_loss | relative_head_loss of h | abs<= 1 % | yes | Exact Colebrook–White head loss within 1 %: the accuracy Swamee & Jain (1976) give for their explicit approximation over 5e3 < Re < 1e8, so a solver using any standard explicit friction formula passes and a wrong friction law or a units error fails. |
| head_profile | L2 of h | abs<= 0.05 m | yes | Heads along the pipe within 5 cm of the linear exact profile: catches a correct total loss distributed wrongly. |

Convergence: not applicable — Steady closed-form pipe flow: a network solver has no grid to refine, so observed order of accuracy does not apply.

**Passes:** EPANET 2.2 US EPA, Hydra water distribution.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1P-010 — Todini multi-loop network

*verification analytic, version 1.0.0, candidate.* Steady two-loop gravity network (Alperovits & Shamir 1977 topology, fixed analysis diameters, Hazen–Williams). Reference heads and flows from a Todini–Pilati gradient solve converged to 1e-12 m, cross-checked against EPANET 2.2 (|ΔH| < 1 mm).

**Reference:** exact solution, `references.todini.steady_network`.
**Sources:** Todini and Pilati (1988); Alperovits and Shamir (1977) doi:10.1029/WR013i006p00885.

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| nodal_head | Linf of h | abs<= 0.05 m | yes | Worst junction head within 5 cm. The SI Hazen–Williams coefficients in use differ by up to 0.1 % (10.667 here, ≈10.67 from EPANET's US-unit 4.727), which moves heads by at most 0.03 m on this network's 26 m of loss; single-precision output adds about 2 mm at 200 m. |
| link_flow | L2 of Q | abs<= 0.1 % | yes | Pipe flows within 0.1 % (relative L2). Flows do not depend on the Hazen–Williams coefficient's absolute value, only on continuity and loop balance; 0.1 % is the default EPANET convergence criterion (sum of flow changes over total flow ≤ 0.001). |

Convergence: not applicable — Steady looped network with a closed-form-equivalent reference: there is no grid or time step to refine.

**Passes:** EPANET 2.2 US EPA, Hydra water distribution.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A1P-020 — Joukowsky instant valve closure

*verification analytic, version 3.0.0, candidate.* Frictionless pipe after an instantaneous valve closure: the classic Joukowsky pressure rise ρaV₀ travels upstream as a sharp front until it reaches the reservoir. Because the front is a discontinuity carried by a linear wave equation, a first-order fixed-grid scheme converges in L1 only at order ½ (p/(p+1) for order p), which sets the convergence target; the storage balance checks mass exactly.

**Reference:** exact solution, `references.joukowsky.pressure_wave`.
**Sources:** Joukowsky (1900).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| peak_pressure | peak_error of p | abs<= 2 % | yes | Peak pressure within ±2% of Joukowsky rise Δp = ρ a V0. |
| storage_balance | storage_balance_error of p | abs<= 1 % | yes | Mass balance with no free parameter: until the first reflection the reservoir keeps delivering V0 while the valve is shut, and the pipe must store exactly that volume by compression, so ∫Δp dx = ρa²V0t. A conservative scheme meets it to round-off; 1 % allows non-conservative interpolation schemes that are otherwise accurate. |

Convergence: L1 of p, expected order 0.5, at least 0.4 required.

**Passes:** Demo 1D suite example.  
**Fails:** none.

**Before it can be frozen:** two independent codes pass (passing codes: demo — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A1P-030 — Advection–dispersion tracer (Ogata–Banks)

*verification analytic, version 1.0.0, candidate.* A tracer is released continuously at x = 0 into a uniform flow (u = 0.1 m/s, D = 0.01 m²/s); after one hour the front is 360 m downstream. Ogata & Banks (1961) give the exact profile, which tests both advection and dispersion and penalises numerical diffusion.

**Reference:** exact solution, `references.ogata_banks.concentration`.
**Sources:** Ogata and Banks (1961).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| concentration_L1 | L1 of c | abs<= 2 % | yes | Concentration L1 error within 2 % of the L1 norm of the Ogata–Banks profile on the finest grid. The front is 8.5 m wide (2√(Dt)) and moves 360 m, so a scheme with numerical diffusion comparable to D (first-order upwind at u·dx/2 = 0.025 m²/s, 2.5×D) visibly smears it and fails. |
| mass | global_mass_error of c | abs<= 0.5 % | yes | Tracer mass in the domain within 0.5 % of the exact integral: a conservative scheme meets it to quadrature error. |

Convergence: L1 of c, expected order 2.0, at least 1.6 required.

**Passes:** Demo 1D suite example.  
**Fails:** none.

**Before it can be frozen:** two independent codes pass (passing codes: demo — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A2A-001 — Thacker parabolic bowl

*verification analytic, version 2.0.0, candidate.* 2D shallow-water planar free-surface oscillation in a parabolic bowl (Thacker 1981) with a moving wet/dry shoreline. Reference: zs = (η h0/L²)(2x cos ωt − η cos² ωt), u = −η ω sin ωt, ω = √(2 g h0)/L. Case v2.0.0 replaces a v1 reference that satisfied momentum but violated mass conservation (wrong ω and a missing cos² term).

**Reference:** exact solution, `references.thacker.depth_velocity`.
**Sources:** Thacker (1981) doi:10.1017/S0022112081001882.

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| depth_L1 | L1 of h | abs<= 0.02 m | yes | L1 depth error within 0.02 m of Thacker exact solution on the finest mesh. |
| mass | global_mass_error of volume | abs<= 0.1 % | yes | Global volume conserved within 0.1% versus analytic wet mass. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 2D suite example, TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1, GeoClaw Clawpack 5.9.  
**Fails:** LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A2A-010 — MacDonald 2D manufactured channel

*verification analytic, version 2.0.0, candidate.* Steady subcritical flow with Manning friction in a 1 km × 100 m channel whose bed is built (MacDonald's method) so that a known smooth depth profile is the exact solution. It is A1F-001's profile on a 2D grid: the solver has to balance pressure, bed slope and friction in two dimensions, starting from a uniform depth.

**Reference:** exact solution, `references.macdonald_2d.depth_velocity`.
**Sources:** MacDonald et al. (1997) doi:10.1061/(ASCE)0733-9429(1997)123:11(1041).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| depth_L1 | L1 of h | abs<= 0.01 m | yes | Mean depth error below 1 cm on the finest grid (1.3 % of the 0.74 m outlet depth); a scheme that is not well balanced over the sloping bed, or that mis-applies friction, settles to a visibly different profile. |
| mass | global_mass_error of volume | abs<= 0.5 % | yes | Water stored in the channel within 0.5 % of the exact profile: confirms the run has reached the steady state rather than a different equilibrium. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 2D suite example, TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2.  
**Fails:** HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM, LISFLOOD-FP 8.3 · ACC.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A2A-020 — Oblique hydraulic jump

*verification analytic, version 2.0.0, candidate.* Supercritical flow (Fr₁ = 2.5) meets a straight wall at 15° and is turned through an oblique hydraulic jump. The exact solution has two uniform states separated by a straight jump at 39.58° to the incoming flow, with depth ratio 1.81. It tests shock capturing in 2D and directional accuracy on a Cartesian grid.

**Reference:** exact solution, `references.oblique_jump.depth_velocity`.
**Sources:** Ippen (1951).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| depth_L1 | L1 of h | abs<= 0.05 m | yes | Mean depth error within 5 cm of the exact two-state field on the finest grid (6 % of the 0.81 m depth jump); a jump at the wrong angle or with the wrong conjugate depth fails. |
| mass | global_mass_error of volume | abs<= 0.1 % | yes | Stored volume within 0.1 % of the exact field: the jump sits where the jump conditions put it. |

Convergence: L1 of h, expected order 1.0, at least 0.8 required.

**Passes:** Demo 2D suite example.  
**Fails:** TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1.

**Before it can be frozen:** two independent codes pass (passing codes: demo-swe2d — needs a second, independently written solver or engine); maintainer review recorded (no maintainer review recorded).

## A2C-EA1 — EA Test 1 — flooding a disconnected water body

*intercomparison, version 1.0.0, candidate.* 700 m × 100 m sloping strip with a depression behind a 10.25 m sill. A water-level boundary rises from 9.7 m to 10.35 m, holds, then falls back; the pond must fill, become horizontal, and settle at the sill crest. Tests wetting/drying and disconnected water bodies.

**Reference:** objective expected states: pond_final_level_p1 = 10.25 m; pond_final_level_p2 = 10.25 m; peak_level = 10.35 m; final_stored_volume = 9954.1 m3.
**Sources:** Néelz and Pender (2013); Néelz and Pender (2010).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| final_level_p1 | expected_state_error of h | abs<= 0.02 m | yes | A solver that conserves mass and handles the sill must leave the pond at the crest level; 2 cm allows for slow drainage over the sill by t = 20 h. |
| final_level_p2 | expected_state_error of h | abs<= 0.02 m | yes | Same pond as P1, so it must settle at the same 10.25 m crest level; a second point catches a solver that leaves the pond tilted or partly drained. |
| peak_level | expected_state_error of h | abs<= 0.02 m | yes | Hydrostatic plateau level during the 10 h hold. |
| final_volume | expected_state_error of volume | abs<= 2 % | no | Informational: depends on how the solver samples the 2 m DEM onto its own grid. |

**Passes:** Demo 2D suite example, HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM, TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A2C-EA2 — EA Test 2 — filling of floodplain depressions

*intercomparison, version 1.0.0, candidate.* 2 km × 2 km floodplain with a 4 × 4 grid of ~0.5 m deep depressions; a 20 m³/s, ~85 min hydrograph enters along 100 m of the north-west edge and the run continues to 48 h. Tests low-momentum filling and final inundation extent.

**Reference:** objective expected states: final_stored_volume = 97200 m3.
**Sources:** Néelz and Pender (2013); Néelz and Pender (2010).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| mass_conservation | expected_state_error of volume | abs<= 0.1 % | yes | The only exact statement the test admits: nothing leaves a closed domain, so any difference is mass created or lost by the scheme (suite target < 0.1 %). |

**Passes:** Demo 2D suite example, TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC.  
**Fails:** HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A2C-EA4 — EA Test 4 — speed of flood propagation over an extended floodplain

*intercomparison, version 1.0.0, candidate.* Flat, horizontal 1000 m × 2000 m floodplain at 0 m; a breach hydrograph peaking at 20 m³/s enters along a 20 m line mid-way along the west edge. Tests front celerity and transient depths and velocities at the leading edge.

**Reference:** objective expected states: final_stored_volume = 285000 m3.
**Sources:** Néelz and Pender (2013); Néelz and Pender (2010).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| mass_conservation | expected_state_error of volume | abs<= 0.1 % | yes | The only exact statement the test admits: nothing leaves a closed domain, so any difference is mass created or lost by the scheme (suite target < 0.1 %). |

**Passes:** Demo 2D suite example, HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM, TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## A2C-EA5 — EA Test 5 — valley flooding

*intercomparison, version 1.0.0, candidate.* Dam-failure hydrograph (peak 3000 m³/s) released down a ~17 km valley whose slope eases from ~0.01 to ~0.001, producing both super- and subcritical flow, run to 30 h. Tests peak levels, velocities and travel times.

**Reference:** objective expected states: final_stored_volume = 9.45e+06 m3.
**Sources:** Néelz and Pender (2013); Néelz and Pender (2010).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| mass_conservation | expected_state_error of volume | abs<= 0.1 % | yes | The only exact statement the test admits: nothing leaves a closed domain, so any difference is mass created or lost by the scheme (suite target < 0.1 %). |

**Passes:** Demo 2D suite example, HEC-RAS 6.6 1D · 2D SWE-ELM, HEC-RAS 6.6 2D · SWE-EM, TELEMAC-2D openTELEMAC 9.1, ANUGA 4.0.1, LISFLOOD-FP 8.3 · FV1, LISFLOOD-FP 8.3 · DG2, LISFLOOD-FP 8.3 · ACC.  
**Fails:** none.

**Before it can be frozen:** maintainer review recorded (no maintainer review recorded).

## B-EPANET-001 — EPANET Net1 parity against EPANET 2.2

*parity, version 1.0.0, candidate.* EPANET Example Network 1 (9 junctions, 1 reservoir, 1 tank, 12 pipes, 1 pump; 24 h extended period). Candidate nodal pressures and link flows are compared element by element with EPANET 2.2.

**Reference:** pinned engine EPANET 2.2.
**Sources:** Rossman et al. (2020).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| peak_pressure | relative_peak of p | abs<= 1 % | yes | Nodal peak pressure within 1 % of EPANET 2.2 at every node. |
| link_volume | relative_volume of Q | abs<= 1 % | yes | 24 h conveyed volume within 1 % of EPANET 2.2 in every pipe and pump. |
| peak_timing | timing_error of Q | abs<= 3600 s | no | Informational: one reporting step. |

**Passes:** Hydra water distribution, EPANET 2.0 vs EPANET 2.2.  
**Fails:** none.

**Before it can be frozen:** reference reproduced by a second build (no second build of the reference engine scored yet); maintainer review recorded (no maintainer review recorded).

## B-EXTRAN-001 — EXTRAN Manual Example 1: parity against SWMM 5.2.4

*parity, version 2.0.0, candidate.* EXTRAN Manual Example 1 (Roesner et al. 1988) as distributed with the OWA/EPA SWMM 5 regression set: a dendritic sewer network with surcharge and three hydrograph inflows, 8 h dynamic-wave routing. Candidate depths and flows are compared with EPA SWMM 5.2.4 at every node and link. Case v2.0.0 replaces a 2-conduit synthetic fixture that v1 presented as this example.

**Reference:** pinned engine SWMM 5.2.4.
**Sources:** Roesner et al. (1988); HydroCouple (2026).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| peak_depth | relative_peak of h | abs<= 1 % | yes | Peak depth within ±1 % of SWMM 5.2.4 at every node. |
| volume | relative_volume of Q | abs<= 1 % | yes | Conveyed volume within ±1 % of SWMM 5.2.4 in every link. |

**Passes:** SWMM 5.1.15 vs SWMM 5.2.4, OpenSWMM 6 vs SWMM 5.2.4.  
**Fails:** Hydra urban drainage.

**Before it can be frozen:** reference reproduced by a second build (no second build of the reference engine scored yet); maintainer review recorded (no maintainer review recorded).

## B-RTC-001 — Control-rule parity: pump stations switched by wet-well level

*parity, version 2.0.0, candidate.* A 90-node sanitary network (SI units) with two pump stations whose pumps are switched ON and OFF by IF/THEN rules on wet-well depth (e.g. pump U433_Psan_1_ou_2 switches 74 times in 36 h). Tests that a candidate evaluates control rules at the same moments as SWMM 5.2.4. Case v2.0.0 replaces EXTRAN Example 1 with a rule whose condition never changed, so v1 never exercised a switch.

**Reference:** pinned engine SWMM 5.2.4.
**Sources:** HydroCouple (2026); Rossman (2017).

| Check | Metric | Limit | Gating | Why this limit |
|---|---|---|---|---|
| peak_depth | relative_peak of h | abs<= 2 % | yes | Architecture parity band (±2 % peak) at every node, wet wells included. |
| link_volume | relative_volume of Q | abs<= 2 % | yes | Pumped and conveyed volume within ±2 % in every link: a rule that fires at the wrong level changes how much each pump moves. |
| peak_timing | timing_error of Q | abs<= 120 s | yes | Four 30 s reporting steps; a rule evaluated at a different moment shifts pump-on times. |

**Passes:** SWMM 5.1.15 vs SWMM 5.2.4.  
**Fails:** Hydra urban drainage, OpenSWMM 6 vs SWMM 5.2.4.

**Before it can be frozen:** reference reproduced by a second build (no second build of the reference engine scored yet); maintainer review recorded (no maintainer review recorded).

