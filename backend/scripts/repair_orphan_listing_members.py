"""
Attach listings that have no listing_group_members row (UI base_query ignores them).

Run from backend/ with PYTHONPATH=. :
  python scripts/repair_orphan_listing_members.py
"""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Listing, ListingGroupMember
from app.services.dedup import attach_listing_to_group


def repair(db: Session) -> int:
    q = (
        db.query(Listing)
        .outerjoin(ListingGroupMember, ListingGroupMember.listing_id == Listing.id)
        .filter(ListingGroupMember.id.is_(None))
    )
    orphans = q.all()
    n = 0
    for listing in orphans:
        attach_listing_to_group(db, listing, group_id=None, method="manual", score=100.0)
        n += 1
    db.commit()
    return n


def main() -> None:
    db = SessionLocal()
    try:
        n = repair(db)
        print(f"Repaired {n} listing(s) missing group membership.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
