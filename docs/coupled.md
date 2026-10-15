# Coupled 1D/2D tests (A12-010 to A12-012)

Three sewer–surface cases whose answers follow exactly from conservation and
hydrostatics, so a coupled model can be judged without a laboratory:

| Test | What is exact |
|---|---|
| A12-010 manhole surcharge onto a street | the steady exchange equals the pipe inflow (0.5 m³/s); the street below runs at normal depth (77.7 mm) |
| A12-011 flood draining into a pipe | the yard settles at the gully crest (0.05 m); 225 m³ leaves by the outfall |
| A12-012 surcharge and return | all 180 m³ of the storm leaves by the outfall; nothing stays on the surface |

Each also scores the model's **water balance** at the end of the run: stored
water (surface + network) has changed by exactly inflow minus outflow
(0.5 % allowed). Results report, besides the surface at the probes, the
exchange flow at each manhole (`element_type` `exchange`, positive onto the
surface) and the volume accounts (`element_type` `account`: `surface`,
`network`, `inflow`, `outflow`, column `V` in m³); see
`schemas/v1/results.schema.json`.

## SWMM 5.2.4 + ANUGA 4.0.1 (the suite's coupler)

No open-source code couples a sewer network to a 2D surface out of the box,
so `scripts/run_coupled_cases.py` couples EPA SWMM 5.2.4 (its stepping API)
to ANUGA 4.0.1 the way most couplings do: an explicit exchange every second,
weir or orifice flow at the manhole depending on the surface level and the
manhole head (Chen et al. 2007), limited so one step cannot overshoot. It is a
worked example of a coupled model, not a product, and it shows that the tests
can be passed.

| Test | Result |
|---|---|
| A12-010 | fails the water balance only: exchange exact, street depth 0.1 mm from exact, but 5 m³ of 885 m³ lost (0.56 %), all of it SWMM's own continuity error (0.50 % in its report) while the dead-end pipe filled |
| A12-011 | passes: level 2.9 mm above the crest, 222.2 m³ out (−1.2 %), balance 0.005 % |
| A12-012 | passes: 180.05 m³ out, surface empty, balance 0.03 % |

**Finding for SWMM users.** While pipes run full, the node and link volumes
SWMM reports (`VOLUME` results) exceed its own balance by up to 1.8 m³ on a
7 m³ pipe; the difference disappears as the pipe empties and SWMM's
end-of-run continuity error is 0.000 %. This is why the water balance is
scored at the end of the run; the largest imbalance during the run is shown
in each score card's detail.

Two coupling choices were needed for a stable explicit exchange: SWMM's
Preissmann slot (with the default EXTRAN surcharge a laterally fed manhole's
head jumped 20 m in one step) and the levelling limit on each step's
exchange. With SWMM's flooding as the network-to-surface path (ponding off)
the exchange chattered between flooding and inflow and SWMM's continuity
error reached −2.9 % (EXTRAN) and −8.5 % (slot).

Commercial coupled codes (TUFLOW, InfoWorks ICM, MIKE+, HEC-RAS 6.6 pipe
networks, PCSWMM 2D) can run the same inputs; see
[submitting results](submitting.md).
