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

## Known finding: build sensitivity

The cross-build job (`scripts/run_swmm_self_parity.py`) runs the official EPA
SWMM 5.2.4 win64 binaries on this input and scores them against the reference
(produced by the same 5.2.4 source compiled in `swmm-toolkit` 0.17.0). Both
builds repeat bit-for-bit, but they disagree with each other beyond this case's
tolerances: −3.7 % peak depth at `Out_U435`, and the `Ref_U435` flow peak moves
by 92,400 s because two near-equal pump-cycle peaks swap order. Depth-triggered
pump rules amplify last-bit floating-point differences between compilers.

Consequences: the cross-build check for this case is informative, not gating;
and a candidate that fails B-RTC-001 by a similar margin is not necessarily
wrong. Whether to widen these tolerances, switch the timing metric to one that
is robust to near-equal peaks, or score against both builds is an open decision
for the maintainers.

