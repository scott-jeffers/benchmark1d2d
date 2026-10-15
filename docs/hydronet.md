# HydroNet (Penn State, psu-efd)

[HydroNet](https://github.com/psu-efd/HydroNet) (MIT licence) is a PyTorch
framework for the 2D shallow-water equations with physics-informed deep
learning: a classical PINN, PI-DeepONet operator learning, and FVM-PINN, a
network trained against a differentiable, well-balanced Roe finite-volume
residual on unstructured meshes. It is a research code; it is scored with
the settings of its own examples, as two solvers:

| Column | What runs | Settings |
|---|---|---|
| HydroNet · finite volume | `run_fvm_rk2`: the Roe finite-volume solver with Heun RK2 time stepping that FVM-PINN's residual and its `*_fvm_only.py` drivers use | CFL 0.3 (its default) |
| HydroNet · FVM-PINN | `FVM_SWE_PINN` trained on each grid, evaluated at the cell centres at the end time | the recipe of its `examples/FVM_PINN/dam_break_1d`: 64×5 Fourier-feature MLP, 5000 Adam epochs, IC + FVM-residual losses, no reference data |

Both run on HydroNet's own mesh structure (`build_mesh` from SRH-2D-style raw
data) with the case's grid as quad cells; the bed is given at the nodes
(HydroNet averages the four per cell). Walls are its default reflective
boundaries; the momentum dry threshold `h_dry` is 1e-4 m, as in its dam-break
example. Runner: `scripts/run_hydronet.py --hydronet <checkout>`; it needs
PyTorch (CPU is enough) and pyHMT2D, which HydroNet imports.

## Findings for the developers

1. **A dam break onto a dry bed never starts** (A1F-010). The residual is
   called with its default `h_small = 1e-2` (`compute_fvm_residual` in
   `_internal/fvm/riemann_solver.py`; `run_fvm_rk2`'s `h_dry` only zeroes
   momentum and does not reach it). At a face between a wet and a dry cell
   the flux is the wet cell's own physical flux, so still water next to a dry
   cell gets equal and opposite pressure on its two faces and no net force:
   nothing moves. The same happens when the downstream layer is under 1 cm
   (a 1 m dam break into 1 cm of water does not move in a small test; into
   10 cm it runs normally).
2. **The Thacker bowl goes unstable on grids finer than 10 cm** (A2A-001,
   a 10 cm-deep laboratory-scale bowl). Momentum grows near the moving
   shoreline from about 0.4 s and every cell is NaN by 0.7 s on the 5 cm
   grid; the same at CFL 0.1 and 0.05 and with `h_dry` from 1e-4 to 1e-2, so
   it is not a time-step limit. The fixed 1 cm dry threshold is a tenth of the
   bowl's depth, which is a likely cause. No score card is published for it.
3. **Stoker (A1F-011) runs normally**: depth error 1.4 mm, mass 0.016 %, but
   the error falls at order 0.69 (minimum 0.8).

FVM-PINN results: see the score cards (`site/fixtures/hydronet/pinn/`).
