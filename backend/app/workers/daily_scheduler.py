"""
Background loop: run ingestion every day at daily_ingestion_local_hour:minute (APP_TIMEZONE).

Startup catch-up (`ensure_today_ingestion_if_missed`) handles a missed slot when the
API starts after that time; this loop handles each following day while the process
stays up. Disable with ENABLE_DAILY_SCHEDULER=false if you use cron.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.datetime_utils import seconds_until_next_daily_ingestion

log = logging.getLogger(__name__)


async def daily_scheduler_loop() -> None:
    from app.workers.daily_runner import run_logged

    while True:
        delay = seconds_until_next_daily_ingestion()
        log.info(
            "Daily scheduler: sleeping %.0f s until next run at %02d:%02d %s",
            delay,
            settings.daily_ingestion_local_hour,
            settings.daily_ingestion_local_minute,
            settings.app_timezone,
        )
        await asyncio.sleep(delay)
        log.info(
            "Daily scheduler: running ingestion (%02d:%02d %s).",
            settings.daily_ingestion_local_hour,
            settings.daily_ingestion_local_minute,
            settings.app_timezone,
        )
        await asyncio.to_thread(run_logged)
