from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import DashboardSummary, IdealistaCsvImportRequest
from app.services.dashboard_summary import build_dashboard_summary

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


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return build_dashboard_summary(db, current_user.id)


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


@router.post("/refetch-listing-prices")
def refetch_listing_prices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(300, ge=1, le=500, description="Max listings to process in one call."),
    delay_seconds: float = Query(0.7, ge=0.0, le=5.0, description="Pause between HTTP fetches to avoid hammering portals."),
    suspicious_only: bool = Query(
        True,
        description="If true, only rows with price NULL, < €20k, or > €2M (typical bad card parses).",
    ),
    source_name_contains: str | None = Query(
        "imovirtual",
        description="Substring match on source.name; pass * or all to include every source (slow).",
    ),
):
    """
    Re-open each listing's public URL, parse the asking price with current rules, and update
    ``listings`` plus the linked ``listings_raw`` snapshot. Use after fixing scraper logic when
    the DB still holds old inflated prices.
    """
    from app.services.listing_price_refetch import refetch_suspicious_listing_prices

    src_in = (source_name_contains or "").strip()
    src = None if src_in.lower() in ("*", "all") else src_in or None
    stats = refetch_suspicious_listing_prices(
        db,
        limit=limit,
        delay_seconds=delay_seconds,
        suspicious_only=suspicious_only,
        source_name_contains=src,
    )
    db.commit()
    return {"ok": True, **stats, "message": "Price refetch finished; see updated / skipped counts."}
