# B-RTC-001 — pump-station control rules

Two pump stations (wet wells `PP_U433`, `PP_U435`) are run by level rules, for example:

```
RULE U433_R2
IF NODE PP_U433 DEPTH >= 1.778
AND NODE PP_U433 DEPTH < 2.032
AND PUMP U433_Psan_1_et_2 STATUS = OFF
AND PUMP U433_Psan_1_et_2_et_3 STATUS = OFF
THEN PUMP U433_Psan_1_ou_2 STATUS = ON
```

On SWMM 5.2.4 pump `U433_Psan_1_ou_2` switches 74 times in the 36 h run, so a candidate that evaluates rules late,
early or with different hysteresis shows up in pumped volumes and peak timing.

Source: HydroCouple `openswmm.engine.benchmarks`, `epa/221-h-h-si-units-elements`, commit `63eb8bc5b4e741c82195ed65c4d7d146b86da1cc` (fetched by hash with
`python scripts/fetch_inputs.py B-RTC-001`). Reference: EPA SWMM 5.2.4.
