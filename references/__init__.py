"""Analytic reference solution generators for hydrobench Track A.

Each submodule implements a classic closed-form (or semi-analytic) solution
used as ground truth for verification benchmarks.
"""

from references.ritter import depth_velocity as ritter_depth_velocity
from references.ritter import front_position as ritter_front_position
from references.stoker import depth_velocity as stoker_depth_velocity
from references.stoker import intermediate_state as stoker_intermediate_state
from references.macdonald import bed_elevation as macdonald_bed_elevation
from references.macdonald import depth_profile as macdonald_depth_profile
from references.joukowsky import delta_p as joukowsky_delta_p
from references.joukowsky import pressure_wave as joukowsky_pressure_wave
from references.thacker import depth_velocity as thacker_depth_velocity
from references.thacker import bed_elevation as thacker_bed_elevation

__all__ = [
    "ritter_depth_velocity",
    "ritter_front_position",
    "stoker_depth_velocity",
    "stoker_intermediate_state",
    "macdonald_depth_profile",
    "macdonald_bed_elevation",
    "joukowsky_delta_p",
    "joukowsky_pressure_wave",
    "thacker_depth_velocity",
    "thacker_bed_elevation",
]
