"""Seeded random-bed MacDonald cases (review F14).

A1F-001 is one MacDonald (1997) manufactured bed with a Froude number near
0.1. A fixed case can be tuned to, and at that Froude number SWMM's
``NORMAL_FLOW_LIMITED SLOPE`` criterion (which caps a conduit's flow at the
upstream normal flow whenever the depth rises downstream) never matters. This
module draws a family of exact cases from a seed: the depth is a smooth random
profile (a few Fourier modes), scaled so the largest Froude number equals a
chosen cap, and the bed is constructed so that steady flow with Manning
friction holds exactly, as in :mod:`references.macdonald`.

The same seed gives the same case on every machine (NumPy's PCG64). A hidden
round publishes ``sha256(seed:salt)`` before the round and the seed and salt
after it (``commitment``), so nobody can tune to the case and anybody can check it.
"""

from __future__ import annotations

import hashlib

import numpy as np

from references.macdonald import bed_slope_from_depth

G = 9.81


def commitment(seed: int, salt: str = "") -> str:
    """What is published before a hidden round: the SHA-256 of ``"<seed>:<salt>"``. A small seed alone
    could be found by trying them all, so a round uses a random salt (``secrets.token_hex(16)``) and
    reveals it with the seed."""
    return hashlib.sha256(f"{int(seed)}:{salt}".encode("ascii")).hexdigest()


def draw(seed: int, froude_cap: float = 0.5, L: float = 1000.0, B: float = 10.0, Q: float = 2.0,
         n_manning: float = 0.03, modes: int = 4, relief: float = 0.35) -> dict:
    """One case: its parameters and the functions for depth and bed.

    The depth is ``h(x) = h0 (1 + relief · s(x))`` with ``s`` a sum of ``modes`` sine modes of random
    amplitude and phase, normalised to the range [−1, 1]; ``h0`` is set so the shallowest point has
    Froude number ``froude_cap`` (so the whole channel is subcritical for a cap below 1).
    """
    if not 0 < froude_cap < 1:
        raise ValueError("froude_cap must be in (0, 1): the construction is for subcritical flow")
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    k = np.arange(1, modes + 1)
    amp = rng.uniform(0.2, 1.0, modes) / k  # smoother at higher modes
    phase = rng.uniform(0.0, 2 * np.pi, modes)
    xs = np.linspace(0.0, L, 20001)
    raw = (amp[:, None] * np.sin(2 * np.pi * k[:, None] * xs[None, :] / L + phase[:, None])).sum(0)
    lo, hi = float(raw.min()), float(raw.max())
    scale, shift = 2.0 / (hi - lo), -(hi + lo) / (hi - lo)
    q = Q / B
    h_min = (q * q / (G * froude_cap ** 2)) ** (1.0 / 3.0)
    h0 = h_min / (1.0 - relief)

    def s(x):
        x = np.asarray(x, dtype=float)
        return scale * (amp[:, None] * np.sin(2 * np.pi * k[:, None] * x[None, :] / L + phase[:, None])).sum(0) + shift

    def ds(x):
        x = np.asarray(x, dtype=float)
        return scale * (amp[:, None] * (2 * np.pi * k[:, None] / L)
                        * np.cos(2 * np.pi * k[:, None] * x[None, :] / L + phase[:, None])).sum(0)

    def depth(x):
        return h0 * (1.0 + relief * s(x))

    zfine = np.empty_like(xs)
    dz = bed_slope_from_depth(depth(xs), h0 * relief * ds(xs), Q=Q, B=B, n_manning=n_manning, g=G)
    zfine[0] = 0.0
    zfine[1:] = np.cumsum(0.5 * (dz[1:] + dz[:-1]) * np.diff(xs))

    def bed(x):
        return np.interp(np.asarray(x, dtype=float), xs, zfine)

    h = depth(xs)
    return {
        "seed": int(seed), "froude_cap": froude_cap, "L": L, "B": B, "Q": Q,
        "n_manning": n_manning, "modes": modes, "relief": relief, "h0": h0,
        "h_downstream": float(depth(np.array([L]))[0]),
        "froude_max": float(q / np.sqrt(G * h.min() ** 3)),
        "depth": depth, "bed": bed,
    }
