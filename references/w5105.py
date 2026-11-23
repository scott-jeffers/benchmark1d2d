"""Tabulated reference profiles from the Environment Agency's 2D/1D benchmarking report (W5-105).

The W5-105 river tests (Tests A and F of TR1) give water levels along the reach
computed by the report's authors from the steady gradually-varied-flow equation.
They are tabulated, not closed-form, so this generator interpolates the table
committed with the case (``reference/profiles.csv``, columns ``x`` and ``h``).

The table is not committed yet: the report's reuse terms are being confirmed
(see the case's ``SOURCE.md``). Until then the case stays a draft and this
function raises :class:`FileNotFoundError` with that explanation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def tabulated_profile(x, t: float = 0.0, table_path: str = "reference/profiles.csv", note: str = "") -> np.ndarray:
    """Depth at positions ``x`` (m), linearly interpolated from the committed table."""
    path = Path(table_path)
    if not path.is_file():
        raise FileNotFoundError(f"pending reference table {path.name}: " + (note or "not yet committed"))
    data = np.genfromtxt(path, delimiter=",", names=True)
    return np.interp(np.asarray(x, dtype=float), data["x"], data["h"])
