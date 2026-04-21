"""Workspace dashboard totals — same rules as GET /dashboard/summary."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.datetime_utils import local_today_midnight_utc_naive
from app.models import Listing, ListingEvent, ListingGroup, ScrapeRun, UserListingState
from app.schemas import DashboardSummary
from app.services.listing_query import base_query
from app.services.listing_visibility import filter_visible_on_main_feed


def _listable_cards_core(db: Session, user_id: UUID, *, eligible_only: bool):
    q = base_query(db, user_id)
    q = q.filter(Listing.is_active.is_(True))
    if eligible_only:
        q = q.filter(Listing.eligibility_status == "eligible")
    else:
        q = q.filter(Listing.eligibility_status.in_(["eligible", "filtered_out"]))
    return q


def _listable_cards_base(db: Session, user_id: UUID, *, eligible_only: bool):
    return filter_visible_on_main_feed(_listable_cards_core(db, user_id, eligible_only=eligible_only))


def build_dashboard_summary(db: Session, user_id: UUID) -> DashboardSummary:
    today = local_today_midnight_utc_naive()
    all_groups_inner = (
        _listable_cards_core(db, user_id, eligible_only=False)
        .with_entities(ListingGroup.id.label("gid"))
        .subquery()
    )
    total = int(db.execute(select(func.count()).select_from(all_groups_inner)).scalar() or 0)

    listable_visible_inner = (
        _listable_cards_base(db, user_id, eligible_only=False)
        .with_entities(
            ListingGroup.id.label("gid"),
            Listing.eligibility_status.label("elig"),
            Listing.first_seen_at.label("first_seen"),
            UserListingState.workflow_status.label("wf"),
        )
        .subquery()
    )
    agg_stmt = select(
        func.count()
        .filter(and_(listable_visible_inner.c.elig == "eligible", listable_visible_inner.c.first_seen >= today))
        .label("new_today"),
        func.count().filter(listable_visible_inner.c.wf == "need_to_call").label("need_to_call"),
        func.count().filter(listable_visible_inner.c.wf == "viewing_arranged").label("viewing_arranged"),
    ).select_from(listable_visible_inner)
    agg_row = db.execute(agg_stmt).one()
    new_today = int(agg_row.new_today or 0)
    need_to_call = int(agg_row.need_to_call or 0)
    viewing_arranged = int(agg_row.viewing_arranged or 0)

    saved = (
        base_query(db, user_id)
        .filter(Listing.is_active.is_(True), Listing.eligibility_status.in_(["eligible", "filtered_out"]))
        .filter(UserListingState.is_saved.is_(True))
        .count()
    )
    ux_stmt = (
        select(
            func.count().filter(UserListingState.is_hidden.is_(True)).label("hidden"),
            func.count().filter(UserListingState.is_seen.is_(True)).label("seen"),
        )
        .select_from(UserListingState)
        .where(UserListingState.user_id == user_id)
    )
    ux_row = db.execute(ux_stmt).one()
    hidden = int(ux_row.hidden or 0)
    seen = int(ux_row.seen or 0)
    not_interested_total = (
        base_query(db, user_id)
        .filter(Listing.is_active.is_(True))
        .filter(Listing.eligibility_status.in_(["eligible", "filtered_out"]))
        .filter(
            UserListingState.id.isnot(None),
            or_(
                UserListingState.workflow_status == "not_interested",
                UserListingState.is_hidden.is_(True),
            ),
        )
        .count()
    )
    price_changes_q = filter_visible_on_main_feed(
        base_query(db, user_id)
        .join(ListingEvent, ListingEvent.listing_id == Listing.id)
        .filter(ListingEvent.event_type == "price_changed")
        .filter(Listing.is_active.is_(True), Listing.eligibility_status == "eligible")
    )
    price_changes_count = price_changes_q.distinct(ListingGroup.id).count()
    last_run = (
        db.query(ScrapeRun)
        .filter(ScrapeRun.status.in_(["success", "partial_success"]))
        .order_by(ScrapeRun.finished_at.desc().nulls_last(), ScrapeRun.started_at.desc())
        .first()
    )
    last_scan_at = None
    if last_run:
        ts = last_run.finished_at or last_run.started_at
        if ts:
            last_scan_at = ts.isoformat()
    return DashboardSummary(
        new_today=new_today,
        saved=saved,
        hidden=hidden,
        seen=seen,
        total=total,
        not_interested=not_interested_total,
        price_changes=price_changes_count,
        need_to_call=need_to_call,
        viewing_arranged=viewing_arranged,
        last_scan_at=last_scan_at,
    )
