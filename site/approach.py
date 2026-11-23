"""How each model was built for each test, in plain words (the test page's "How it was modelled").

Written from the runners' own documentation (``scripts/run_*.py``); each text says how the
test's geometry, start and boundaries were put into that software, and what the software
did with them. ``approach(key, sid)`` returns a short paragraph, or "" when nothing is known.
"""

from __future__ import annotations

DAM = {"A1F-010", "A1F-011"}
BUMPS = {"A1F-040", "A1F-041", "A1F-042", "A1F-043"}
CHANNEL = DAM | BUMPS | {"A1F-001", "A1F-020"}
EA = {"A2C-EA1", "A2C-EA2", "A2C-EA4", "A2C-EA5"}

SWMM_ENGINE = {
    "swmm524": "EPA SWMM 5.2.4's dynamic-wave routing",
    "swmm515": "EPA SWMM 5.1.15's dynamic-wave routing",
    "swmm524-converged": "EPA SWMM 5.2.4's dynamic-wave routing, with its iteration tightened (head tolerance 0.01 mm, 20 trials) so every step converges",
    "swmm524-defaults": "EPA SWMM 5.2.4's dynamic-wave routing with SWMM's own iteration defaults (head tolerance 1.5 mm, 8 trials)",
    "openswmm-dw": "OpenSWMM Engine v6's dynamic-wave routing",
    "openswmm-dw-converged": "OpenSWMM Engine v6's dynamic-wave routing, with its iteration tightened (head tolerance 0.01 mm, 20 trials)",
    "openswmm-fv": "OpenSWMM Engine v6's new explicit finite-volume routing",
    "openswmm6": "OpenSWMM Engine v6",
    "hydra-uds": "Hydra's urban-drainage engine (dynamic wave with a Preissmann slot), run through its command line",
}


def _swmm(key: str, sid: str) -> str:
    eng = SWMM_ENGINE.get(key, "the engine")
    if sid in CHANNEL:
        bits = ["SWMM models networks of pipes and nodes, so the channel is built as a chain of rectangular open conduits, "
                "one per grid cell, with nodes on the cell faces; depth and velocity are read at the middle of each conduit."]
        if sid in DAM:
            bits.append("The bed is frictionless (n = 0.0001, the smallest SWMM accepts). The dam sits on a node, with a very short "
                        "conduit across it, so every cell starts at a single depth.")
        elif sid == "A1F-001":
            bits.append("The bed follows the exact profile, Manning's n = 0.03, and the channel is made 100 km wide so the hydraulic "
                        "radius equals the depth, as the exact answer assumes. A constant inflow enters upstream and the water level is "
                        "held downstream.")
        elif sid == "A1F-020":
            bits.append("The supercritical flow enters as an inflow upstream and the sequent depth is held at the outfall; the run "
                        "starts from the two states either side of the jump. SWMM cannot fix the upstream depth as well as the flow.")
        else:
            bits.append("Bed levels at the nodes trace the bump; the bed is frictionless (n = 0.0001). The unit discharge enters "
                        "upstream and the level is held downstream. The routing step is a twentieth of the cell size, and the minimum "
                        "node surface area is lowered to 0.001 m² (the default is larger than a node on the finest grid).")
        return " ".join(bits) + f" Routing: {eng}."
    if sid == "A1F-100":
        return (f"The published Bellinge EPA SWMM model (Pedersen et al. 2021) is run unchanged, once per storm, with its own rain-gauge "
                f"file; only the run dates are set. Water levels at the level-meter manholes are compared with the measurements. Engine: {eng}.")
    if sid.startswith("A1D"):
        return (f"The test's network is written as one SWMM input file, the same for every engine: pipes, manholes, storage and pumps as "
                f"specified, a 1 s routing step with SWMM's variable step, manhole rims raised 10 m so nothing floods, and no junction "
                f"losses. Depths and flows at the end are compared with the exact answer. Engine: {eng}"
                + (", with its default number of cells per pipe." if key == "openswmm-fv" else "."))
    if sid.startswith("B-"):
        return (f"The test's own SWMM input file is run as it is, with the engine's defaults, and every node and link is compared with "
                f"EPA SWMM 5.2.4 on the same file. Engine: {eng}.")
    return f"Engine: {eng}."


