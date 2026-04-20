from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Listing, ListingEvent, ListingGroup, ListingGroupMember


def _get_listing_group_id(db: Session, listing_id: UUID) -> UUID | None:
    m = db.query(ListingGroupMember).filter(ListingGroupMember.listing_id == listing_id).first()
    return m.listing_group_id if m else None


def find_existing_same_source(
    db: Session,
    source_id: UUID,
    canonical_url: str,
    source_listing_id: str | None,
) -> Listing | None:
    q = db.query(Listing).filter(Listing.source_id == source_id)
    existing = q.filter(Listing.canonical_url == canonical_url).first()
    if existing:
        return existing
    if source_listing_id:
        existing = q.filter(Listing.source_listing_id == source_listing_id).first()
        if existing:
            return existing
    return None


def find_group_match_any_source(db: Session, fingerprint: str | None) -> tuple[UUID | None, str | None, float | None]:
    """
    Cross-source grouping hint. IMPORTANT: do not treat this as an "existing listing" to update,
    because the same property can appear on multiple sources with different URLs.
    """
    if not fingerprint:
        return None, None, None
    existing = db.query(Listing).filter(Listing.fingerprint == fingerprint).order_by(Listing.first_seen_at.asc()).first()
    if not existing:
        return None, None, None
    group_id = _get_listing_group_id(db, existing.id)
    return group_id, "fingerprint", 92.0


def attach_listing_to_group(db: Session, listing: Listing, group_id: UUID | None, method: str, score: float):
    # Already attached
    if db.query(ListingGroupMember).filter(ListingGroupMember.listing_id == listing.id).first():
        return

    if group_id:
        db.add(
            ListingGroupMember(
                listing_group_id=group_id,
                listing_id=listing.id,
                match_method=method,
                match_score=score,
            )
        )
        return

    group = ListingGroup(group_status="active", confidence_score=score)
    db.add(group)
    db.flush()
    db.add(ListingGroupMember(listing_group_id=group.id, listing_id=listing.id, match_method=method, match_score=score))


def upsert_listing(db: Session, source_id: UUID, payload: dict, raw_listing_id: UUID | None = None):
    """
    Persist the property in `listings` first, then rows that FK to it:
    `listing_events`, and via `attach_listing_to_group` → `listing_groups` / `listing_group_members`.
    """
    # 1) Strong identity within same source: update the existing listing row
    existing = find_existing_same_source(db, source_id, payload["canonical_url"], payload.get("source_listing_id"))
    if existing:
        old_price = float(existing.price) if existing.price is not None else None
        new_price = payload.get("price")

        existing.title = payload["title"]
        existing.normalized_title = payload.get("normalized_title")
        existing.description = payload.get("description")
        existing.normalized_description = payload.get("normalized_description")
        existing.price = new_price
        existing.location_text = payload.get("location_text")
        existing.normalized_location = payload.get("normalized_location")
        existing.area_name = payload.get("area_name")
        existing.municipality = payload.get("municipality")
        existing.bedrooms = payload.get("bedrooms")
        existing.bathrooms = payload.get("bathrooms")
        existing.property_type = payload.get("property_type")
        existing.listing_type = payload.get("listing_type", "sale")
        existing.image_url = payload.get("image_url")
        existing.image_urls = payload.get("image_urls")
        existing.fingerprint = payload.get("fingerprint")
        existing.raw_listing_id = raw_listing_id
        existing.last_seen_at = datetime.utcnow()

        event = "updated"
        if old_price is not None and new_price is not None and old_price != float(new_price):
            event = "price_changed"

        db.add(
            ListingEvent(
                listing_id=existing.id,
                event_type=event,
                old_value_json={"price": old_price} if event == "price_changed" else None,
                new_value_json={"price": float(new_price) if new_price is not None else None},
            )
        )
        return existing, False

    # 2) New listing row. If fingerprint matches, group it with the existing property cluster.
    group_id, method, score = find_group_match_any_source(db, payload.get("fingerprint"))

    listing = Listing(
        source_id=source_id,
        raw_listing_id=raw_listing_id,
        source_listing_id=payload.get("source_listing_id"),
        canonical_url=payload["canonical_url"],
        source_url=payload["source_url"],
        title=payload["title"],
        normalized_title=payload.get("normalized_title"),
        description=payload.get("description"),
        normalized_description=payload.get("normalized_description"),
        price=payload.get("price"),
        currency=payload.get("currency", "EUR"),
        location_text=payload.get("location_text"),
        normalized_location=payload.get("normalized_location"),
        area_name=payload.get("area_name"),
        municipality=payload.get("municipality"),
        bedrooms=payload.get("bedrooms"),
        bathrooms=payload.get("bathrooms"),
        property_type=payload.get("property_type"),
        listing_type=payload.get("listing_type", "sale"),
        image_url=payload.get("image_url"),
        published_at=payload.get("published_at"),
        fingerprint=payload.get("fingerprint"),
        eligibility_status=payload.get("eligibility_status", "eligible"),
    )

    db.add(listing)
    db.flush()

    db.add(ListingEvent(listing_id=listing.id, event_type="new", new_value_json={"title": listing.title}))
    attach_listing_to_group(db, listing, group_id=group_id, method=method or "manual", score=score or 100.0)
    return listing, True
