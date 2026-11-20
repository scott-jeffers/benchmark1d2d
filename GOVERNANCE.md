# Governance

## Automation charter

The suite runs itself. Results are produced, checked and published by CI
without human approval, notice periods or embargoes
([evidence protocol 4.0](docs/methodology/evidence.md), §6). People take part
by *adding* things: a case, a dataset, an adapter, a better configuration. The
pipeline does the rest:

- runs every configuration on every grid
- scores each run with the frozen scorer
- checks that references still reproduce
- republishes the site and its data exports
- reruns submitted configurations, and promotes a configuration that does better across its capability group to the T2 shown

Only three decisions are left to people. None of them is on the publishing
path:

| Decision | Why it can't be automated | How |
| --- | --- | --- |
| Changing the protocol: kinds of evidence, tiers, metrics, significance values | It defines the standard | An ADR, a protocol version bump and a changelog entry |
| Accepting a new case or dataset as a reference, and freezing it | Someone must judge that the truth is right | The promotion rules ([promotion.md](docs/methodology/promotion.md)); rules 1–7 are computed, rule 8 is one recorded review |
| Fixing an adapter when an engine changes its file format | The format break is new information | A normal PR, flagged by the failing run |

Everything else is the machine's job. A results page never waits on a
person, and nobody can hold a result back.

## Maintainers

- Technical lead / initial author: @Scott (OpenHydro)
- Additional maintainers are added by consensus of the current maintainers.
- Planned: a steering group with balanced seats from agencies, academia, practice and developers, and published conflict-of-interest declarations ([draft charter](docs/submission/steering_group_charter.md), [declaration form](docs/submission/conflict_of_interest_form.md)). It holds the three decisions above and nothing else.

## Technical steering

Architecture Decision Records in [`docs/adr/`](docs/adr/) document irreversible
choices. Changes to the **contract** (`schemas/v1/`) require:

1. A new ADR if the change is behavioural.
2. A schema semver bump.
3. A changelog entry and regenerated example manifests.

Code changes that do not alter schemas follow normal PR review.

## Frozen cases

Only manifests with `status: frozen` have fixed inputs and answers, so only
their results are comparable across releases. A frozen case is never edited in
place: any change to its inputs, reference or tolerances bumps `case_version`.
There are no certification levels and no pass marks (ADR-0004).

## External liaison

- **ASCE / EWRI**: reviewer packet in `docs/submission/`.
- **U.S. EPA**: pinned SWMM / EPANET reference builds; liaison via maintainers.
- **HydroCouple**: Track B federates the `openswmm.engine.benchmarks` tag
  vocabulary and provenance format. Do not fork the corpus.

## Naming

The public product name is **Benchmark1d2d** (Python/CLI package: `benchmark1d2d`).
It is distinct from the EMScience HydroBench hydrological diagnostic toolkit.
The display name may be revised before the `v1.0.0` freeze and Zenodo DOI.
After that, a rename requires a redirect alias so existing citations remain valid.

## Releases

Suite releases are tagged `vX.Y.Z`. `v1.0.0` freezes the catalogue and mints a
Zenodo DOI. Schema versions are independent of suite versions.
