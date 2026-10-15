# A1D-001 — Normal depth in partly full circular pipes

## Physics

Three independent chains of ten 1.0 m circular pipes (100 m each, Manning
\(n = 0.013\), slope 0.002) carry 0.15, 0.5 and 1.0 m³/s from a constant
inflow to an outfall at normal depth. At steady state the flow in every pipe
is uniform, so its depth is the root of

\[ Q = \frac{1}{n} A R^{2/3} S^{1/2}, \quad A = \tfrac{D^2}{8}(\theta - \sin\theta),\ P = \tfrac{D\theta}{2},\ \theta = 2\arccos(1 - 2y/D) \]

solved by bisection to \(10^{-13} D\): 0.253, 0.480 and 0.765 m.

## What it checks

The circular section and the friction law, with nothing else in play. Every
pipe and every interior manhole is scored; the inflow and outfall manholes are
not (their depth depends on how an engine treats a chain's ends), but the last
pipe is, so an engine's normal-depth outfall must hold normal depth.

SWMM-family engines store a circular pipe's area and hydraulic radius in
51-entry tables; EPA SWMM 5.2.4 is 0.27 mm off for that reason. An engine with
exact geometry agrees to rounding.

## Citation

Chow, V. T. (1959). *Open-Channel Hydraulics*. McGraw-Hill.
Rossman, L. A. (2017). *SWMM Reference Manual Volume II – Hydraulics*. EPA/600/R-17/111.
