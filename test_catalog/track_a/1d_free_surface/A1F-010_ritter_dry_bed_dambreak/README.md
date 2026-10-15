# A1F-010 — Ritter dry-bed dam break

## Physics

Instantaneous dam break of still water of depth \(h_0 = 1\,\mathrm{m}\) at
\(x_0 = 1000\,\mathrm{m}\) onto a dry frictionless bed. The exact inviscid
1D Saint-Venant solution is a left-going rarefaction and a wet/dry front that
advances as \(x_f(t) = x_0 + 2 t \sqrt{g h_0}\). At \(t = 60\,\mathrm{s}\)
with \(g = 9.81\,\mathrm{m\,s^{-2}}\) the front is at \(1375.8\,\mathrm{m}\).

## Citation

Ritter, A. (1892). "Die Fortpflanzung der Wasserwellen."
*Zeitschrift des Vereines Deutscher Ingenieure*, 36(33), 947–954.
Report identifier: ZdVDI 36(33).

Analytic generator: `references.ritter.depth_velocity`.

## Front check (v2.0.0)

The gating front is **integral**: the abscissa beyond which lies the last 5 %
of the water downstream of the dam, exactly \(x_0 + 2c_0 t\,(1-0.05^{1/3})\)
= 1237.4 m at 60 s, within 2.5 m. Version 1 used the 1 mm depth contour
(~1358 m). On the thin tip that contour moves about 10 m per millimetre of
depth error, and production codes treat depths under ~1 mm as dry, so every
production code failed it by 12–211 m while their wave bodies were close. It
is still reported, but no longer gates.

## Pitfalls

- Wet/dry treatment and positivity-preserving fluxes dominate front error;
  schemes that clip negative depths can lag the front systematically.
- First-order Godunov methods typically achieve observed order \(\approx 1\)
  in L1(\(h\)); do not expect second-order near the front.
- Mass conservation must be measured against the continuous conserved volume
  (including dry cells), not against a wet-only mask.
- Mesh spacings must keep Courant number fixed across the refinement study
  (`fixed_courant: 0.5`).
