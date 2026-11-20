# ADR-0004: Evidence, not rankings; three kinds of evidence; configuration tiers

- Status: Accepted
- Date: 2026-11-20
- Supersedes: the ranking and rating parts of scoring method 3.0 (§3–4); refines ADR-0001

## Context

The suite was presented as a leaderboard: an Elo-style rating, a rank on every
test and head-to-head win counts. Three problems followed:

1. A rank adds up things that cannot be compared. A 0.3 % win on a dam-break
   front and a win on a manhole-exchange test counted the same. A 0.01 % vs
   0.012 % win counted as much as 1 % vs 40 %.
2. A rank turns every set-up choice into a dispute. The published results came
   from the suite's own set-ups, so a low rank for an agency or commercial
   code read as a claim against the product when it could equally reflect a
   setting an experienced user would change.
3. Track A mixed exact solutions, measurements and code inter-comparison,
   which say different things when a model misses.

The project's audiences are engineers deciding whether to trust a tool,
developers who need a target, and ASCE/EWRI defending a standard of care.
None of them needs a standing. All of them need evidence that says what it
can and cannot show.

## Decision

- Remove the rating, per-test ranks and win counts from the site, its data
  exports and its badges. Keep every measurement.
- Every case states its kind of evidence (verification, validation,
  comparison) and its capability groups (manifest schema 1.2.0). The site
  shows evidence profiles: capability × kind of evidence, per model.
- Every model has a configuration record (tier T0/T1/T2 plus the settings
  changed from default, `schemas/v1/configuration.schema.json`). Results are
  always shown with their tier and are listed by tier, never by result.
- The suite publishes results automatically, with no notice period. Anyone can
  contest a result by submitting a better configuration, which CI reruns.

Tracks A and B (ADR-0001) remain as storage and workflow labels in the
catalogue. Readers see the three kinds of evidence.

## Consequences

- `site/ranking.py`, `site/rankpage.py` and `site/static/rankings.js` are deleted. `rankings.html` redirects to `profiles.html`.
- Score cards are unchanged; no card is re-scored.
- The `passed`, `verdict` and `certification_claims` fields in older cards are not shown. They will be removed from the card schema in a later version.
- Most configuration records are `defaults_audit: pending`. Diffing each engine's written model against its defaults automatically is the next piece of work.