def _hecras(key: str, sid: str) -> str:
    ver = "HEC-RAS 6.6" if key.startswith("hecras66") else "HEC-RAS 7.0.1"
    eq = ("the full-momentum Eulerian equations (SWE-EM), which HEC recommends for dam breaks" if key.endswith("-em")
          else "HEC-RAS's default shallow-water equations (SWE-ELM)")
    if sid == "A1F-001":
        return (f"A 1D steady-flow model in {ver}: cross-sections at every grid point following the exact bed, solved by the standard-step "
                "method. The reach is 100 km wide so the hydraulic radius equals the depth; friction only (expansion and contraction "
                "coefficients 0), and the solution tolerance is tightened to 0.01 mm.")
    head = (f"A 2D model built and run without the user interface: the bed becomes a HEC-RAS terrain, and the mesh is made from seed points "
            f"on the test's grid, so every cell is a square of the test's size.")
    if sid in DAM:
        return (head + " HEC-RAS starts a 2D area from one flat level, so a short still-water run writes a restart file, the cells past the "
                f"dam are set to the downstream depth in it, and the dam break runs from there. Friction is as close to zero as HEC-RAS "
                f"allows (n = 0.0001) and the time step follows HEC-RAS's Courant control. Equations: {eq}.")
    if sid == "A2A-010":
        return (head + " Flow enters on a boundary line upstream and the level is held on one downstream. The run starts from a uniform depth "
                f"over the sloping bed (set through a restart file), with Manning friction. Equations: {eq}.")
    if sid in EA:
        return (head + " The Environment Agency's own terrain raster is used as HEC-RAS's sub-grid terrain, the boundary hydrographs go on "
                f"boundary lines, and the depth reported is each cell's water volume over its area. Equations: {eq}.")
    return head + f" Equations: {eq}."


STRIP = "The 1D channel is run as a narrow 2D strip"


