# A1P-020 — Joukowsky instant valve closure

## Physics

Frictionless pipe of length \(L\) with reservoir at \(x = 0\) and valve at
\(x = L\). Steady velocity \(V_0\) toward the valve; instantaneous full
closure at \(t = 0\). Before the first upstream reflection
(\(0 \le t \le L/a\)) the closed-end state propagates at celerity \(a\) with
pressure rise \(\Delta p = \rho a V_0\). Default parameters:
\(L = a = 1000\), \(V_0 = 1\), \(\rho = 1000\) so \(\Delta p = 10^6\,\mathrm{Pa}\)
and first reflection at \(t = 1\,\mathrm{s}\).

## Mass balance

Until the first reflection the reservoir end still delivers \(V_0\) while the
valve is shut, and the pipe stores that inflow by compressing the water and
stretching the wall. Per unit area the stored volume is
\(\int \Delta p \,dx / (\rho a^2)\), so

$$\int_0^L \Delta p\,dx = \rho a^2 V_0 t ,$$

whatever the front's shape. The `storage_balance` criterion checks this
identity; it does not depend on how sharply a scheme resolves the front.

## Case history

- **3.0.0** — the `continuity` criterion (mean \(|u|\) behind the front)
  measured front smearing rather than mass, and failed accurate first-order
  schemes. It is replaced by the storage balance above. Scores are not
  comparable with 2.x.
- **2.0.0** — convergence target set from theory (0.5, minimum 0.4).

## Citation

Joukowsky, N. (1900). "Über den hydraulischen Stoss in Wasserleitungsröhren."
*Mémoires de l'Académie Impériale des Sciences de St.-Pétersbourg*, Series 8,
9(5). English translation: Simin, O. (1904). "Water hammer."
*Proc. Am. Water Works Assoc.*, 24, 341–424.

Analytic generator: `references.joukowsky.pressure_wave`.

## Pitfalls

- Score only before the first reflection; after \(t > L/a\) the simple
  step-wave formula is invalid.
- Numerical dispersion smears the pressure front; peak_error on \(p\) is more
  robust than pointwise L∞ near the discontinuity.
- Elastic wave speed \(a\) must match the solver's pipe/fluid compressibility
  model; mismatched \(a\) shifts both timing and \(\Delta p\).
- Instantaneous closure is an idealization — finite closure laws will under-
  predict the classic Joukowsky rise.
