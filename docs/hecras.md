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
| A1F-010 / 011 dam breaks | next | 1D unsteady needs a dam and instantaneous breach to start from a step; dry bed needs HEC-RAS's minimum-depth handling |
| A1F-020 stationary jump | not applicable | a steady solver places a jump by momentum balance, which is neutral on a frictionless flat bed; the case tests a time-marching solver holding the jump |
| 2D cases (A2A, A2C) | needs meshes | see below |

## Adding a 2D case

A 2D flow area needs a computational mesh and a terrain built by RAS Mapper.
Once per case, someone with HEC-RAS 6.6 on Windows:

1. Creates a project in `test_catalog/<case>/solvers/hecras/`, imports the
   case's terrain (or builds the flat/analytic surface) and draws the 2D area
   covering the case domain.
2. Sets the cell size to the case's finest refinement level, adds the case's
   boundary conditions, and saves (geometry `.g01` plus its `.g01.hdf`).
3. Commits the project folder without results (`*.p??.hdf`, `*.dss`, `*.tmp`).

CI then re-runs it on every change. `ras-commander` 0.105 also offers
headless mesh generation (`GeomMesh`, HEC-RAS 6.6 + pythonnet), which may let
CI build these meshes itself; that is worth trying before doing it by hand.

## Findings so far

- HEC-RAS 6.6 stores input elevations to the nearest 0.001 ft (0.3 mm), even
  in an SI project: every cross-section invert and the known downstream water
  surface come back on that grid. On A1F-001 the depth error is 0.1 mm on
  every grid — well inside the 1 cm tolerance — so finer grids cannot show
  convergence and the convergence criterion fails.
