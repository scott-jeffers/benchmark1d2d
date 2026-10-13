"""Discrete L1 / L2 / L∞ error norms for field comparisons."""

from __future__ import annotations

import numpy as np


def L1(sim, ref, dx: float = 1.0) -> float:
    """Discrete L1 error: ``mean(|sim - ref|) * dx``.

    Parameters
    ----------
    sim, ref :
        Array-like fields (broadcastable).
    dx :
        Cell size / measure weight (default 1.0).

    Returns
    -------
    float
        Non-negative L1 error.
    """
    err = np.asarray(sim, dtype=float) - np.asarray(ref, dtype=float)
    return float(np.mean(np.abs(err)) * dx)


def L2(sim, ref, dx: float = 1.0) -> float:
    """Discrete L2 error: ``sqrt(mean((sim - ref)^2) * dx)``.

    Parameters
    ----------
    sim, ref :
        Array-like fields (broadcastable).
    dx :
        Cell size / measure weight (default 1.0).

    Returns
    -------
    float
        Non-negative L2 error.
    """
    err = np.asarray(sim, dtype=float) - np.asarray(ref, dtype=float)
    return float(np.sqrt(np.mean(err**2) * dx))


def Linf(sim, ref) -> float:
    """Discrete L∞ error: ``max(|sim - ref|)``.

    Parameters
    ----------
    sim, ref :
        Array-like fields (broadcastable).

    Returns
    -------
    float
        Non-negative L∞ error.
    """
    err = np.asarray(sim, dtype=float) - np.asarray(ref, dtype=float)
    return float(np.max(np.abs(err)))
