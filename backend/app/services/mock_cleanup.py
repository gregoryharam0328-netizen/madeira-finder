"""Remove rows tied to MockSource (sample data from seed_mock)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def remove_mock_source_data(db: Session, *, commit: bool = True) -> dict[str, object]:
    """
    Delete MockSource listings and related audit rows, empty groups, and the source itself.
    Works on SQLite and PostgreSQL (no schema-qualified table names).
    """
    sid = db.execute(text("SELECT id FROM sources WHERE name = :name LIMIT 1"), {"name": "MockSource"}).scalar()
    if not sid:
        return {
            "ok": True,
            "removed_listings": 0,
            "removed_source": False,
            "message": "No MockSource row — nothing to remove.",
        }

    try:
        db.execute(
            text(
                """
                DELETE FROM user_listing_state
                WHERE listing_group_id IN (
                  SELECT m.listing_group_id FROM listing_group_members m
                  INNER JOIN listings l ON l.id = m.listing_id
                  WHERE l.source_id = :sid
                )
                """
            ),
            {"sid": sid},
        )
        r = db.execute(text("DELETE FROM listings WHERE source_id = :sid"), {"sid": sid})
        removed_listings = getattr(r, "rowcount", -1)
        if removed_listings is None or removed_listings < 0:
            removed_listings = 0

        db.execute(
            text(
                """
                DELETE FROM listing_groups
                WHERE id NOT IN (SELECT listing_group_id FROM listing_group_members)
                """
            )
        )
        db.execute(text("DELETE FROM listings_raw WHERE source_id = :sid"), {"sid": sid})
        db.execute(text("DELETE FROM scrape_runs WHERE source_id = :sid"), {"sid": sid})
        db.execute(text("DELETE FROM sources WHERE id = :sid"), {"sid": sid})
        if commit:
            db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "removed_listings": removed_listings,
        "removed_source": True,
        "message": "MockSource and its listings, raw rows, and scrape runs were removed.",
    }
