# A2A-020 — Oblique hydraulic jump

## Physics

Uniform supercritical flow, \(h_1 = 1\) m, \(Fr_1 = 2.5\), arrives at
\(\theta = 15°\) towards a straight slip wall and is turned parallel to it
through a straight jump from the wall's leading edge. The exact shallow-water
jump conditions (mass, normal momentum, continuous tangential velocity) give

$$\tan\theta = \frac{\tan\beta\,\left(\sqrt{1 + 8Fr_1^2\sin^2\beta} - 3\right)}{2\tan^2\beta + \sqrt{1 + 8Fr_1^2\sin^2\beta} - 1},$$

so \(\beta = 39.58°\) to the incoming flow (24.58° to the wall),
\(h_2/h_1 = 1.807\) and \(Fr_2 = 1.58\).

The case is posed in the wall frame on a Cartesian grid: the wall is the south
edge, the upstream state enters from the west and north, and the outflow to
the east is supercritical.

## What it checks

2D shock capturing at an angle to the grid: jump angle, conjugate depth and
L1 convergence at order 1. The demo first-order solver converges at 0.91.

## Case history

- **2.0.0** — the 1.x reference used the gas-dynamics θ–β–M relation (jump at
  34.0° instead of 39.6°) and labelled the region between wall and jump as
  upstream.

## Citation

Ippen, A. T. (1951). "Mechanics of supercritical flow." *Trans. ASCE*, 116,
268–295. Chow, V. T. (1959). *Open-Channel Hydraulics*, §17-5. McGraw-Hill.
