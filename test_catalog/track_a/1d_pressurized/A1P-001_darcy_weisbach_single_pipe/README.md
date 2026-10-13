# A1P-001 — Darcy–Weisbach single pipe

## Physics

Steady flow from a reservoir (head 100 m) through a horizontal pipe,
\(L = 1000\) m, \(D = 0.3\) m, roughness \(\varepsilon = 0.15\) mm, withdrawn at
\(V = 1\) m/s. With \(\nu = 10^{-6}\) m²/s, \(Re = 3.0\times10^5\) and the
Colebrook–White equation, solved to machine precision, gives
\(f = 0.018210\). The exact head loss is

$$\Delta h = f\,\frac{L}{D}\,\frac{V^2}{2g} = 3.094\ \text{m},$$

and the hydraulic grade line falls linearly along the pipe.

## What it checks

The friction law a solver uses and how it applies it. Explicit formulas
(Swamee–Jain, Haaland) are within about 1 % of Colebrook–White in this range,
so they pass; a fixed friction factor, the wrong viscosity or a units error
fails. EPA EPANET 2.2, which uses Swamee–Jain, comes out 0.60 % high, as
theory predicts (0.65 %).

## Case history

- **1.0.0** — friction factor from Colebrook–White instead of a fixed
  \(f = 0.02\); head-loss metric relative to the exact drop; grid convergence
  marked not applicable (steady closed-form flow).

## Citation

Colebrook, C. F. (1939). "Turbulent flow in pipes, with particular reference
to the transition region between the smooth and rough pipe laws." *J. ICE*,
11(4), 133–156. Swamee, P. K., and Jain, A. K. (1976). "Explicit equations for
pipe-flow problems." *J. Hydraul. Div.*, 102(5), 657–664.
