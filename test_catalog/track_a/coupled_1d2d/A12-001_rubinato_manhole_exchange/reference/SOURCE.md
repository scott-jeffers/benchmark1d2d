# Source of the reference data

`steady_exchange.csv` is Table 2, and `rig_geometry.yaml` is the rig description (section 3.1, Figs 1–2), of:

> Rubinato, M., Martins, R., Kesserwani, G., Leandro, J., Djordjevic, S. and Shucksmith, J. (2017).
> Experimental calibration and validation of sewer/surface flow exchange equations in steady and unsteady flow conditions.
> *Journal of Hydrology* 552, 421–432. doi:10.1016/j.jhydrol.2017.06.024. Open access under CC BY 4.0.

The transcription comes from the HydroCouple OpenSWMM benchmarks corpus
(`corpus/rubinato-2017`, commit `3f490b5`, released into the public domain). It was
spot-checked against the published table for rows in all four scenarios. Columns:

- scenario
- exchange discharge `q_e_lps` (l/s)
- surcharge (%)
- exchange-flow variation `xi_f_lps` (l/s, eq. 6)
- surface depth `h_s_m` (m)
- pipe head `h_p_m` (m)
- surface Froude number
- `h_s/D_M`
- pipe and manhole Reynolds numbers

A blank cell is printed as "–" in the paper.
