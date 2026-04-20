"""Serialize listing group rows into API card models."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Listing, ListingEvent, ListingGroup, ListingGroupMember, Source, UserListingState
from app.schemas import ListingCardOut, PortalLinkOut
from app.services.user_workflow import effective_workflow

# Full listing descriptions are huge JSON; cards only show a short blurb — trim to speed API + frontend.
_LIST_CARD_DESCRIPTION_MAX = 400


def _trim_description_for_list_card(text: str | None) -> str | None:
    if text is None:
        return None
    s = str(text).strip()
    if len(s) <= _LIST_CARD_DESCRIPTION_MAX:
        return s
    return s[: _LIST_CARD_DESCRIPTION_MAX - 1].rstrip() + "…"


def batch_price_reduced(db: Session, listing_ids: list[UUID]) -> dict[UUID, bool]:
    """True if any recorded price change lowered the asking price for that listing row."""
    if not listing_ids:
        return {}
    evs = (
        db.query(ListingEvent)
        .filter(ListingEvent.listing_id.in_(listing_ids), ListingEvent.event_type == "price_changed")
        .all()
    )
    out: dict[UUID, bool] = {}
    for e in evs:
        old_p = (e.old_value_json or {}).get("price")
        new_p = (e.new_value_json or {}).get("price")
        try:
            if old_p is not None and new_p is not None and float(old_p) > float(new_p):
                out[e.listing_id] = True
        except (TypeError, ValueError):
            continue
    return out


def batch_group_portal_links(db: Session, group_ids: list[UUID]) -> dict[UUID, list[tuple[str, str]]]:
    """Per listing_group_id: unique (source name, source_url) for active member listings."""
    if not group_ids:
        return {}
    rows = (
        db.query(ListingGroupMember.listing_group_id, Source.name, Listing.source_url)
        .join(Listing, Listing.id == ListingGroupMember.listing_id)
        .join(Source, Source.id == Listing.source_id)
        .filter(ListingGroupMember.listing_group_id.in_(group_ids), Listing.is_active.is_(True))
        .all()
    )
    grouped: dict[UUID, list[tuple[str, str]]] = defaultdict(list)
    seen_by_group: dict[UUID, set[str]] = defaultdict(set)
    for gid, name, surl in rows:
        if not surl or not str(surl).strip():
            continue
        url = str(surl).strip()
        if url in seen_by_group[gid]:
            continue
        seen_by_group[gid].add(url)
        grouped[gid].append((name or "Source", url))
    for gid, pairs in grouped.items():
        pairs.sort(key=lambda x: x[0].lower())
    return dict(grouped)


def serialize_listing_rows(db: Session, rows: list) -> list[ListingCardOut]:
    listing_ids = [r[1].id for r in rows]
    reduced = batch_price_reduced(db, listing_ids)
    group_ids = [r[0].id for r in rows]
    portal_by_group = batch_group_portal_links(db, group_ids)
    out: list[ListingCardOut] = []
    for row in rows:
        group, listing, source, state = row
        wf = effective_workflow(state)
        plinks = [PortalLinkOut(source_name=n, url=u) for n, u in portal_by_group.get(group.id, [])]
        out.append(
            ListingCardOut(
                listing_group_id=str(group.id),
                title=listing.title,
                description=_trim_description_for_list_card(listing.description),
                price=float(listing.price) if listing.price is not None else None,
                currency=listing.currency,
                location_text=listing.location_text,
                area_name=listing.area_name,
                municipality=listing.municipality,
                bedrooms=listing.bedrooms,
                property_type=listing.property_type,
                image_url=listing.image_url,
                source_url=listing.source_url or listing.canonical_url,
                canonical_url=listing.canonical_url,
                portal_links=plinks,
                primary_source=source.name if source else None,
                eligibility_status=listing.eligibility_status,
                group_status=group.group_status,
                workflow_status=wf,
                note=state.note if state else None,
                price_reduced=bool(reduced.get(listing.id)),
                is_saved=bool(state and state.is_saved),
                is_seen=bool(state and state.is_seen),
                is_hidden=bool(state and state.is_hidden),
                published_at=listing.published_at.isoformat() if listing.published_at else None,
                first_seen_at=listing.first_seen_at.isoformat() if listing.first_seen_at else None,
                last_seen_at=listing.last_seen_at.isoformat() if listing.last_seen_at else None,
            )
        )
    return out
