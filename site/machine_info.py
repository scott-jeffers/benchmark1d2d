import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner" / "python"))
from benchmark1d2d.machine import specs, summary  # noqa: E402,F401
