"""Print why New Today may be empty. Run: PYTHONPATH=. python scripts/diag_new_today.py"""

from app.config import settings
from app.database import SessionLocal
from app.datetime_utils import local_today_midnight_utc_naive
from app.models import Listing


def main() -> None:
    db = SessionLocal()
    try:
        today = local_today_midnight_utc_naive()
        n_all = db.query(Listing).count()
        n_today = (
            db.query(Listing)
            .filter(Listing.first_seen_at >= today, Listing.is_active.is_(True), Listing.eligibility_status == "eligible")
            .count()
        )
        apify = bool((settings.apify_token or "").strip())
        print("APP_TIMEZONE:", settings.app_timezone)
        print("Today window starts (UTC-naive):", today)
        print("Total listing rows:", n_all)
        print("Eligible listings with first_seen_at in today window:", n_today)
        print("APIFY_TOKEN set:", apify)
        if n_all > 0 and n_today == 0:
            print(
                '\nNote: You have older listings but none first-seen since local midnight '
                '(New Today only shows rows first seen on this calendar day in APP_TIMEZONE).'
            )
        if not apify:
            print("\nIdealista returns no items until APIFY_TOKEN is set in backend/.env")
    finally:
        db.close()


if __name__ == "__main__":
    main()
