"""Analytic reference solution generators for benchmark1d2d Track A.

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
from references.thacker import planar_oscillation as thacker_planar_oscillation
from references.macdonald_2d import depth_velocity as macdonald_2d_depth_velocity
from references.macdonald_2d import depth_2d as macdonald_depth_2d
from references.oblique_jump import depth_velocity as oblique_jump_depth_velocity
from references.oblique_jump import shock_angle as oblique_jump_shock_angle

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
    "thacker_planar_oscillation",
    "macdonald_2d_depth_velocity",
    "macdonald_depth_2d",
    "oblique_jump_depth_velocity",
    "oblique_jump_shock_angle",
]
