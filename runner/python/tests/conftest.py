"""Pytest path setup for hydrobench and analytic references."""

from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
_HYDROBENCH_ROOT = Path(__file__).resolve().parents[3]

for path in (_PYTHON_ROOT, _HYDROBENCH_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
