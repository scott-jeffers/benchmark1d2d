# Engineering-significance values

A check's `significance` (manifest schema 1.2.0, `scoring.criteria[].significance`)
is the size of error that matters in engineering practice. It must come from a
cited external source, never from the suite's own results:

- a code of practice
- a design standard
- an agency's model-review guidance
- a published acceptance criterion

The site reports each result as meeting or missing it. The value is not a pass
mark, and it does not change the measured numbers.

## Values in use

| Test | Check | Value | Source |
| --- | --- | --- | --- |
| A1F-100 | Peak level | ±0.1 m | WaPUG (2002) *Code of Practice for the Hydraulic Modelling of Sewer Systems*; CIWEM UDG (2017) *Code of Practice for the Hydraulic Modelling of Urban Drainage Systems* |
| A1F-100 | Level NSE | ≥ 0.5 | Moriasi et al. (2007), *Trans. ASABE* 50(3): the lower bound of "satisfactory" |

## Wanted

Most checks have no value yet. Candidate kinds of source for each capability:

| Capability | Kind of source to look for |
| --- | --- |
| Wetting and drying, inundation | Flood-mapping guidance on water-surface or extent tolerances, for example agency floodplain-mapping and model-review standards |
| Steady open-channel profiles | Guidance on calibration to high-water marks and on water-surface tolerances for floodplain studies |
| Shocks, jumps, flood waves | Dam-safety and inundation-mapping guidance on arrival time and peak level |
| Pipe hydraulics, drainage networks, storage and pumps | Sewer-model verification codes of practice (as for A1F-100) |
| Pressurised networks, water hammer | Water-distribution model calibration guidance, and surge-analysis design margins |
| Sewer–surface exchange | Urban flood modelling codes of practice |

Proposing a value means opening a pull request that adds `significance` to the
check, with the source document, clause and basis. Accepting it is a
protocol decision ([GOVERNANCE.md](../../GOVERNANCE.md)). The value has to
apply to the quantity the check measures (a level, a peak, a timing), not to
the percent difference.
