# A1F-020 — Bélanger hydraulic jump

## Physics

On a horizontal frictionless bed, supercritical flow \(h_1 = 0.2\) m,
\(Fr_1 = 2.5\) meets the sequent depth held downstream,

$$\frac{h_2}{h_1} = \tfrac12\left(\sqrt{1 + 8Fr_1^2} - 1\right) = 3.05 .$$

The jump conserves mass and momentum and dissipates energy. Started from the
exact step at \(x = 50\) m, it must stay there: on a frictionless bed its
position is neutral, so any imbalance in the scheme shows up as drift.

## What it checks

Shock capturing of a stationary jump: the conjugate depths, the
Rankine–Hugoniot balance (no drift) and convergence of the captured profile
at order 1 in L1, which is what any consistent shock-capturing scheme
achieves. The demo first-order HLL solver holds the jump within one cell and
converges at 1.00.

## Case history

- **1.0.0** — grids 2, 1, 0.5, 0.25 m (the draft's 20 m grid had five cells
  in the channel); criteria on the relative L1 profile error and the stored
  volume.

## Citation

Bélanger, J.-B. (1828). *Essai sur la solution numérique de quelques
problèmes relatifs au mouvement permanent des eaux courantes*. Paris.
Chow, V. T. (1959). *Open-Channel Hydraulics*, ch. 15. McGraw-Hill.
