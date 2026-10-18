"""When a run happened, for the score card's ``timestamp`` (review F11: every card used to carry
2024-01-01). ``BENCH_TIMESTAMP`` (an ISO 8601 time) pins it, for byte-identical cards in tests and
reproductions; otherwise it is the current UTC time, to the second.

The collector (scripts/collect_results.py) only replaces a stored card when a measured value, the
solver, the case version or the machine changes, so a new time alone never rewrites the site.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone


def run_timestamp() -> str:
    pinned = os.environ.get("BENCH_TIMESTAMP")
    if pinned:
        return pinned
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
