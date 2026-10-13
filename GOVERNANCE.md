# Governance

## Maintainers

- Technical lead / initial author: @Scott (OpenHydro)
- Additional maintainers are added by consensus of the current maintainers.

## Technical steering

Architecture Decision Records in [`docs/adr/`](docs/adr/) document irreversible
choices. Changes to the **contract** (`schemas/v1/`) require:

1. A new ADR if the change is behavioural.
2. A schema semver bump (`schemas/v1` → `schemas/v1.1` or `schemas/v2`).
3. A changelog entry and regenerating example manifests.

Code changes that do not alter schemas follow normal PR review.

## Certification change control

Only manifests with `status: frozen` count toward certification levels
(Verified A-V, Validated A-L / A-F, Parity B-x%). Freezing a case requires:

- Schema validation green
- License registered in [`DATA_LICENSES.md`](DATA_LICENSES.md)
- DOI / citation resolvable
- Two independent reviewers approving the tolerance rationale

## External liaison

- **ASCE / EWRI** — reviewer packet in `docs/submission/`
- **U.S. EPA** — pinned SWMM / EPANET reference builds; liaison via maintainers
- **HydroCouple** — Track B federates `openswmm.engine.benchmarks` tag vocabulary
  and provenance format; do not fork the corpus

## Releases

Suite releases are tagged `vX.Y.Z`. `v1.0.0` freezes the catalog and mints a
Zenodo DOI. Schema versions are independent of suite versions.
