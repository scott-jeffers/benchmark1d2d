# A2C-EA2_floodplain_depressions — EA Test 2 — filling of floodplain depressions

2 km × 2 km floodplain with a 4 × 4 grid of ~0.5 m deep depressions; a 20 m³/s, ~85 min hydrograph enters along 100 m of the north-west edge and the run continues to 48 h. Tests low-momentum filling and final inundation extent.

| Parameter | Value |
|---|---|
| Manning's n | 0.03 |
| Grid | 20 m |
| Run time | 48 h |
| Inflow volume to t_end | 97,200 m³ |

Probe levels and velocities are compared with the published package spread for context only.

## Data and licence

Inputs come from the GOV.UK 'Benchmarking model data' archive, published under the Open Government Licence v3.0 (the page licence; the archive carries no other terms). Attribution: Environment Agency, SC120002 (2013), test specifications May 2010.

- Archive: <https://assets.publishing.service.gov.uk/media/6033a9bbd3bf7f72182e99ca/Benchmarking_Model_Data.zip> (SHA-256 `388c2789570e5975fe909033e34bedbe5d7bde5e6d7f9b7d7c1eaf04e58bc732`)
- Landing page: <https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm>
- Report: <https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf>

Fetch the non-committed inputs with `python scripts/fetch_inputs.py A2C-EA2`.
