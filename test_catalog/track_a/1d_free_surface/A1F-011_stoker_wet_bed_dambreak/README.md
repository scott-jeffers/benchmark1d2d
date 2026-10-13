# A1F-011 — Stoker wet-bed dam break

## Physics

Riemann dam-break problem with left depth \(h_l = 1\,\mathrm{m}\), right depth
\(h_r = 0.1\,\mathrm{m}\), both initially at rest. The exact inviscid solution
(Stoker, 1957) comprises a left rarefaction, a constant intermediate state
\((h^*, u^*)\), and a right-going shock. Generator:
`references.stoker.depth_velocity`.

## Citation

Stoker, J. J. (1957). *Water Waves: The Mathematical Theory with Applications*.
Interscience, New York. ISBN 978-0-471-57034-9 (Wiley Classics Library reprint).

## Pitfalls

- Shock smearing dominates L1(\(h\)); observed order near 1 is expected for
  first-order Godunov schemes even when the rarefaction is well resolved.
- Incorrect intermediate-state solvers or approximate Riemann solvers with
  large entropy glitches can shift the shock speed.
- Keep Courant number fixed across refinement (`fixed_courant: 0.5`).
- Do not treat this as a dry-bed case: \(h_r > 0\) removes the wet/dry front
  pathology of A1F-010.
