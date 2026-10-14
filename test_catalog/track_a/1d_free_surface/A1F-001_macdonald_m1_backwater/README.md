# A1F-001 — MacDonald M1 subcritical backwater

## Physics

Steady rectangular-channel flow with constant discharge \(Q\) and Manning
friction. A smooth depth profile \(h(x)\) is prescribed; the bed \(z_b(x)\) is
manufactured so that the steady Saint-Venant equations hold exactly
(MacDonald et al., 1997). Default M1 parameters live in
`references.macdonald.M1_PARAMS` (\(L = 1000\,\mathrm{m}\), \(B = 10\,\mathrm{m}\),
\(Q = 2\,\mathrm{m^3\,s^{-1}}\), \(n = 0.03\)).

## Citation

MacDonald, I., Baines, M. J., Nichols, N. K., and Samuels, P. G. (1997).
"Analytic benchmark solutions for open-channel flows."
*J. Hydraul. Eng.*, 123(11), 1041–1045.
https://doi.org/10.1061/(ASCE)0733-9429(1997)123:11(1041)

Analytic generator: `references.macdonald.depth_profile` (case `m1`).

## Pitfalls

- Errors in bed slope / friction source terms (well-balanced vs non-balanced
  discretizations) dominate depth error on coarse meshes.
- Reach steady state before scoring; transient residuals pollute L1(\(h\)).
- Boundary conditions must match the analytic subcritical regime (downstream
  depth control).
- Use the manufactured bed from the same parameter set as the depth profile;
  mismatched \(n\) or \(Q\) voids the exactness property.

## Case history

- **1.1.0** — `inputs/params.json` described a 1 m channel with n = 0.033,
  contradicting the reference (10 m, n = 0.03, wide-channel hydraulic radius).
  The inputs now state the reference's parameters, the exact downstream depth
  and that only friction losses apply. The reference is unchanged, so scores
  from solvers that used the reference parameters are comparable.