def _two_d(key: str, sid: str) -> str:
    """The 2D shallow-water codes, each with its own defaults."""
    if key == "anuga":
        base = ("ANUGA 4.0.1 with its own defaults (flow algorithm and wet/dry thresholds), on a triangular 'rectangular cross' mesh at each "
                "of the test's grid sizes; the result is sampled at the test's cell centres.")
        if sid in CHANNEL:
            return base + f" {STRIP}." + (" Inflow is added with an inlet operator and the level held downstream." if sid in BUMPS | {"A1F-001", "A1F-020"} else "")
        if sid == "A2A-010":
            return base + " Inflow enters through an inlet operator and the level is held downstream."
        if sid == "A2A-020":
            return base + " The upstream supercritical state is set on the west and north edges."
        if sid in EA:
            return base + " The Environment Agency's terrain and boundary series are used as given, at the specified resolution."
        return base
    if key == "telemac":
        base = ("openTELEMAC-2D 9.1 with its default finite-volume set-up (kinetic scheme, first order) and a variable time step at "
                "Courant 0.45, on an unstructured triangle mesh whose nodes are the test's grid points.")
        if sid in DAM:
            return base + " The channel is a 2D strip two triangle pairs wide with slip walls; the dam-break step is given as a starting file."
        if sid in CHANNEL:
            extra = " The HLLC scheme is used because the default one goes unstable with this inflow." if sid == "A1F-020" else ""
            return base + f" {STRIP} three nodes wide, with the inflow and downstream level set node by node.{extra}"
        if sid == "A2A-020":
            return base + " The upstream supercritical state is set node by node on the west and north edges; HLLC is used because the default scheme goes unstable with this inflow."
        if sid in EA:
            return base + " Each Environment Agency test is run once at the specified resolution with its terrain and boundary series."
        return base + " Walls all round, or the test's inflow and level where it has them."
    if key == "geoclaw":
        return ("GeoClaw (Clawpack 5.9) with the settings of its own stock example (second order, MC limiter, transverse waves, 1 mm dry "
                "tolerance), on a single uniform grid at each size (no adaptive refinement), walls all round, no friction. The starting "
                "water surface is given as a GeoClaw surface file." + (f" {STRIP}." if sid in CHANNEL else ""))
    if key.startswith("lisflood-"):
        solver = {"fv1": "FV1, its first-order finite-volume solver of the full shallow-water equations",
                  "dg2": "DG2, its second-order discontinuous-Galerkin solver of the full shallow-water equations",
                  "acc": "ACC, its local-inertia solver, which leaves out the advection term"}[key.split("-")[1]]
        base = (f"LISFLOOD-FP 8.3, solver {solver}, with its own defaults, on rasters of the test's grid sizes. The CFL condition alone sets "
                f"the time step, and output precision is raised from 1 mm to 8 decimals.")
        if sid in CHANNEL:
            return base + f" {STRIP} two cells wide" + (", with the inflow and downstream level as fixed-flow and fixed-level boundaries." if sid != "A1F-010" and sid != "A1F-011" else ".")
        if sid == "A2A-010":
            return base + " Inflow is a fixed-flow boundary on the west edge and the level is held on the east."
        if sid in EA:
            return base + " Each Environment Agency test runs once at the specified resolution."
        return base
    if key == "basilisk":
        return ("Basilisk's Saint-Venant solver (second order, well balanced) with its defaults, as a small generated C program on a uniform "
                "grid at each size: a true 1D grid for the channel tests, a 2D one otherwise. Inflow holds the velocity at q/h on the "
                "boundary, a held depth sets the level, and walls are free-slip. Basilisk has no friction built in, so Manning friction is "
                "applied after each step as in its own examples.")
    if key == "landlab":
        return ("Landlab's OverlandFlow component (the local-inertia scheme of de Almeida et al. 2012) with its defaults, one node per cell "
                "centre and closed boundary nodes as walls. Landlab has no inflow boundary, so the inflow is added to the first column of "
                "cells after every step; a held depth is reset after every step. Like LISFLOOD-FP ACC, it leaves out the advection term."
                + (f" {STRIP} one cell wide." if sid in CHANNEL else ""))
    if key == "hydronet-fvm":
        return ("HydroNet's differentiable Roe finite-volume solver (Heun time stepping, CFL 0.3, its default) on HydroNet's own mesh "
                "structure: the channel as a strip of square cells one cell wide, with reflective walls and a 0.1 mm wet/dry threshold.")
    if key == "hydronet-pinn":
        return ("HydroNet's FVM-PINN neural network, trained on each grid with the recipe of HydroNet's own 1D dam-break example "
                "(a 64×5 Fourier-feature network, 5,000 Adam epochs, starting-state and finite-volume residual losses, no reference data), "
                "then evaluated at the cell centres at the end time.")
    if key == "demo1d":
        ex = "The suite's own worked example, written to show how a model is scored: "
        if sid.startswith("A1P"):
            return ex + "a method-of-characteristics water-hammer solver on a fixed grid at Courant 0.5, reservoir upstream, valve shut at t = 0."
        if sid == "A1F-001":
            return ex + "the steady gradually-varied-flow equation integrated upstream from the downstream depth (Heun's method), on the test's grid."
        return ex + "a finite-volume shallow-water solver with HLL fluxes (exact fluxes at wet/dry faces) on a true 1D grid."
    if key == "demo2d":
        return "The suite's own worked example: a first-order 2D finite-volume solver on the test's grid, written to show how a model is scored."
    return ""


