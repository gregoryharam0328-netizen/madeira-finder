"""
Remove listings (and related rows) created by seed_mock / MockSource.

Run from backend/ with PYTHONPATH=. :
  python scripts/delete_mock_listings.py
"""

from app.database import SessionLocal
from app.services.mock_cleanup import remove_mock_source_data


def main() -> None:
    db = SessionLocal()
    try:
        out = remove_mock_source_data(db, commit=True)
        print(out.get("message", out))
    finally:
        db.close()


if __name__ == "__main__":
    main()
