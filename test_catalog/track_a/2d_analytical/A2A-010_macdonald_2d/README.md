# A2A-010 — MacDonald 2D channel

## Physics

MacDonald's method: prescribe a smooth depth and a discharge, then build the
bed so the steady shallow-water equations with Manning friction hold exactly.
Here A1F-001's profile, \(h(x) = (4/g)^{1/3}\,[1 + \tfrac12 e^{-16(x/L - 1/2)^2}]\),
fills a 1000 m × 100 m channel with slip walls, unit discharge
\(q = 0.2\) m²/s and \(n = 0.03\). The flow is uniform across the channel, so
\(h = h(x)\), \(u = q/h\), \(v = 0\) over the bed

$$\frac{dz_b}{dx} = -\left(1 - \frac{q^2}{g h^3}\right)\frac{dh}{dx} - \frac{n^2 q^2}{h^{10/3}} .$$

## What it checks

That a 2D solver balances pressure, bed slope and friction on its own grid.
Only the inflow discharge and the outlet depth are imposed; the run starts at
a uniform depth and must settle onto the exact surface. The demo first-order
finite-volume solver converges at order 1.02.

## Case history

- **2.0.0** — the 1.x reference held the free surface flat while water flowed
  without friction, which is not a solution of the shallow-water equations;
  it is replaced by the construction above.
- **2.0.0, October 2026** — a typo in `inputs/params.json` (the text gave the
  downstream depth as 0.742 m) corrected to 0.748 m, the depth the reference
  and every run use. No result changes.

## Citation

MacDonald, I., Baines, M. J., Nichols, N. K., and Samuels, P. G. (1997).
"Analytic benchmark solutions for open-channel flows." *J. Hydraul. Eng.*,
123(11), 1041–1045. https://doi.org/10.1061/(ASCE)0733-9429(1997)123:11(1041)
