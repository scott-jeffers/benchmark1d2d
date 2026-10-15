# A12-010 — Manhole surcharge onto a sloping street

## Physics

A 0.6 m pipe brings a constant 0.5 m³/s to manhole M1, which has no outlet
(its only other connection is a 1 m stub to a flap-gated outfall that never
opens, because SWMM-family engines need an outfall). The manhole surcharges
onto a 10 m wide, 200 m long street that falls at \(S = 0.005\) (Manning
\(n = 0.02\)), walled on three sides and open at its foot.

Two answers follow exactly at steady state:

* **Exchange**: the manhole must pass the whole inflow, \(Q = 0.5\) m³/s.
* **Street depth**: below the manhole the flow becomes uniform sheet flow of
  \(q = Q/B = 0.05\) m²/s. With the depth as hydraulic radius (as in every 2D
  shallow-water model), \(h = (n q / \sqrt{S})^{3/5} = 77.7\) mm.

The street's foot is held at that normal depth, so the depth 75 and 125 m
below the manhole tests what the manhole released, not the outflow boundary.

## What it checks

That the network-to-surface exchange delivers the network's flow onto the 2D
mesh, all of it and nothing more, and that the coupled model balances its
water. The exchange coefficients in `inputs/coupling.json` (weir 0.5, orifice
0.6, a 0.6 m grate) are for engines that need them; the scored states do not
depend on them.

## Citation

Chen, A. S., Djordjević, S., Leandro, J., and Savić, D. A. (2007). The urban
inundated area: a coupled 1D/2D model for the interaction between sewer and
surface. *Proc. NOVATECH 2007*.
