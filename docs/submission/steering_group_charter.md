# Steering group charter (draft)

## Role

The steering group holds the three decisions the
[automation charter](../../GOVERNANCE.md) leaves to people, and nothing else:

1. **Changing the protocol:** kinds of evidence, capability groups, tiers,
   metrics, validation-design rules and engineering-significance values.
2. **Accepting a reference:** a new case's truth (an exact solution,
   measurements or a pinned engine), and freezing a case.
3. **Adapter breaks:** making sure an adapter is fixed when an engine changes
   its file format. The fix itself is a normal pull request.

The group does not approve, delay or withdraw results. Results are produced
and published by CI. A result is contested by submitting a better
configuration, which CI reruns.

## Membership

- Seven to nine members:
    - two from federal or national agencies
    - two from academia
    - two practitioners from consulting firms
    - one or two developers (one open-source, one commercial, rotating each year)
    - one data or uncertainty specialist
- Three-year terms, staggered. A member may serve two terms.
- Every member publishes a conflict-of-interest declaration
  ([form](conflict_of_interest_form.md)) before their first decision, and
  updates it when it changes.

## Decisions

- Every decision is made on a public issue or pull request with at least 14
  days for comment.
- A protocol change needs two-thirds of members. Accepting a reference needs
  a majority, plus one recorded review by someone other than the case's
  author.
- A member with a declared interest in an engine does not vote on a decision
  that affects only that engine's cases or configurations.
- Every decision is recorded in an ADR (`docs/adr/`) or in the case's
  manifest (`review`), and is versioned.

## Meetings

The group meets quarterly, online, with public minutes. Between meetings,
decisions are made asynchronously on the repository.
