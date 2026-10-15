# Hydra (NEER AI)

[Hydra](https://github.com/neeraip/hydra) is a Rust water-infrastructure
engine (AGPL-3.0 or commercial licence) with two engines on the standard data
models: **water distribution** (`wds`, EPANET `.inp`) and **urban drainage**
(`uds`, SWMM `.inp`). Hydra states that correctness is defined by
conservation laws, not by agreement with EPANET or SWMM, and that its
departures are deliberate and documented. The suite therefore scores it on
both questions: physics (Track A, exact answers) and parity (Track B, distance
from the reference engines).

It runs as a black box through its CLI, pinned to **CLI 4.1.1 / library
17.0.0** (`hydra-cli-4.1.1-x86_64-unknown-linux-gnu.tar.gz`, SHA-256
`bffb9859c0a84391f4a28e61b9df96dfc12890c10af24b182246c0f476e3591d`):

    hydra run model.inp --engine wds|uds --results model.out --summary model.rpt --quiet

Its results files are EPANET- and SWMM-format binaries, read with the same
readers as the reference engines (`benchmark1d2d.adapters.hydra`).

## Results

### Water distribution

| Test | Result |
|---|---|
| A1P-001 single pipe (Darcy–Weisbach, exact) | passes: head loss 0.65 % (EPANET 2.2: 0.60 %) |
| A1P-010 two-loop network (Todini, exact) | passes: nodal head 7.4 mm (EPANET 2.2: 0.7 mm) |
| B-EPANET-001 Net1 vs EPANET 2.2 | passes: pressure 0.11 %, pipe volume 0.09 % |

On six independent networks (`scripts/epanet_parity.py`: WNTR's Net1, Net2,
Net3, Net6, ky4, ky10), worst element against EPANET 2.2:

| Network | Hydra, defaults | Hydra, `--tank-tolerance 0` | EPANET 2.0 (scale) |
|---|---|---|---|
| Net1 | 0.11 % | 0.02 % | 0 % |
| Net2 | 0.06 % | 0.06 % | 0 % |
| Net3 | 4.7 % | 0.03 % | 0 % |
| Net6 | 26.8 % | 3.4 % | 0.03 % |
| ky4 | 0.35 % | 0.35 % | 0 % |
| ky10 | 0.55 % | 0.55 % | 11.2 % |

The largest differences are in pipe volumes on tank-fed networks and come
from Hydra's default second-order tank integration; with EPANET's first-order
stepping (`--tank-tolerance 0`) five of six networks agree within 1 %.
Pressures agree within 0.7 % in every case. Peak-timing differences are not
reported: on links whose flow is nearly constant, the time of the peak is not
well defined (EPANET 2.0 shows the same four-day "difference" on Net6).

### Urban drainage

| Test | Hydra | EPA SWMM 5.2.4 |
|---|---|---|
| A1F-001 backwater (exact) | passes (0.2 mm, order 0.90) | passes |
| A1F-011 Stoker dam break | fails: 2.1 cm, order −0.34; mass −0.015 % | fails: 3.7 cm; mass +4.1 % |
| A1F-010 Ritter dam break | fails: front 102 m behind | fails: front 41 m behind |
| B-EXTRAN-001 vs SWMM 5.2.4 | depth 1.3 %, volume 4.5 % | (reference) |
| B-RTC-001 vs SWMM 5.2.4 | node 1 peak 0.048 m vs 0.463 m; pumps switch 338 vs 335 times | (reference) |

On B-RTC-001 Hydra's own routing continuity error is 0.16 % (SWMM 5.2.4:
−1.1 %), and it reports the changes it makes to the input: adverse-slope
channels reversed, negative offsets zeroed, a maximum depth raised,
`INERTIAL_DAMPING NONE` substituted and `LENGTHENING_STEP` ignored. Node 1 is a
storage node whose parameters are all zero. The difference is a declared
modelling divergence, not an obvious defect on either side.

### Urban drainage: exact network answers

On the five drainage networks with exact answers (A1D-001 to 005, worst depth
error, limit in brackets) Hydra passes everything and is the most accurate
engine on the steady pipe cases, because it computes the circular section
exactly where the SWMM engines interpolate a 51-entry table:

| Case | EPA SWMM 5.2.4 | v6 dynamic wave | v6 finite volume | Hydra 17 |
|---|---|---|---|---|
| A1D-001 normal depth, part-full pipes (1 cm) | 0.27 mm | 0.27 mm | **fails**: 1.4 cm | 0.0005 mm |
| A1D-002 surcharged grade line (1 cm) | 0.40 mm | 0.40 mm | **fails**: 28 cm | 0.0001 mm |
| A1D-003 storage drain-down (5 mm) | 1.4 mm | 1.4 mm | 1.3 mm | 1.1 mm |
| A1D-004 pump on its curve (1 cm) | 0.0001 mm | 0.0001 mm | 0.0001 mm | 0.0001 mm |
| A1D-005 backwater through manholes (2 cm) | 0.30 mm | 0.30 mm | 3.7 mm | 0.29 mm |

### Urban drainage across the HydroCouple collection

Nightly tier, 500 models, worst node (relative peak depth) and worst link
(relative volume of |Q|) against SWMM 5.2.4
(`test_catalog/track_b/parity/nightly_hydra.*`):

| | Hydra 17 | OpenSWMM v6 | SWMM 5.1.15 |
|---|---|---|---|
| Identical | 33 | 207 | 358 |
| Within 1 % | 32 | 172 | 76 |
| 1–5 % | 60 | 46 | 18 |
| Over 5 % | 351 | 71 | 23 |
| Refused or timed out (600 s) | 21 | 1 | 21 |

* **Hydrology agrees, routing differs.** 16 of 17 LID models are within
  5 %; the classic EXTRAN examples differ by a median 7.5 %, and 115 models
  that OpenSWMM v6 reproduces exactly differ by more than 5 %. That is
  consistent with Hydra's own Preissmann-slot dynamic wave being a different
  scheme from SWMM's, as Hydra says it is.
* **Not a units artifact**: on the 362 US-unit models the signed median
  differences are −0.8 % (depth) and +0.7 % (volume); SI models differ more
  (median volume +18 %).
* **Refusals are explicit**: incomplete subcatchment data (5), ground below
  the initial water table (3), rule and geometry validation, missing
  rainfall or interface files. Three models exceeded 600 s.

Which engine is right is a Track A question; on the channel cases above
Hydra conserves water better than SWMM 5.2.4 but places the dry-bed front
further behind.
