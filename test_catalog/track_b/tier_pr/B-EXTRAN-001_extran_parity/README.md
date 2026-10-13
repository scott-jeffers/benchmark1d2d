# B-EXTRAN-001 — EXTRAN Manual Example 1 parity

The first example of the EXTRAN user's manual (Roesner, Aldrich and Dickinson, 1988), as carried in the OWA/EPA SWMM 5 regression models:
a dendritic sewer network with surcharge, driven by three inflow hydrographs and routed by dynamic wave for 8 hours.

The reference is EPA SWMM 5.2.4 (`swmm-toolkit` build; the official Windows binaries are checked against it in CI). A candidate passes when
every node's peak depth and every link's conveyed volume are within 1 % of the reference.

Source: HydroCouple `openswmm.engine.benchmarks`, `owa-extran/extran1`, commit `63eb8bc5b4e741c82195ed65c4d7d146b86da1cc`. Regenerate the reference with
`python scripts/make_reference.py B-EXTRAN-001`.

A Track B fail shows a difference from SWMM 5.2.4, not a physics error.
