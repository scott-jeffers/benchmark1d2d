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

As a worked example with no coupling code of its own, `scripts/run_coupled_cases.py` couples EPA SWMM 5.2.4 (its stepping API)
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

## OpenSWMM Engine v6 (its own coupling)

OpenSWMM v6 couples its network to a 2D surface itself
(`scripts/run_openswmm_coupled.py`, model written by
`scripts/openswmm_coupled_model.py`): an explicit local-inertial
finite-volume mesh, each manhole tied to a mesh vertex
(`[2D_VERTEX_NODE_MAP]`) with an orifice law whose gate shuts at the
manhole's rim. The suite writes the model and runs the engine with its
defaults (pre-release `6.0.0a4.dev1`):

* the network as in the SWMM + ANUGA runs, each manhole's rim at the grate
  crest; dynamic wave;
* the surface as the case's grid of 1 m squares, ground levels at the
  vertices; the case's orifice coefficient (0.6) and grate area at each
  manhole;
* the street's open foot as a `NORMAL_FLOW` boundary at the street's slope,
  the same condition the case defines.

The squares are triangulated two ways, each scored as its own variant: cut
along one diagonal (`openswmm-2d`, two triangles) and along both
(`openswmm-2d-x`, four, the mesh the ANUGA surface uses).

| Test | Two triangles per square | Four triangles per square |
|---|---|---|
| A12-010 | **passes**: exchange 0.503 m³/s, street 0.6 mm from exact, balance 0.001 % | fails the street depth only: 85.7 mm against 77.7 mm |
| A12-011 | fails: yard 12 mm below the crest, 4.1 % too much out, balance −0.55 % | fails: 14 mm below, 5.1 % too much out (balance −0.31 % passes) |
| A12-012 | **passes**: 179.6 m³ out, 0.4 m³ left, balance 0.016 % | **passes**: the same within 0.1 m³ |

**Findings.**

* *Below-crest drainage.* On A12-011 the yard drains below the 5 cm crest
  on both meshes. The engine's exchange is documented to shut at the rim
  (a smooth gate over 5 cm above it), and a still pond started 1 cm below the
  crest does not drain at all. But during the run the exchange kept draining
  at 0.035–0.045 m³/s for about ten minutes after both the surface
  (38–45 mm) and the manhole head (−1.87 m) were below the crest, until the
  yard settled at 36–38 mm.
* *Mesh dependence.* The steady street on A12-010 is 77.1–77.4 mm deep on the
  two-triangle mesh (77.7 mm exact) and 85.7 mm on the four-triangle mesh, the
  same model and the same grid.
* *Network continuity.* The surface balances to round-off (10⁻¹⁴) in every
  run; the network's own continuity error is 0.35–0.62 % on A12-011, which is
  what the balance misses. The report's continuity line also differs from the
  stored volumes: on A12-010 it shows 0.37 % while surface plus network plus
  outflow match the inflow to 0.01 m³.

Commercial coupled codes (TUFLOW, InfoWorks ICM, MIKE+, HEC-RAS 6.6 pipe
networks, PCSWMM 2D) can run the same inputs; see
[submitting results](submitting.md).
