# A1D-005 — Backwater through a chain of manholes

## Physics

Twenty 1.2 m circular pipes (50 m each, \(n = 0.013\), slope 0.001) carry
0.6 m³/s to an outfall held 1.0 m above its invert. Normal depth is 0.59 m and
critical depth lower, so the flow is subcritical and the outfall level backs up
an M1 profile,

\[ \frac{dy}{dx} = \frac{S_0 - S_f}{1 - Fr^2}, \quad S_f = \frac{n^2Q^2}{A^2R^{4/3}},\ Fr^2 = \frac{Q^2 T}{g A^3}, \]

integrated upstream from the outfall, pipe by pipe, with an adaptive
eighth-order Runge–Kutta method (DOP853, relative tolerance \(10^{-11}\)). The
manholes have no losses and the inverts are continuous, so depth is continuous
through every manhole. A pipe's reference depth is the profile at its
midpoint.

## What it checks

Gradually varied flow in a network: friction, the circular section and the
convective term together. A link–node model represents each pipe by its end
heads and a mid-pipe depth; on 50 m pipes that costs a few millimetres at most.

## Citation

Chow, V. T. (1959). *Open-Channel Hydraulics*. McGraw-Hill.
Rossman, L. A. (2017). *SWMM Reference Manual Volume II – Hydraulics*. EPA/600/R-17/111.
