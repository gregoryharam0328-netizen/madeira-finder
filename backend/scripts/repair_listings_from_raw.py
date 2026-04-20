"""Re-sync listing price/image from listings_raw. Run: PYTHONPATH=. python scripts/repair_listings_from_raw.py"""

from app.database import SessionLocal
from app.services.listing_repair import repair_listings_from_last_raw


def main() -> None:
    db = SessionLocal()
    try:
        n = repair_listings_from_last_raw(db)
        db.commit()
        print(f"Repaired {n} listing(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
