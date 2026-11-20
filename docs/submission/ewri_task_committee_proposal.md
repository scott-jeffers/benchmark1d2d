# Proposal: EWRI Task Committee on Verification and Validation Evidence for 1D/2D Hydraulic Models

*Draft for the proposers to edit and submit. It states what the committee would
do and what already exists. Names, sponsoring council and dates are left for
the proposers.*

## Purpose

Establish an open, reproducible and tool-neutral body of evidence on whether
1D, 2D and coupled 1D/2D hydraulic models get the answers engineers depend on.
Publish the protocol that produces it, so that any tool, from long-standing
public-domain engines to GPU solvers and machine-learned surrogates, can be
held to the same standard of care.

## Why now

- No shared, citable protocol exists for showing that a water model is fit
  for a stated purpose. Vendor and agency validation reports are valuable but
  cannot be reproduced by third parties.
- New classes of tool, including machine-learned surrogates and
  cloud-platform solvers, are being offered for work that has relied on
  established engines. Engineers need a neutral way to ask what evidence a
  tool has.
- There is precedent for benchmark-based acceptance:
    - US tsunami inundation models used in National Tsunami Hazard Mitigation
      Program projects must complete a defined set of analytic, laboratory and
      field benchmark problems.
    - The UK Environment Agency's 2D benchmarking exercise and its
      reproductions (HEC RD-51, FHWA's benchmarking of SRH-2D) showed the
      value of common tests.
    - ASCE's *Verification and Validation of 3D Free-Surface Flow Models*
      (2009) set out the method for 3D models.

## What exists today

An open implementation, Benchmark1d2d (Apache-2.0 code; per-dataset data
licences), already runs:

- **The catalogue.** 44 cases, each stating its kind of evidence
  (verification against exact solutions, validation against measurements,
  comparison with pinned reference engines) and the capabilities it tests.
- **Engines.** Public-domain, open-source, research and commercial engines
  are run headless on fixed, hashed inputs.
- **Configurations.** Every model's set-up is recorded: its tier (out of the
  box, documented guidance, expert) and every setting changed from the
  engine's default. For SWMM and EPANET engines the changes are computed
  automatically from the model files.
- **Evidence profiles.** The results are published as evidence profiles per
  model, with no rankings and no combined scores.
- **Automation.** It runs, scores and publishes itself in CI. Anyone can
  contest a result by submitting a better set-up, which CI reruns.

## Scope of the committee

1. **Protocol.** Review and adopt the evidence protocol: kinds of evidence,
   capability groups, configuration tiers, metrics and the rules for
   validation designs (calibration, scored and held-back events).
2. **Engineering significance.** For each kind of check, agree the size of
   error that matters in practice, from cited codes of practice and agency
   guidance.
3. **Reference acceptance.** Review each case's reference (the exact solution,
   the measurements, or the pinned engine) and freeze a reviewed core set.
4. **Validation data.** Identify and help release observed datasets with open
   licences. The current priority gaps are:
    - rainfall-on-grid
    - hydraulic structures (culverts, bridges)
    - water hammer in real systems
    - a held-back field dataset for blind rounds
5. **Machine-learned surrogates.** Define what evidence a non-discretised
   model must show: blind and out-of-distribution rounds, physical-consistency
   checks, and disclosure of training data.

## Deliverables

- An EWRI report setting out the protocol (versioned like a standard).
- A data-descriptor paper on the frozen core catalogue and its references.
- The living, automatically updated evidence site and data exports, as the
  reference implementation.
- An annual blind round.

## Membership

The committee would have balanced seats from federal agencies, academia,
consulting practice, and developers (open-source and commercial, rotating),
plus a data or uncertainty specialist. Conflict-of-interest declarations would
be published (see [conflict_of_interest_form.md](conflict_of_interest_form.md)).
The committee decides only protocol, reference acceptance and significance
values. It does not approve or hold back results, which the system publishes
automatically ([GOVERNANCE.md](../../GOVERNANCE.md)).

## Duration

Three years, with the protocol report in year two.
