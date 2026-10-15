"""Bounded, read-only samples of an already known launcher process."""

from __future__ import annotations

import time
from collections.abc import Callable

from .process_identity import observe_descendants, verify_identity
from .utils import now_iso


def sample_lineage(launcher: dict, *, sample_count: int = 10, interval_seconds: float = 0.1,
                   sleep: Callable[[float], None] = time.sleep) -> list[dict]:
    """Observe only; the caller owns scheduling and any explicit evidence storage."""
    if (not isinstance(sample_count, int) or isinstance(sample_count, bool)
            or not 1 <= sample_count <= 600 or not 0.05 <= interval_seconds <= 1.0
            or sample_count * interval_seconds > 60):
        raise ValueError("sampling must be 1-600 samples, 0.05-1.0 seconds apart, at most 60 seconds")
    observations = []
    for index in range(sample_count):
        scan = observe_descendants(launcher)
        launcher_state = verify_identity(launcher)["state"]
        children = scan["children"][:64]
        observations.append({"observed_at": now_iso(), "launcher_state": launcher_state,
                             "scan_state": scan["state"] if len(scan["children"]) <= 64 else "UNCONFIRMED",
                             "children_truncated": len(scan["children"]) > 64,
                             "children": children})
        if index + 1 < sample_count:
            sleep(interval_seconds)
    return observations
