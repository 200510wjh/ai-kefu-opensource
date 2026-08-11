from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.internal_growth.workflows import run_daily_growth_workflow


SCHEDULER_TASK: asyncio.Task[None] | None = None


def schedule_enabled() -> bool:
    return os.getenv("INTERNAL_GROWTH_ENABLE_DAILY_SCHEDULE", "").lower() in {"1", "true", "yes"}


def schedule_time() -> tuple[int, int]:
    raw = os.getenv("INTERNAL_GROWTH_DAILY_TIME", "08:00")
    hour_text, minute_text = (raw.split(":", 1) + ["0"])[:2]
    return max(0, min(23, int(hour_text))), max(0, min(59, int(minute_text)))


def schedule_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("INTERNAL_GROWTH_TIMEZONE", "Asia/Shanghai"))


def next_run_at(now: datetime | None = None) -> datetime:
    tz = schedule_timezone()
    current = now.astimezone(tz) if now else datetime.now(tz)
    hour, minute = schedule_time()
    candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate


async def daily_scheduler_loop() -> None:
    while True:
        target = next_run_at()
        await asyncio.sleep(max(1, (target - datetime.now(target.tzinfo)).total_seconds()))
        run_daily_growth_workflow("schedule")


def maybe_start_scheduler() -> asyncio.Task[None] | None:
    global SCHEDULER_TASK
    if not schedule_enabled():
        return None
    if SCHEDULER_TASK and not SCHEDULER_TASK.done():
        return SCHEDULER_TASK
    SCHEDULER_TASK = asyncio.create_task(daily_scheduler_loop())
    return SCHEDULER_TASK
