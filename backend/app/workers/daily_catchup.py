"""
If the API starts after today's configured ingestion time (see daily_ingestion_local_hour)
and no successful *scheduled* scrape has finished since that slot, run daily ingestion once.

Before that wall time each day, catch-up does nothing so the automatic 05:00 run is not duplicated early.
"""

from __future__ import annotations

import logging

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal
from app.datetime_utils import is_past_todays_ingestion_slot, local_today_scheduled_ingestion_utc_naive, to_utc_naive
from app.models import ScrapeRun

log = logging.getLogger(__name__)


def is_daily_ingestion_missing_for_today(db) -> bool:
    """True if we should run catch-up (local time is past today's slot and no successful scheduled run since then)."""
    if not is_past_todays_ingestion_slot():
        return False
    day_start = local_today_scheduled_ingestion_utc_naive()
    latest = (
        db.query(func.max(ScrapeRun.started_at))
        .filter(ScrapeRun.run_type == "scheduled", ScrapeRun.status == "success")
        .scalar()
    )
    latest_naive = to_utc_naive(latest)
    if latest_naive is None:
        return True
    return latest_naive < day_start


def ensure_today_ingestion_if_missed() -> None:
    if not settings.enable_startup_daily_catchup:
        return
    db = SessionLocal()
    try:
        if not is_daily_ingestion_missing_for_today(db):
            return
    finally:
        db.close()

    log.info(
        "No successful scheduled scrape since today's %02d:%02d %s slot — running daily ingestion catch-up.",
        settings.daily_ingestion_local_hour,
        settings.daily_ingestion_local_minute,
        settings.app_timezone,
    )
    from app.workers.daily_runner import run as daily_run

    try:
        daily_run()
    except Exception:
        log.exception("Daily ingestion catch-up failed")
