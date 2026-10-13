"""Hydrologic and inundation scoring metrics.

References
----------
Nash, J. E., and Sutcliffe, J. V. (1970). "River flow forecasting through
conceptual models part I – A discussion of principles." *J. Hydrol.*, 10(3),
282–290.

Gupta, H. V., Kling, H., Yilmaz, K. K., and Martinez, G. F. (2009).
"Decomposition of the mean squared error and NSE performance criteria:
Implications for improving hydrological modelling." *J. Hydrol.*, 377(1–2),
80–91.

Bates, P. D., and De Roo, A. P. J. (2000). "A simple raster-based model for
flood inundation simulation." *J. Hydrol.*, 236(1–2), 54–77.
"""

from __future__ import annotations

import numpy as np


def global_mass_error(sim_volume: float, ref_volume: float) -> float:
    """Percent global mass (volume) error: ``100 * (sim - ref) / ref``.

    Parameters
    ----------
    sim_volume, ref_volume :
        Simulated and reference total volumes (same units).

    Returns
    -------
    float
        Relative error in percent.
    """
    ref_volume = float(ref_volume)
    if ref_volume == 0.0:
        raise ValueError("ref_volume must be non-zero")
    return float(100.0 * (float(sim_volume) - ref_volume) / ref_volume)


def nse(sim, obs) -> float:
    """Nash–Sutcliffe efficiency (Nash & Sutcliffe 1970).

    ``NSE = 1 - Σ(sim - obs)² / Σ(obs - mean(obs))²``.

    Returns 1.0 for a perfect match; ``-inf`` if the observation variance is
    zero and the series are not identical.
    """
    sim = np.asarray(sim, dtype=float).ravel()
    obs = np.asarray(obs, dtype=float).ravel()
    if sim.shape != obs.shape:
        raise ValueError("sim and obs must have the same shape")
    denom = np.sum((obs - np.mean(obs)) ** 2)
    if denom == 0.0:
        if np.allclose(sim, obs):
            return 1.0
        return float("-inf")
    return float(1.0 - np.sum((sim - obs) ** 2) / denom)


def kge(sim, obs) -> float:
    """Kling–Gupta efficiency (Gupta et al. 2009).

    ``KGE = 1 - sqrt((r - 1)² + (α - 1)² + (β - 1)²)`` where ``r`` is the
    linear correlation, ``α = σ_sim / σ_obs`` and ``β = μ_sim / μ_obs``.
    """
    sim = np.asarray(sim, dtype=float).ravel()
    obs = np.asarray(obs, dtype=float).ravel()
    if sim.shape != obs.shape:
        raise ValueError("sim and obs must have the same shape")
    if sim.size < 2:
        raise ValueError("kge requires at least two samples")

    mu_s = float(np.mean(sim))
    mu_o = float(np.mean(obs))
    sigma_s = float(np.std(sim, ddof=0))
    sigma_o = float(np.std(obs, ddof=0))

    if sigma_o == 0.0 or mu_o == 0.0:
        raise ValueError("obs must have non-zero mean and variance for KGE")

    # Pearson correlation; identical constant series already rejected above.
    if sigma_s == 0.0:
        r = 0.0
    else:
        r = float(np.corrcoef(sim, obs)[0, 1])

    alpha = sigma_s / sigma_o
    beta = mu_s / mu_o
    return float(1.0 - np.sqrt((r - 1.0) ** 2 + (alpha - 1.0) ** 2 + (beta - 1.0) ** 2))


def peak_error(sim, obs) -> float:
    """Relative peak error: ``(max(sim) - max(obs)) / max(obs)``.

    Useful for Joukowsky-style pressure-rise checks and hydrograph peaks.
    """
    sim = np.asarray(sim, dtype=float)
    obs = np.asarray(obs, dtype=float)
    obs_max = float(np.max(obs))
    if obs_max == 0.0:
        raise ValueError("obs peak must be non-zero")
    return float((float(np.max(sim)) - obs_max) / obs_max)


def arrival_time_error(t, sim, obs, threshold: float) -> float:
    """Time difference of first exceedance of ``threshold``.

    Returns ``t_sim - t_obs`` where each is the first time the respective
    series is ``>= threshold``.
    """
    t = np.asarray(t, dtype=float).ravel()
    sim = np.asarray(sim, dtype=float).ravel()
    obs = np.asarray(obs, dtype=float).ravel()
    if not (t.size == sim.size == obs.size):
        raise ValueError("t, sim and obs must have the same length")

    sim_idx = np.where(sim >= threshold)[0]
    obs_idx = np.where(obs >= threshold)[0]
    if sim_idx.size == 0 or obs_idx.size == 0:
        raise ValueError("threshold never exceeded in sim and/or obs")
    return float(t[sim_idx[0]] - t[obs_idx[0]])


def front_position_error(x, h, h_threshold: float, exact_front: float) -> float:
    """Absolute front-position error against an exact location.

    The detected front is the farthest abscissa where ``h >= h_threshold``
    (wet/dry interface for a dam-break style profile).
    """
    x = np.asarray(x, dtype=float).ravel()
    h = np.asarray(h, dtype=float).ravel()
    if x.size != h.size:
        raise ValueError("x and h must have the same length")
    wet = h >= h_threshold
    if not np.any(wet):
        raise ValueError("no wet cells above h_threshold")
    detected = float(np.max(x[wet]))
    return float(abs(detected - float(exact_front)))


def csi(sim_wet, obs_wet) -> float:
    """Critical Success Index (threat score) for binary wet/dry maps.

    Following Bates & De Roo (2000)::

        CSI = hits / (hits + misses + false_alarms)

    where hits are cells wet in both, misses are observed-wet / simulated-dry,
    and false alarms are simulated-wet / observed-dry.
    """
    sim_wet = np.asarray(sim_wet, dtype=bool).ravel()
    obs_wet = np.asarray(obs_wet, dtype=bool).ravel()
    if sim_wet.shape != obs_wet.shape:
        raise ValueError("sim_wet and obs_wet must have the same shape")

    hits = int(np.sum(sim_wet & obs_wet))
    misses = int(np.sum(~sim_wet & obs_wet))
    false_alarms = int(np.sum(sim_wet & ~obs_wet))
    denom = hits + misses + false_alarms
    if denom == 0:
        # Both maps entirely dry — perfect agreement on the null event.
        return 1.0
    return float(hits / denom)
