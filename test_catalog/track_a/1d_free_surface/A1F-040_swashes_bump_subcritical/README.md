# A1F-040 — Subcritical flow over a bump (SWASHES)

## Physics

A frictionless 25 m channel with a parabolic bump
\(z = 0.2 - 0.05 (x - 10)^2\) on \(8 < x < 12\) carries \(q = 4.42\) m²/s,
held at 2 m downstream. In steady flow the discharge is constant and so is
the Bernoulli head, so at every point the depth is the subcritical root of

\[ \frac{q^2}{2 g h^2} + h + z = \frac{q^2}{2 g h_{out}^2} + h_{out}, \]

found to \(10^{-14}\) m (`references/swashes.py`). The surface dips to
1.71 m over the crest. The run starts from still water at 2 m and lasts
300 s.

## What it checks

The balance between the bed slope and the pressure gradient in moving water,
and that a steady state carries the same discharge everywhere.

## Citation

Delestre, O., et al. (2013). SWASHES: a compilation of shallow water analytic
solutions for hydraulic and environmental studies. *Int. J. Numer. Meth.
Fluids*, 72(3), 269–300. doi:10.1002/fld.3741. Goutal, N., and Maurel, F.
(1997), EDF report HE-43/97/016/B.
