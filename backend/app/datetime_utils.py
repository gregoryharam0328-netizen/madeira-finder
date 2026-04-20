"""Shared date helpers aligned with APP_TIMEZONE (e.g. Madeira / Lisbon)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def local_today_midnight_utc_naive() -> datetime:
    """UTC-naive instant equal to today's 00:00 in the configured local timezone."""
    tz = ZoneInfo(settings.app_timezone)
    now_local = datetime.now(tz)
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_utc = midnight_local.astimezone(timezone.utc)
    return midnight_utc.replace(tzinfo=None)


def to_utc_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def local_today_scheduled_ingestion_utc_naive() -> datetime:
    """UTC-naive instant for today's daily_ingestion_local_hour:minute in APP_TIMEZONE."""
    tz = ZoneInfo(settings.app_timezone)
    now_local = datetime.now(tz)
    slot = now_local.replace(
        hour=settings.daily_ingestion_local_hour,
        minute=settings.daily_ingestion_local_minute,
        second=0,
        microsecond=0,
    )
    return slot.astimezone(timezone.utc).replace(tzinfo=None)


def is_past_todays_ingestion_slot() -> bool:
    """True once local wall time has reached today's configured ingestion slot."""
    tz = ZoneInfo(settings.app_timezone)
    now_local = datetime.now(tz)
    slot = now_local.replace(
        hour=settings.daily_ingestion_local_hour,
        minute=settings.daily_ingestion_local_minute,
        second=0,
        microsecond=0,
    )
    return now_local >= slot


def seconds_until_next_daily_ingestion() -> float:
    """Wall-clock seconds until the next daily_ingestion_local_hour:minute in APP_TIMEZONE."""
    tz = ZoneInfo(settings.app_timezone)
    now_local = datetime.now(tz)
    h = settings.daily_ingestion_local_hour
    m = settings.daily_ingestion_local_minute
    slot_today = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    if now_local < slot_today:
        next_run = slot_today
    else:
        next_run = slot_today + timedelta(days=1)
    return max(1.0, (next_run - now_local).total_seconds())
