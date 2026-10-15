# HEC-RAS in CI

HEC-RAS is free, public-domain software from the U.S. Army Corps of Engineers
Hydrologic Engineering Center (HEC). It runs on Windows, so it is scored by its
own workflow, `.github/workflows/hecras.yml`, on `windows-latest`:

1. **Install.** HEC-RAS 6.6 is downloaded from HEC's release
   (`HydrologicEngineeringCenter/hec-downloads`, tag 1.0.33), checked against a
   pinned SHA-256 and installed silently (`/S /v/qn`).
2. **Terms.** HEC-RAS shows its Terms and Conditions for Use (TCU) the first
   time a user runs it, which would block an unattended run. With
   `--accept-hec-terms` the runner records acceptance for the CI user, exactly
   what clicking "I Agree" stores (`HKCU\Software\VB and VBA Program Settings\
   <install folder>\ras.exe\Projects`, value `System Statistic`). By enabling
   this workflow the repository owner accepts HEC's terms:
   <https://www.hec.usace.army.mil/software/hec-ras/>.
3. **Build.** `scripts/run_hecras.py` writes a plain-text HEC-RAS project
   (`.prj`, `.g01`, `.f01`, `.p01`) for every refinement level of a case.
4. **Run.** `ras-commander` runs each plan through HEC-RAS's command line,
   watching for dialogs. If a run stalls, the runner logs the open windows and
   saves a screenshot to the job artifact.
5. **Score.** Results are read from the plan HDF and scored like any solver.

## Cases

| Case | Status | Notes |
|---|---|---|
| A1F-001 MacDonald backwater | running | steady standard step; 100 km stand-in width so hydraulic radius = depth; step tolerance 0.01 mm |
| A1F-010 / 011 dam breaks | running (2D) | headless 2D strip, SWE-ELM and SWE-EM (`scripts/run_hecras_2d.py`) |
| A1F-020 stationary jump | not applicable | a steady solver places a jump by momentum balance, which is neutral on a frictionless flat bed; the case tests a time-marching solver holding the jump |
| A2A-010 MacDonald 2D | running (2D) | flow hydrograph in, stage out on boundary lines; uniform start depth by restart file (`scripts/run_hecras_2d_cases.py`). 0.06–0.09 mm, but errors level off near 0.1 mm (order 0.39 / 0.67) |
| A2C-EA1, 2, 4, 5 | running (2D) | the EA's own DEMs as sub-grid terrain; EA 1, 4 and 5 pass; EA 2 fails mass (HEC-RAS's own accounting: +1.4 %) |
| A2A-001 Thacker | not yet | needs a 1 s run with sub-second output; HEC-RAS plan times are whole minutes |
| A2A-020 oblique jump | not yet | needs depth and both velocity components fixed at an inflow, which HEC-RAS boundary types do not take |

## 2D, fully headless

`scripts/run_hecras_2d.py` builds and runs a 2D model with no GUI step:

1. **Terrain.** The bed is written as a GeoTIFF (UTM 18N, metres) and turned
   into a HEC-RAS terrain with HEC-RAS's own `RasProcess.exe CreateTerrain`.
2. **Mesh.** HEC-RAS builds a 2D mesh from the cell-centre seed points stored
   in the geometry text (`Storage Area 2D Points`). Seeds on the case's regular
   grid give square cells, the grid every other solver uses.
3. **Geometry.** Ras.exe compiles the text geometry; the terrain is associated
   through RasMapperLib (`ras-commander` + `pythonnet`), and property tables
   are computed.
4. **The dam-break step.** HEC-RAS 2D starts from one flat level per area, a
   restart file or earlier results. A one-minute still-water run at the
   upstream level writes a restart file; in it the per-cell water surface is
   the one run of doubles equal to round-off (stored in feet), and the cells downstream
   of the dam are set to the downstream level. The dam-break plan starts from
   that file ("Initial conditions read from the file … .rst" in its log, with
   the expected starting volume).
5. **Run and score** with both full shallow-water options: SWE-ELM (the
   default when SWE is chosen) and SWE-EM (which HEC recommends for dam breaks).
   HEC-RAS rejects a Manning n of zero, so n = 0.0001 stands in for the
   frictionless reference (friction slope below 1e-7 here).

Other 2D cases need inflow and level boundary lines (`BC Line` entries in the
geometry and the matching unsteady-flow boundaries); the same pipeline applies.

## Findings so far

- HEC-RAS 6.6 stores input elevations to the nearest 0.001 ft (0.3 mm), even
  in an SI project: every cross-section invert and the known downstream water
  surface come back on that grid. On A1F-001 the depth error is 0.1 mm on
  every grid — well inside the 1 cm tolerance — so finer grids cannot show
  convergence and the convergence criterion fails.
- HEC-RAS 6.6 2D, dam break onto dry ground (A1F-010): the flood front
  advances as a steep bore that stops 209 m (SWE-ELM) or 161 m (SWE-EM) short
  of the exact front after 60 s, and the depth error does not fall on finer
  grids (observed order 0.07 and 0.01). Into shallow water (A1F-011) the depth
  error is 5–8 mm, inside the 5 cm limit, but again does not fall with the grid
  (order 0.20 and −0.14). Water is conserved to 0.01 % in every run.

## Boundary lines and EA tests

`scripts/run_hecras_2d_cases.py` extends the headless pipeline with boundary
lines (`BC Line ...` in the geometry text, a hair outside the area's edge as
RAS Mapper draws them; EA Test 5's inflow line is internal) and their flow or
stage hydrographs in the unsteady-flow text. HEC-RAS writes its results HDF at
the *mapping* interval, so that is set to the probe interval. Depths written
to the results are each cell's water volume over its plan area, integrated
from the same terrain pixels, with the cell's mean ground level as the bed;
HEC-RAS's own volume accounting is logged next to it.

