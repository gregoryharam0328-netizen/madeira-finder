"""Shared ORM query for dashboard cards and listing routes (one row per listing group)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import String, Uuid, cast, func, select
from sqlalchemy.orm import Session

from app.models import Listing, ListingGroup, ListingGroupMember, Source, UserListingState


def group_display_listing_subquery():
    """
    One listing row per group via listing_group_members.
    Postgres has no min(uuid); pick one id per group via min(text)::uuid.
    """
    return (
        select(
            ListingGroupMember.listing_group_id,
            cast(func.min(cast(ListingGroupMember.listing_id, String)), Uuid).label("display_listing_id"),
        )
        .group_by(ListingGroupMember.listing_group_id)
        .subquery()
    )


def base_query(db: Session, user_id: UUID):
    disp = group_display_listing_subquery()
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
