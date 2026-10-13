# A2L-EA6A_dambreak_isolated_building — EA Test 6A — dam break past an isolated building (laboratory scale)

UCL laboratory dam break through a 1 m gate against a single idealised building (Soares-Frazão & Zech 2002, IMPACT), as adopted by the Environment Agency. Tests hydraulic jumps and the wake behind an obstacle against gauge measurements.

| Parameter | Value |
|---|---|
| Manning's n | 0.01 |
| Grid | 0.1 m (DEM 0.05 m) |
| Run time | 2 min |
| Initial depths | 0.4 m upstream, 0.02 m downstream |

**Status: draft** — the DEM and gauge locations are real; gauge measurements still have to be obtained.

## Data and licence

Inputs come from the GOV.UK 'Benchmarking model data' archive, published under the Open Government Licence v3.0 (the page licence; the archive carries no other terms). Attribution: Environment Agency, SC120002 (2013), test specifications May 2010.

- Archive: <https://assets.publishing.service.gov.uk/media/6033a9bbd3bf7f72182e99ca/Benchmarking_Model_Data.zip> (SHA-256 `388c2789570e5975fe909033e34bedbe5d7bde5e6d7f9b7d7c1eaf04e58bc732`)
- Landing page: <https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm>
- Report: <https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf>

Fetch the non-committed inputs with `python scripts/fetch_inputs.py A2L-EA6A`.
