from __future__ import annotations

import time
from pathlib import Path


class LocalSendGate:
    def __init__(self, min_gap_seconds: float) -> None:
        self.min_gap_seconds = min_gap_seconds
        self.last_send_at = 0.0

    def can_send(self) -> bool:
        return not self.last_send_at or time.time() - self.last_send_at >= self.min_gap_seconds

    def mark_sent(self) -> None:
        self.last_send_at = time.time()


def is_locally_paused(path: str) -> bool:
    return bool(path and Path(path).exists())
