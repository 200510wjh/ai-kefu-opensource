from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path


class LocalSendGate:
    def __init__(self, min_gap_seconds: float, daily_limit: int = 0, state_file: str = "") -> None:
        self.min_gap_seconds = min_gap_seconds
        self.daily_limit = max(0, int(daily_limit or 0))
        self.state_file = state_file
        self.last_send_at = 0.0
        self.last_block_reason = ""
        self._day = date.today().isoformat()
        self._sent_today = 0
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_file:
            return
        path = Path(self.state_file)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if data.get("day") == self._day:
            self._sent_today = int(data.get("sent_today") or 0)
        self.last_send_at = float(data.get("last_send_at") or 0.0)

    def _save_state(self) -> None:
        if not self.state_file:
            return
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"day": self._day, "sent_today": self._sent_today, "last_send_at": self.last_send_at}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def can_send(self) -> bool:
        self.last_block_reason = ""
        if self.daily_limit and self._sent_today >= self.daily_limit:
            self.last_block_reason = "daily send limit"
            return False
        if self.last_send_at and time.time() - self.last_send_at < self.min_gap_seconds:
            self.last_block_reason = "local rate limit"
            return False
        return True

    def mark_sent(self) -> None:
        self.last_send_at = time.time()
        self._sent_today += 1
        self._save_state()


def is_locally_paused(path: str) -> bool:
    return bool(path and Path(path).exists())
