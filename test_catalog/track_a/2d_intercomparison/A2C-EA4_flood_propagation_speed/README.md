# A2C-EA4_flood_propagation_speed — EA Test 4 — speed of flood propagation over an extended floodplain

Flat, horizontal 1000 m × 2000 m floodplain at 0 m; a breach hydrograph peaking at 20 m³/s enters along a 20 m line mid-way along the west edge. Tests front celerity and transient depths and velocities at the leading edge.

| Parameter | Value |
|---|---|
| Manning's n | 0.05 |
| Grid | 5 m |
| Run time | 5 h |
| Inflow volume to t_end | 285,000 m³ |

Probe levels and velocities are compared with the published package spread for context only.

## Data and licence

Inputs come from the GOV.UK 'Benchmarking model data' archive, published under the Open Government Licence v3.0 (the page licence; the archive carries no other terms). Attribution: Environment Agency, SC120002 (2013), test specifications May 2010.

- Archive: <https://assets.publishing.service.gov.uk/media/6033a9bbd3bf7f72182e99ca/Benchmarking_Model_Data.zip> (SHA-256 `388c2789570e5975fe909033e34bedbe5d7bde5e6d7f9b7d7c1eaf04e58bc732`)
- Landing page: <https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm>
- Report: <https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf>

Fetch the non-committed inputs with `python scripts/fetch_inputs.py A2C-EA4`.
