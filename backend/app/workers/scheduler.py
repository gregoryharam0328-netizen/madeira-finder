import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.workers.daily_runner import run as daily_run


def main():
    """
    Lightweight in-process scheduler.
    For production, prefer a platform scheduler (cron/railway/render) calling `daily_runner`.
    """
    scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        daily_run,
        "cron",
        hour=settings.daily_ingestion_local_hour,
        minute=settings.daily_ingestion_local_minute,
        id="daily_run",
    )
    scheduler.start()

    print(f"Scheduler started at {datetime.utcnow().isoformat()}Z. Next run(s):")
    for job in scheduler.get_jobs():
        print(f"- {job.id}: {job.next_run_time}")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
