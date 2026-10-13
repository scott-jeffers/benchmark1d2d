# ADR-0001: Dual independent tracks (A physics, B parity)

- Status: Accepted
- Date: 2026-10-13

## Context

Reviewers need to know whether a solver is *correct* and whether it is
*compatible with the industry reference*. These are different questions.
A new Godunov solver may pass Track A and fail Track B; a SWMM fork may
do the opposite.

## Decision

Score Track A and Track B separately on every score card. Never collapse them
into a single pass/fail badge. Certification levels (A-V, A-L/A-F, B-x%) may
be held in any combination.

## Consequences

- Manifests declare exactly one `track`.
- Site and README tables always split by track.
- Track B tolerances are relative to a pinned engine build, not "SWMM" in general.
