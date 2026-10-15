# A1D-003 — Storage draining through a power-law outlet

## Physics

A prismatic storage of plan area \(A = 100\) m², initially 2 m deep, drains
through an outlet rated \(Q = C h^b\) (\(C = 0.5\), \(b = 0.5\)) to a free
outfall 5 m below. Continuity, \(A\,dh/dt = -C h^b\), integrates to

\[ h(t)^{1-b} = h_0^{1-b} - (1-b)\frac{C t}{A}, \]

so after 300 s the depth is 0.4412 m and the outlet passes 0.3321 m³/s.

## What it checks

Storage continuity and the outlet rating through an unsteady drain-down: the
time integration of a single node, where an engine's error is its time
stepping alone.

## Citation

Rossman, L. A. (2017). *SWMM Reference Manual Volume II – Hydraulics*. EPA/600/R-17/111.
