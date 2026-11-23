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
- reruns proposed set-ups (`setups/`) weekly and shows each beside the suite's own result, under its proposer's name, never in its place
- publishes, for every result, the settings, the model files the solver read and what it wrote ("Check this result")
- measures how much reasonable settings move each result (sensitivity envelopes)

Only three decisions are left to people. None of them is on the publishing
path:

| Decision | Why it can't be automated | How |
| --- | --- | --- |
| Changing the protocol: kinds of evidence, tiers, metrics, significance values | It defines the standard | An ADR, a protocol version bump and a changelog entry |
| Accepting a new case or dataset as a reference, and freezing it | Someone must judge that the truth is right | The promotion rules ([promotion.md](docs/methodology/promotion.md)); rules 1–7 are computed, rule 8 is one recorded review |
| Fixing an adapter when an engine changes its file format | The format break is new information | A normal PR, flagged by the failing run |

Everything else is the machine's job. A results page never waits on a
person, and nobody can hold a result back.

## Who runs a result, and checking it

"The modeller built a bad model" is answered by making every result checkable
and every set-up challengeable, not by argument:

- **Every result can be checked.** Each result's *Check this result* box gives
  the settings changed from the engine's defaults and why, the exact files the
  solver read, what it wrote (as release files, too large for the website),
  the signed score card, and the commands to run it again.
- **Every set-up can be challenged.** Anyone may propose a different set-up for
  a model the suite can re-run (`setups/<slug>/setup.json`, or the *Propose a
  better set-up* issue form). The suite applies it to its own model files, runs
  it on its own machines and shows the result beside its own, under the
  proposer's name and GitHub account. Nobody approves it and nothing is
  replaced. Settings the test defines (geometry, boundaries, friction, grid,
  end time) cannot change, so every set-up solves the same problem.
- **Developers are invited, not consulted.** A software's developer may
  propose their recommended set-up at any time; it is marked as theirs, and as
  T1 when it follows their published guidance. There is no right of reply,
  notice period or embargo: results are published as they are produced.
- **How much the set-up matters is measured.** Each model the suite can re-run
  is swept one documented option at a time; the range is shown on every test.

Every result carries one of five labels, so an engineer knows who ran it and
whether it can be checked:

| Label | Who ran it | Can anyone check it? |
| --- | --- | --- |
| Run by the suite | The suite, on its own machines | Yes: model files, outputs and commands are published |
| Proposed set-up, run by the suite | The suite, with someone else's settings | Yes, as above |
| Run on the owner's machine | The software's owner, on their licensed machine, through the suite's workflow (`owner-run.yml`, [guide](docs/owner-runner.md)) | With a licence: model files are published when the owner's command keeps them |
| Submitted, with model files | The submitter | With a licence: model files are published |
| Submitted results only | The submitter | No: shown, but labelled |

**Commercial licences.** Some software licences restrict publishing benchmark
results. The suite runs only software whose licence allows it, and publishes
owner-run and submitted results on the understanding, confirmed by the person
who sends them, that they may be published. A result whose owner shows it was
published against their licence is removed; the removal is recorded in the
changelog. No other result is ever withdrawn on request.

## Maintainers

- Technical lead / initial author: Scott Jeffers
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
