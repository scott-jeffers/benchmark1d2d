# A1P-010 — Todini multi-loop network

## Physics

The Alperovits–Shamir two-loop gravity network: one reservoir at 210 m, six
junctions, eight 1 km pipes with Hazen–Williams \(C = 130\). Steady flow
satisfies continuity at every junction and zero head loss around each loop.
The reference is the Todini–Pilati global gradient algorithm iterated to
\(|\Delta H| < 10^{-12}\) m, which is exact for practical purposes.

## What it checks

That a network solver closes mass and energy balances to its stated accuracy.
Flows depend only on the balances, so they must agree to 0.1 %. Heads also
depend on the Hazen–Williams coefficient's SI form (10.667 here; EPANET's
US-unit 4.727 converts to ≈ 10.67), so they are held to 5 cm. EPA EPANET 2.2
agrees to under 1 mm and 0.001 %.

Node and pipe names overlap ("1"–"7" are both): results must carry
`element_type` so the scorer can tell them apart.

## Citation

Todini, E., and Pilati, S. (1988). "A gradient algorithm for the analysis of
pipe networks." *Computer Applications in Water Supply*, Vol. 1, 1–20.
Alperovits, E., and Shamir, U. (1977). "Design of optimal water distribution
systems." *Water Resour. Res.*, 13(6), 885–900.
