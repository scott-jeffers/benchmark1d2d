# A1D-002 — Surcharged pipes: hydraulic grade line

## Physics

Five 0.6 m circular pipes (100 m each, \(n = 0.013\), slope 0.001) carry
0.3 m³/s to an outfall held 1.5 m above its invert, well above every pipe's
crown, so all five run full. With no junction losses, the hydraulic grade line
falls along each pipe by the Manning friction loss of a full pipe,

\[ \Delta H = \frac{n^2 Q^2 L}{A^2 R^{4/3}}, \quad A = \pi D^2/4,\ R = D/4, \]

0.239 m per pipe, 1.19 m over the five. The reference checks that the grade line stays above every
crown, so the answer is exact.

## What it checks

How an engine solves heads in surcharged pipes (SWMM's EXTRAN surcharge
iteration, a Preissmann slot, a pressurised finite-volume cell). Manhole
depths are scored against the grade line; pipe depths are not (a full pipe's
"depth" is its diameter, or a slot depth, by convention).

## Citation

Chow, V. T. (1959). *Open-Channel Hydraulics*. McGraw-Hill.
Rossman, L. A. (2017). *SWMM Reference Manual Volume II – Hydraulics*. EPA/600/R-17/111.
