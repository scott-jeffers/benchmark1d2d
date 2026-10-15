# OpenSWMM Engine v6 (HydroCouple's SWMM 6)

[OpenSWMM Engine](https://github.com/HydroCouple/openswmm.engine) is a
community continuation of EPA SWMM with a rewritten C++20 engine. Its Python
wheel (`openswmm` on PyPI, MIT licence) carries two engines:
`openswmm.legacy` (EPA SWMM 5.3) and `openswmm.engine` (the new v6 engine).
The suite scores **the new engine**, pre-release `6.0.0a4.dev1`, run as a
black box with its own defaults. It writes the standard SWMM binary output
(version field 60000), so its results are read with the same reader as
SWMM 5.

## How it is run

| Where | Script | What |
|---|---|---|
| Track B cases | `scripts/run_track_b.py --openswmm-python …` | B-EXTRAN-001, B-RTC-001 against SWMM 5.2.4 reference results |
| Corpus | `scripts/corpus_parity.py --candidate-engine openswmm …` | every model of a tier against SWMM 5.2.4, worst node and worst link |
| Track A | `scripts/run_swmm_track_a.py --openswmm-python …` | 1D channel physics cases, dynamic wave and the new finite-volume routing |

The engine lives in its own virtual environment (`pip install
"openswmm==6.0.0a4.dev1" numpy`, Python 3.12 or 3.13) and is called through
`benchmark1d2d.adapters.openswmm`.

## Results

### Track A — 1D channel physics

Each channel is a chain of rectangular open conduits, one per grid cell, with
depth and velocity read at the cell centres (details in the script's header).

| Case | EPA SWMM 5.2.4 | v6 dynamic wave | v6 finite volume (`FLOW_ROUTING FV`) |
|---|---|---|---|
| A1F-010 Ritter (dry bed) | fails: front 152 m short, no convergence | identical to 5.2.4 | fails: front 45 m short, order 0.73; mass 0.003 % |
| A1F-011 Stoker (wet bed) | fails: depth error 3.7 cm, mass +4.1 % | identical to 5.2.4 | **passes**: depth error 1 mm, order 0.91 |
| A1F-001 MacDonald backwater | passes: 0.02 mm, order 1.74 | identical to 5.2.4 | fails convergence: 0.44 mm, order 0.76 (minimum 0.8) |

v6 dynamic wave reproduces SWMM 5.2.4 bit for bit on all three. The new
finite-volume routing is the first SWMM engine to pass a dam break.

### Track B — cases

* **B-EXTRAN-001**: identical to SWMM 5.2.4.
* **B-RTC-001** (pump station run by control rules): differs. Node 1 peaks at
  0.697 m after 35 h against 0.463 m after 12 h in 5.2.4, although the pumps
  switch the same 74 times.

### Track B — corpus (nightly tier)

500 models from the HydroCouple collection (pinned commit `63eb8bc`), each
scored by its worst node (relative peak depth) and worst link (relative
volume of |Q|):

| | OpenSWMM v6 | EPA SWMM 5.1.15 (for scale) |
|---|---|---|
| Identical to 5.2.4 | 207 | 358 |
| Within 1 % | 172 | 76 |
| 1–5 % | 46 | 18 |
| Over 5 % | 71 | 23 |
| Could not run | 1 (an error at initialisation) | 21 |
| Nothing to compare | 3 | 4 |

Median worst difference 0.011 %. 425 of 496 scored models are within 5 %.
v6 runs far more of the collection than SWMM 5.1.15 (1 failure against 21),
but changes more models: 289 differ at all, against 117 for 5.1.15.

* In **20 of the 71** models over 5 % the worst node is an **outfall**: v6
  reports outfall depths where 5.2.4 reports (almost) none. This is the
  largest single pattern and may be a reporting convention rather than a
  routing change.
* **Speed.** Three models are 3.5–57 times slower in v6 than in 5.2.4 and
  exceeded the nightly run's 120 s limit on a shared runner; given 900 s they
  finish and match 5.2.4 (two identical, one within 0.06 %):

  | Model | 5.2.4 | v6 | Simulated |
  |---|---|---|---|
  | `swmm5-ncimm/small-rdii-example` | 2.9 s | 101.5 s | 7 years, 30 s routing step |
  | `hydrology/baisismodell-si-units` | 0.8 s | 28.8 s | 2 years, 30 s routing step |
  | `wq/peter-klaver-wq-tracer` | 6.5 s | 22.7 s | 1 month, 2 s routing step |

  The nightly workflow now allows v6 600 s per model.

## Leads for the engine's developers

1. **`swmm5-ncimm/weir-overtopping` creates water at an outfall.** The v6 report
   gives a flow-routing continuity error of **−48.2 %** (SWMM 5.2.4: 0.011 %).
   A storage node (`depression`, invert 1040.9 m) drains through a culvert and
   over a transverse weir (crest 2 m) to a FREE outfall `Spill` whose invert is
   the crest level (1042.9 m). In 5.2.4 the storage never reaches the crest
   (peak 2.6 cm) and nothing flows. In v6 the outfall `Spill` sits at 2.0 m
   depth and the weir carries a constant 33.6 m³/s *backwards*, from the
   outfall into the storage, at every report step — water is created at the
   outfall — and the storage fills to its full 2 m. v6 also prints
   `WARNING 10: crest elevation is below downstream invert` for the weir,
   which 5.2.4 does not; the weir's
   offset/crest reference may be handled differently.
2. **B-RTC-001 control rules**: same switching count, different peaks (above).
3. **`swmm5-ncimm/3525-nodes` fails at `initialize()` with
   `ParseError: Input file parse error`**, although `open()` succeeds and a
   lenient open lists no errors. The only change that makes it run is removing
   `FLOW_ROUTING KINWAVE` (28 other kinematic-wave models run). This model
   also sets `IGNORE_ROUTING YES` and has pumps under control rules. Two
   leads: whatever v6 rejects here, and an error raised at initialisation that
   is labelled a parse error with no detail.
4. **Speed**: long continuous simulations run 35–57 times slower than in 5.2.4
   (table above).

A difference is not a defect by itself: Track B measures distance from the
reference engine, not which one is right. The weir case is reported because
its continuity error shows water being created or lost.
