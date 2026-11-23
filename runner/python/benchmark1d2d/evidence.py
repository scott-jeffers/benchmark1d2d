"""Evidence categories and capability groups (protocol 4.0).

Every case in the catalogue is one kind of evidence and exercises one or more
capabilities. The site's evidence profiles are organised by these two axes:
a model's profile shows, for each capability, what each kind of evidence says
about it. Nothing here ranks models.

The three kinds of evidence answer different questions and are never averaged
together:

* ``verification`` -- the truth is an exact or manufactured solution. A miss
  means the code (or its numerics as configured) is wrong.
* ``validation`` -- the truth is a measurement with an uncertainty. A miss can
  come from the code, the set-up, the data or the equations themselves.
* ``comparison`` -- there is no independent truth: the result is compared with
  a pinned reference engine or with settled states derived from the inputs.
  A difference shows only that two codes differ.

The evidence kind follows from the manifest's ``test_class``; the manifest
also states it explicitly (``evidence``) and ``tools/validate_catalog.py``
checks the two agree.
"""

from __future__ import annotations

EVIDENCE = {
    "verification": {
        "name": "Verification",
        "short": "exact solution",
        "truth": "an exact or manufactured solution",
        "a_miss_means": "the code, or its numerics as configured, is wrong",
    },
    "validation": {
        "name": "Validation",
        "short": "measurement",
        "truth": "a measurement, with its uncertainty",
        "a_miss_means": "something is wrong: the code, the set-up, the data or the equations",
    },
    "comparison": {
        "name": "Comparison",
        "short": "another code",
        "truth": "another code (a pinned reference engine), or states that follow from the inputs; nothing independent",
        "a_miss_means": "only that two codes differ",
    },
}

EVIDENCE_OF_CLASS = {
    "verification_analytic": "verification",
    "verification_manufactured": "verification",
    "validation_lab": "validation",
    "validation_field": "validation",
    "validation_coupled": "validation",
    "intercomparison": "comparison",
    "parity": "comparison",
    "regression": "comparison",
    "stress": "comparison",
}

# HydroCouple openswmm.engine.benchmarks reference classes (docs/concepts/grading.html)
# mapped onto the three kinds, so results can move between the two suites.
HYDROCOUPLE_CLASS = {
    "analytic": "verification",
    "manufactured": "verification",
    "observed": "validation",
    "external_reference": "comparison",
    "blessed_baseline": "comparison",
    "self_consistency": "comparison",
}

# Capability groups, in the order the profiles show them. ``engineer`` is the
# plain-language line at the top of each group: what evidence in this group
# tells a practising engineer.
CAPABILITIES = {
    "wet_dry": {
        "name": "Wetting and drying",
        "engineer": "Whether flood edges advance and recede over dry ground without losing water or stalling.",
    },
    "still_water": {
        "name": "Still water stays still",
        "engineer": "Whether water at rest over uneven ground stays at rest, with no spurious currents.",
    },
    "steady_open_channel": {
        "name": "Steady open-channel profiles",
        "engineer": "Backwater, drawdown and friction-controlled water levels in rivers and channels.",
    },
    "shocks_jumps": {
        "name": "Shocks and hydraulic jumps",
        "engineer": "Where a jump or bore sits and how high it is, including transcritical flow.",
    },
    "flood_waves": {
        "name": "Dam-break and flood waves",
        "engineer": "How fast and how high a rapidly released flood travels.",
    },
    "inundation": {
        "name": "Floodplain inundation and storage",
        "engineer": "Final flooded extent and levels when water spreads into and fills low ground.",
    },
    "urban_surface": {
        "name": "Flow around buildings",
        "engineer": "Depths and velocities where streets and buildings steer the flow.",
    },
    "structures": {
        "name": "Bridges, culverts and weirs",
        "engineer": "Head losses and afflux at hydraulic structures in rivers and channels.",
    },
    "pipe_hydraulics": {
        "name": "Partly full and surcharged pipes",
        "engineer": "Depths, grade lines and capacity in gravity pipes, including surcharge.",
    },
    "storage_structures": {
        "name": "Storage, pumps and outlets",
        "engineer": "Ponds, wet wells, pumps on their curves and outlet rating relationships.",
    },
    "controls": {
        "name": "Operating rules and controls",
        "engineer": "Whether pumps, gates and rules switch when and as they should.",
    },
    "drainage_networks": {
        "name": "Drainage network routing",
        "engineer": "Flows and levels through whole sewer and stormwater networks.",
    },
    "pressure_networks": {
        "name": "Pressurised water networks",
        "engineer": "Steady heads and flows in pipes and looped distribution networks.",
    },
    "transients": {
        "name": "Water hammer",
        "engineer": "Pressure surges after rapid valve or pump changes.",
    },
    "transport": {
        "name": "Tracer and water-quality transport",
        "engineer": "How a dissolved substance is carried and spread by the flow.",
    },
    "coupled_exchange": {
        "name": "Sewer-surface exchange",
        "engineer": "Water leaving and re-entering a drainage network through manholes during flooding.",
    },
}


def evidence_of(manifest: dict) -> str:
    """The evidence kind of a manifest, from its stated field or its test class."""
    stated = manifest.get("evidence")
    return stated if stated else EVIDENCE_OF_CLASS[manifest["test_class"]]


def capabilities_of(manifest: dict) -> list[str]:
    """The manifest's capability groups, in profile order."""
    caps = set(manifest.get("capabilities") or [])
    return [c for c in CAPABILITIES if c in caps]
