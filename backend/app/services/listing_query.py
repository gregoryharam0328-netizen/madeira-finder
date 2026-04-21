"""Shared ORM query for dashboard cards and listing routes (one row per listing group)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import String, Uuid, cast, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Listing, ListingGroup, ListingGroupMember, Source, UserListingState
from app.services.normalization import _client_price_bounds_eur


def group_display_listing_subquery(*, brief_only: bool = False):
    """
    One listing row per group via listing_group_members.
    Postgres has no min(uuid); pick one id per group via min(text)::uuid.

    When ``brief_only`` is True, only members that match the client brief (eligible,
    active, price within configured EUR band) are considered — so the card never
    shows a filtered_out or out-of-band duplicate from the same cluster.
    """
    stmt = (
        select(
            ListingGroupMember.listing_group_id,
            cast(func.min(cast(ListingGroupMember.listing_id, String)), Uuid).label("display_listing_id"),
        )
        .select_from(ListingGroupMember)
    )
    if brief_only:
        min_eur, max_eur = _client_price_bounds_eur()
        stmt = stmt.join(Listing, Listing.id == ListingGroupMember.listing_id).where(
            Listing.is_active.is_(True),
            Listing.eligibility_status == "eligible",
            Listing.price.isnot(None),
            Listing.price >= min_eur,
            Listing.price <= max_eur,
        )
    stmt = stmt.group_by(ListingGroupMember.listing_group_id)
    return stmt.subquery()


def base_query(db: Session, user_id: UUID, *, display_brief_only: bool = True):
    disp = group_display_listing_subquery(brief_only=display_brief_only)
    return (
        db.query(ListingGroup, Listing, Source, UserListingState)
        .join(disp, disp.c.listing_group_id == ListingGroup.id)
        .join(Listing, Listing.id == disp.c.display_listing_id)
        .outerjoin(Source, Source.id == Listing.source_id)
        .outerjoin(
            UserListingState,
            (UserListingState.listing_group_id == ListingGroup.id) & (UserListingState.user_id == user_id),
        )
    )
