from sqlalchemy import func

from app.database import SessionLocal
from app.models import Listing, ListingGroupMember


def main() -> None:
    db = SessionLocal()
    try:
        t = db.query(Listing).count()
        active = db.query(Listing).filter(Listing.is_active.is_(True)).count()
        elig = db.query(Listing).filter(Listing.eligibility_status == "eligible").count()
        both = (
            db.query(Listing)
            .filter(Listing.is_active.is_(True), Listing.eligibility_status == "eligible")
            .count()
        )
        members = db.query(ListingGroupMember).count()
        by_status = (
            db.query(Listing.eligibility_status, func.count())
            .group_by(Listing.eligibility_status)
            .all()
        )
        print("listings_total", t)
        print("listings_active", active)
        print("listings_eligible", elig)
        print("listings_active_and_eligible", both)
        print("listing_group_members", members)
        print("eligibility_status breakdown:", by_status)
    finally:
        db.close()


if __name__ == "__main__":
    main()
