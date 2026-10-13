# B-EXTRAN-001 — EXTRAN parity (SWMM 5.2.4)

## Physics

Track B industry-parity case. Candidate solvers are scored against a pinned
EPA SWMM 5.2.4 binary on an EXTRAN-style 1D sewer network (free-surface /
pressurized transitions, surcharge, and network routing). Ground truth is
**not** analytic — only engine-to-engine agreement within the stated band.

## Citation

Roesner, L. A., Aldrich, J. A., and Dickinson, R. E. (1988).
*Storm Water Management Model User's Manual, Version 4: EXTRAN Addendum*.
EPA/600/3-88/001b, U.S. EPA, Athens, GA.

Pinned engine: SWMM 5.2.4 (`binary_sha256` placeholder until the release
binary is recorded).

## License

`Unlicense` — see `DATA_LICENSES.md` (1729-SWMM5-Models / openswmm corpora).

## Pitfalls

- Do not interpret a Track B fail as a physics proof of incorrectness; it only
  shows difference from SWMM 5.2.4.
- Routing options, surcharge methods, and time-step controls must match the
  pinned engine settings recorded with the fixture.
- Replace the empty `network.inp` and binary hash placeholders before
  promoting beyond `candidate`.
