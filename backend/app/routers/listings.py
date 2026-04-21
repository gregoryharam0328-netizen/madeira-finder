from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.datetime_utils import local_today_midnight_utc_naive
from app.models import Listing, ListingEvent, User, UserListingState
from app.services.listing_cards import serialize_listing_rows
from app.services.listing_query import base_query
from app.services.listing_visibility import filter_dismissed_not_interested, filter_visible_on_main_feed

router = APIRouter()


def _apply_listing_filters(
    query,
    *,
    min_price: float | None,
    max_price: float | None,
    bedrooms: int | None,
    property_type: str | None,
    only_new: bool,
    area: str | None,
    workflow_status: str | None,
):
    if min_price is not None:
        query = query.filter(Listing.price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.price <= max_price)
    if bedrooms is not None:
        query = query.filter(Listing.bedrooms >= bedrooms)
    if property_type:
        query = query.filter(Listing.property_type == property_type)
    if only_new:
        query = query.filter(Listing.first_seen_at >= local_today_midnight_utc_naive())
    if area and area.strip() and area.strip().lower() != "all":
        term = f"%{area.strip()}%"
        query = query.filter(
            or_(Listing.municipality.ilike(term), Listing.area_name.ilike(term), Listing.location_text.ilike(term))
        )
    if workflow_status and workflow_status.strip().lower() != "all":
        ws = workflow_status.strip().lower()
        if ws == "new":
            query = query.filter(
                or_(
                    UserListingState.id.is_(None),
                    UserListingState.workflow_status.is_(None),
                    UserListingState.workflow_status == "new",
                )
            )
        else:
            query = query.filter(UserListingState.workflow_status == ws)
    return query


def _apply_sort(query, sort: str | None):
    s = (sort or "newest").strip().lower()
    if s == "price_asc":
        return query.order_by(Listing.price.asc().nulls_last(), Listing.first_seen_at.desc())
    if s == "price_desc":
        return query.order_by(Listing.price.desc().nulls_last(), Listing.first_seen_at.desc())
    return query.order_by(Listing.first_seen_at.desc())


@router.get("")
def all_listings(
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    bedrooms: int | None = Query(None),
    property_type: str | None = Query(None),
    area: str | None = Query(None, description="Filter by municipality / area name (substring)."),
    workflow_status: str | None = Query(None, description="Filter by user workflow status."),
    sort: str | None = Query("newest", description="newest | price_asc | price_desc"),
    only_new: bool = Query(False),
    exclude_hidden: bool = Query(True),
    eligible_only: bool = Query(
        False,
        description="If true, only client-brief matches (eligible). If false (default), include filtered_out scrapes.",
    ),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = base_query(db, current_user.id)
    query = query.filter(Listing.is_active.is_(True))
    if eligible_only:
        query = query.filter(Listing.eligibility_status == "eligible")
    else:
        query = query.filter(Listing.eligibility_status.in_(["eligible", "filtered_out"]))
    ws_for_visibility = (workflow_status or "").strip().lower() if workflow_status else ""
    if exclude_hidden:
        # "Not interested" lives off the main feed; allow browsing via explicit workflow filter.
        if ws_for_visibility == "not_interested":
            query = filter_dismissed_not_interested(query)
        else:
            query = filter_visible_on_main_feed(query)
    query = _apply_listing_filters(
        query,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        property_type=property_type,
        only_new=only_new,
        area=area,
        workflow_status=workflow_status,
    )
    query = _apply_sort(query, sort)
    rows = query.offset(offset).limit(limit).all()
    return serialize_listing_rows(db, rows)


@router.get("/new")
def new_today(
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    bedrooms: int | None = Query(None),
    property_type: str | None = Query(None),
    area: str | None = Query(None),
    sort: str | None = Query("newest"),
    exclude_hidden: bool = Query(True),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = base_query(db, current_user.id).filter(Listing.first_seen_at >= local_today_midnight_utc_naive())
    query = query.filter(Listing.is_active.is_(True), Listing.eligibility_status == "eligible")
    if exclude_hidden:
        query = filter_visible_on_main_feed(query)
    query = _apply_listing_filters(
        query,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        property_type=property_type,
        only_new=False,
        area=area,
        workflow_status=None,
    )
    query = _apply_sort(query, sort)
    rows = query.offset(offset).limit(limit).all()
    return serialize_listing_rows(db, rows)


@router.get("/saved")
def saved(
    exclude_hidden: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = base_query(db, current_user.id).filter(UserListingState.is_saved.is_(True))
    query = query.filter(Listing.is_active.is_(True), Listing.eligibility_status.in_(["eligible", "filtered_out"]))
    if exclude_hidden:
        query = filter_visible_on_main_feed(query)
    rows = query.order_by(Listing.first_seen_at.desc()).offset(offset).limit(limit).all()
    return serialize_listing_rows(db, rows)


@router.get("/not-interested")
def not_interested_listings(
    sort: str | None = Query("newest", description="newest | price_asc | price_desc"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listing groups the user marked Not interested (still in DB; hidden from main feeds)."""
    query = base_query(db, current_user.id)
    query = query.filter(Listing.is_active.is_(True))
    query = query.filter(Listing.eligibility_status.in_(["eligible", "filtered_out"]))
    query = filter_dismissed_not_interested(query)
    query = _apply_sort(query, sort)
    rows = query.offset(offset).limit(limit).all()
    return serialize_listing_rows(db, rows)


@router.get("/price-changes")
def price_changes(
    exclude_hidden: bool = Query(True),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = base_query(db, current_user.id).join(ListingEvent, ListingEvent.listing_id == Listing.id).filter(
        ListingEvent.event_type == "price_changed"
    )
    query = query.filter(Listing.is_active.is_(True), Listing.eligibility_status == "eligible")
    if exclude_hidden:
        query = filter_visible_on_main_feed(query)
    rows = query.order_by(ListingEvent.detected_at.desc()).offset(offset).limit(limit).all()
    return serialize_listing_rows(db, rows)
