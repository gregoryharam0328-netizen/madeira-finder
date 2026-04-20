from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.datetime_utils import local_today_midnight_utc_naive
from app.models import Listing, ListingEvent, ListingGroup, ScrapeRun, User, UserListingState
from app.schemas import DashboardSummary, IdealistaCsvImportRequest
from app.services.listing_query import base_query
from app.services.listing_visibility import filter_visible_on_main_feed

router = APIRouter()


def _ingestion_notices() -> list[str]:
    notes: list[str] = []
    if not (settings.apify_token or "").strip() and not (settings.idealista_csv_import_url or "").strip():
        notes.append(
            "Idealista will not return any listings until APIFY_TOKEN is set in the backend .env "
            "(see .env.example), unless you import from a dataset URL (IDEALISTA_CSV_IMPORT_URL). "
            "Other portals use HTML scraping and may still return zero rows if the site layout changed."
        )
    notes.append(
        "After clicking Fetch, check the scrape_runs table in Supabase: status, listings_found, and error_log "
        "show what each source did."
    )
    return notes


def _listable_cards_core(db: Session, user_id, *, eligible_only: bool):
    """
    All active listing groups in the workspace (eligible + filtered_out), including dismissed.
    No visibility filter — use for workspace-wide totals.
    """
    q = base_query(db, user_id)
    q = q.filter(Listing.is_active.is_(True))
    if eligible_only:
        q = q.filter(Listing.eligibility_status == "eligible")
    else:
        q = q.filter(Listing.eligibility_status.in_(["eligible", "filtered_out"]))
    return q


def _listable_cards_base(db: Session, user_id, *, eligible_only: bool):
    """
    Same join as GET /listings main grid: excludes Not interested / hidden from the feed.
    """
    return filter_visible_on_main_feed(_listable_cards_core(db, user_id, eligible_only=eligible_only))


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = local_today_midnight_utc_naive()
    # Workspace total = every active group (including dismissed). Do not use the visible-only subquery.
    all_groups_inner = (
        _listable_cards_core(db, current_user.id, eligible_only=False)
        .with_entities(ListingGroup.id.label("gid"))
        .subquery()
    )
    total = int(db.execute(select(func.count()).select_from(all_groups_inner)).scalar() or 0)

    # One pass over the visible grid for feed metrics (not total).
    listable_visible_inner = (
        _listable_cards_base(db, current_user.id, eligible_only=False)
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
    # Match GET /listings/saved (one row per group, eligible + active).
    saved = (
        base_query(db, current_user.id)
        .filter(Listing.is_active.is_(True), Listing.eligibility_status == "eligible")
        .filter(UserListingState.is_saved.is_(True))
        .count()
    )
    ux_stmt = (
        select(
            func.count().filter(UserListingState.is_hidden.is_(True)).label("hidden"),
            func.count().filter(UserListingState.is_seen.is_(True)).label("seen"),
        )
        .select_from(UserListingState)
        .where(UserListingState.user_id == current_user.id)
    )
    ux_row = db.execute(ux_stmt).one()
    hidden = int(ux_row.hidden or 0)
    seen = int(ux_row.seen or 0)
    not_interested_total = (
        base_query(db, current_user.id)
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
    # Match GET /listings/price-changes (exclude_hidden default true); distinct groups if multiple events.
    price_changes_q = filter_visible_on_main_feed(
        base_query(db, current_user.id)
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


@router.get("/ingestion-hints")
def ingestion_hints(current_user: User = Depends(get_current_user)):
    """Static hints for ingestion (real scrapers only; sample/mock data is not used)."""
    return {
        "notices": _ingestion_notices(),
    }


@router.post("/trigger-ingestion")
def trigger_ingestion(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Run the same pipeline as the scheduled daily job once, in the background (for testing or catch-up).
    Requires a logged-in user. Can take several minutes (scrapers + Apify).
    """
    from app.workers.daily_runner import run_logged

    background_tasks.add_task(run_logged)
    return {
        "ok": True,
        "message": "Daily ingestion started in the background. Any MockSource sample rows are cleared first; wait a few minutes, then click Refresh data.",
        "notices": _ingestion_notices(),
    }


@router.post("/remove-mock-listings")
def remove_mock_listings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all rows tied to MockSource (sample data). Safe if MockSource does not exist."""
    from app.services.mock_cleanup import remove_mock_source_data

    return remove_mock_source_data(db, commit=True)


@router.post("/import-idealista-csv")
def import_idealista_csv(
    body: IdealistaCsvImportRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download an Apify Idealista dataset (CSV, JSONL, or a single JSON array/object) and upsert into
    `listings` / `listings_raw`. Google Drive share links (`/file/d/.../view`) are rewritten to a direct download URL.
    Rows must pass strict checks (EUR price range, HTTP(S) image, resolvable bedrooms).
    """
    from app.services.idealista_csv_import import import_idealista_csv_from_url

    raw = (body.url if body else None) or settings.idealista_csv_import_url
    raw = (raw or "").strip()
    if not raw:
        raise HTTPException(
            status_code=400,
            detail="Provide `url` in the JSON body or set IDEALISTA_CSV_IMPORT_URL in the backend environment.",
        )
    try:
        return import_idealista_csv_from_url(db, raw)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/repair-listings-from-raw")
def repair_listings_from_raw(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fix active listings whose price or image disagrees with the stored `listings_raw` snapshot
    for the same URL (re-applies normalization). Run automatically after each daily ingestion; use this for a manual pass.
    """
    from app.services.listing_repair import repair_listings_from_last_raw

    n = repair_listings_from_last_raw(db)
    db.commit()
    return {
        "ok": True,
        "repaired": n,
        "message": f"Updated {n} listing(s) from raw scrape payloads where price or image was wrong.",
    }
