# A2C-EA1_disconnected_water_body — EA Test 1 — flooding a disconnected water body

700 m × 100 m sloping strip with a depression behind a 10.25 m sill. A water-level boundary rises from 9.7 m to 10.35 m, holds, then falls back; the pond must fill, become horizontal, and settle at the sill crest. Tests wetting/drying and disconnected water bodies.

| Parameter | Value |
|---|---|
| Manning's n | 0.03 |
| Grid | 10 m (DEM 2 m) |
| Run time | 20 h |
| Initial level | 9.7 m |
| Settled pond volume | 9,887 m³ |

## Data and licence

Inputs come from the GOV.UK 'Benchmarking model data' archive, published under the Open Government Licence v3.0 (the page licence; the archive carries no other terms). Attribution: Environment Agency, SC120002 (2013), test specifications May 2010.

- Archive: <https://assets.publishing.service.gov.uk/media/6033a9bbd3bf7f72182e99ca/Benchmarking_Model_Data.zip> (SHA-256 `388c2789570e5975fe909033e34bedbe5d7bde5e6d7f9b7d7c1eaf04e58bc732`)
- Landing page: <https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm>
- Report: <https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf>

Fetch the non-committed inputs with `python scripts/fetch_inputs.py A2C-EA1`.
