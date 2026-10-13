# A1P-030 — Advection–dispersion tracer

## Physics

A tracer enters a uniform flow \(u = 0.1\) m/s at \(x = 0\) with \(c = c_0\)
from \(t = 0\); dispersion \(D = 0.01\) m²/s. Ogata & Banks (1961) give

$$\frac{c}{c_0} = \tfrac12\left[\operatorname{erfc}\frac{x-ut}{2\sqrt{Dt}} + e^{ux/D}\operatorname{erfc}\frac{x+ut}{2\sqrt{Dt}}\right].$$

After one hour the front is at 360 m and about 8.5 m wide.

## What it checks

Advection without excess numerical diffusion. A first-order upwind scheme adds
\(u\,\Delta x/2\), already 2.5 × \(D\) on a 0.5 m grid, and smears the front;
a second-order TVD scheme should converge at order 2 on this smooth, monotone
profile (minimum 1.6). The demo solver (MUSCL with van Leer limiter, central
diffusion, SSP-RK2) reaches 1.67 across the four grids: its coarsest grid is
half the front width, so the asymptotic order of 2 only shows on the finer
pairs (1.8).

## Citation

Ogata, A., and Banks, R. B. (1961). *A Solution of the Differential Equation
of Longitudinal Dispersion in Porous Media*. USGS Professional Paper 411-A.