def _pipes(key: str, sid: str) -> str:
    if key == "epanet22":
        if sid == "A1P-030":
            return "The test is written as an EPANET input file and run with EPANET 2.2 (the library in WNTR), using its water-quality routing for the tracer."
        return "The test's network is written as an EPANET input file and run with EPANET 2.2 (the library in WNTR), as a utility would run it."
    if key == "wntr":
        return "The test's network is written as an EPANET input file and solved by WNTR's own Python hydraulic solver (WNTRSimulator), not by the EPANET library."
    if key == "hydra-wds":
        return "The network is run with Hydra's water-distribution engine through its command line, with its defaults." + (
            " The test's EPANET file is used as it is and compared with EPANET 2.2." if sid.startswith("B-") else "")
    if key == "epanet20":
        return "The test's EPANET file is run as it is with EPANET 2.0 (the 2.00.12 library in WNTR) and compared with EPANET 2.2."
    if key == "tsnet":
        return ("The pipe is written as an EPANET network for TSNet's method-of-characteristics solver: a reservoir, the 1 km pipe split into "
                "reaches of the grid's length, and a valve that closes in one time step. Friction is made negligible (Hazen-Williams C = 10,000), "
                "the wave speed is 1,000 m/s and the valve opening gives exactly 1 m/s to start.")
    return ""


def _coupled(key: str, sid: str) -> str:
    if key in ("openswmm-2d", "openswmm-2d-x"):
        mesh = "four triangles per square (cut along both diagonals)" if key.endswith("-x") else "two triangles per square (cut along one diagonal)"
        return (f"OpenSWMM Engine v6 does the coupling itself. The sewer is the test's SWMM network (dynamic wave, defaults), each manhole's "
                f"rim at the grate's crest. The surface is the test's grid of squares, {mesh}, with ground levels at the vertices. Each manhole "
                f"is tied to the mesh vertex at its position with the test's orifice coefficient and grate area, and the street's open end is "
                f"a normal-flow boundary.")
    if key == "hecras-pipes":
        return ("HEC-RAS 7's own storm-drain network with its 2D surface. The surface is built as in the 2D tests; the pipes, nodes and "
                "inlets are written into the geometry the way RAS Mapper does. Each manhole is a node with a top inlet at the rim, using the "
                "test's orifice area and coefficient and its perimeter as the weir length; flow can go both ways. The pipe inflow is a flow "
                "hydrograph on the upstream node, and a free outfall is a stage one metre below its invert.")
    if key == "swmm-anuga":
        return ("EPA SWMM 5.2.4 for the sewer and ANUGA 4.0.1 for the surface, joined by the suite's own explicit coupler: both advance 1 s "
                "at a time, and each manhole exchanges water by weir and orifice laws on the surface level and the manhole head "
                "(Chen et al. 2007; Rubinato et al. 2017), limited so the exchange cannot overshoot. SWMM surcharges with its Preissmann slot.")
    return ""


SETUP_NOTE = "The suite applied the proposed settings to its own model files and re-ran it:"


def approach(key: str, sid: str, solver: dict | None = None) -> str:
    """How ``key`` was modelled on test ``sid``. For a proposed set-up, its base model's method plus the changes."""
    solver = solver or {}
    if solver.get("kind") == "setup" and solver.get("base"):
        return approach(solver["base"], sid)
    if key in SWMM_ENGINE or key is None:
        return _swmm(key, sid) if key else ""
    if key.startswith("hecras") and key != "hecras-pipes":
        return _hecras(key, sid)
    if sid.startswith("A12"):
        return _coupled(key, sid)
    if key in ("demo1d", "demo2d"):
        return _two_d(key, sid)
    if sid.startswith("A1P") or key in ("epanet22", "epanet20", "wntr", "hydra-wds", "tsnet"):
        return _pipes(key, sid)
    return _two_d(key, sid)
