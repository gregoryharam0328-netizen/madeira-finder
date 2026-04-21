"""
Daily ingestion: for each scraped item we (1) keep an audit row in `listings_raw`
   so `listings.raw_listing_id` can point at it, then (2) upsert the canonical row
   in `listings` and link `listing_events` / `listing_groups` / `listing_group_members`
   inside `upsert_listing`. Dashboard 'New Today' uses `listings.first_seen_at`.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from app.config import settings
from app.database import SessionLocal
from app.models import ListingRaw, ScrapeRun, Source
from app.scrapers.factory import build_scrapers
from app.services.dedup import SourceListingLookupCache, upsert_listing
from app.services.digest import create_and_send_digests
from app.services.listing_repair import repair_listings_from_last_raw
from app.services.mock_cleanup import remove_mock_source_data
from app.services.normalization import (
    normalize_listing,
    passes_hard_bedroom_floor,
    passes_hard_property_type_floor,
)

log = logging.getLogger(__name__)


def _fetch_listings_safe(scraper):
    """Run one scraper; return (scraper, items, error). Used in parallel fetch phase."""
    try:
        return scraper, scraper.fetch_listings(), None
    except Exception as exc:  # pragma: no cover - network / portal variability
        log.exception("Scraper %s raised during fetch", scraper.name)
        return scraper, None, exc


def ensure_source(db, scraper_name: str) -> Source:
    source = db.query(Source).filter(Source.name == scraper_name).first()
    if source:
        return source
    source = Source(name=scraper_name, base_url="https://example.com", source_type="portal", priority=1)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def run() -> None:
    db = SessionLocal()
    total_inserted = 0
    total_updated = 0
    try:
        purged = remove_mock_source_data(db, commit=True)
        if purged.get("removed_source") or (purged.get("removed_listings") or 0) > 0:
            log.info("%s", purged.get("message"))

        scrapers = list(build_scrapers())
        fetch_results: list[tuple] = []
        if settings.scrape_parallel_sources and len(scrapers) > 1:
            workers = max(1, min(int(settings.scrape_parallel_max_workers), len(scrapers)))
            log.info("Fetching %s sources in parallel (max_workers=%s)", len(scrapers), workers)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_fetch_listings_safe, s): s for s in scrapers}
                for fut in as_completed(futures):
                    fetch_results.append(fut.result())
            order = {s.name: i for i, s in enumerate(scrapers)}
            fetch_results.sort(key=lambda t: order.get(t[0].name, 999))
        else:
            for s in scrapers:
                fetch_results.append(_fetch_listings_safe(s))

        for scraper, raw_items, fetch_exc in fetch_results:
            source = ensure_source(db, scraper.name)
            run = ScrapeRun(source_id=source.id, run_type="scheduled", status="running")
            db.add(run)
            db.commit()
            db.refresh(run)
            inserted = 0
            updated = 0
            if fetch_exc is not None:
                run.listings_found = 0
                run.status = "failed"
                run.finished_at = datetime.utcnow()
                run.error_log = str(fetch_exc)
                db.commit()
                continue

            if not isinstance(raw_items, list):
                raw_items = []
            run.listings_found = len(raw_items)
            skipped_bedroom_floor = 0
            skipped_property_type_floor = 0
            prepared: list[dict] = []
            for item in raw_items:
                allowed_type, normalized_type = passes_hard_property_type_floor(item)
                if not allowed_type:
                    skipped_property_type_floor += 1
                    continue
                # Keep normalized property type on raw payload for downstream consistency.
                item["property_type"] = normalized_type
                allowed, resolved_beds = passes_hard_bedroom_floor(item)
                if not allowed:
                    skipped_bedroom_floor += 1
                    continue
                # Keep a resolved bedroom count on the raw snapshot so downstream normalization is consistent.
                item["bedrooms"] = resolved_beds
                prepared.append(item)

            lookup_cache = SourceListingLookupCache()
            raw_rows: list[ListingRaw] = []
            for item in prepared:
                raw = ListingRaw(
                    scrape_run_id=run.id,
                    source_id=source.id,
                    source_listing_id=item.get("source_listing_id"),
                    source_url=item["url"],
                    raw_payload_json=item,
                )
                db.add(raw)
                raw_rows.append(raw)
            if raw_rows:
                db.flush()

            for item, raw in zip(prepared, raw_rows):
                normalized = normalize_listing(item)
                _listing, created = upsert_listing(
                    db,
                    source_id=source.id,
                    payload=normalized,
                    raw_listing_id=raw.id,
                    lookup_cache=lookup_cache,
                )
                inserted += int(created)
                updated += int(not created)
            run.status = "success"
            run.finished_at = datetime.utcnow()
            run.listings_inserted = inserted
            run.listings_updated = updated
            db.commit()
            total_inserted += inserted
            total_updated += updated
            log.info(
                "Ingestion source=%s raw=%s inserted=%s updated=%s skipped_non_residential=%s skipped_bedrooms_lt_%s=%s",
                scraper.name,
                len(raw_items),
                inserted,
                updated,
                skipped_property_type_floor,
                int(settings.min_bedrooms),
                skipped_bedroom_floor,
            )
            if not raw_items:
                log.warning("Scraper %s returned zero rows (see README: APIFY_TOKEN for Idealista).", scraper.name)

        csv_url = (getattr(settings, "idealista_csv_import_url", None) or "").strip()
        if csv_url:
            try:
                from app.services.idealista_csv_import import import_idealista_csv_from_url

                out = import_idealista_csv_from_url(db, csv_url)
                log.info("Idealista CSV import: %s", out.get("message", out))
            except Exception:
                log.exception("Idealista CSV import during daily run failed")
                db.rollback()

        try:
            n_rep = repair_listings_from_last_raw(db)
            if n_rep:
                db.commit()
        except Exception:
            log.exception("listing_repair step failed")
            db.rollback()

        create_and_send_digests(db)
        log.info("Daily run complete (total inserted=%s updated=%s).", total_inserted, total_updated)
        if total_inserted == 0 and total_updated == 0:
            log.warning(
                "No listing rows were written. Idealista needs APIFY_TOKEN; HTML sources may return "
                "nothing if selectors no longer match. Inspect table scrape_runs for error_log."
            )
    finally:
        db.close()


def run_logged() -> None:
    """Same as `run` but logs uncaught errors (for FastAPI BackgroundTasks)."""
    try:
        run()
    except Exception:
        log.exception("Daily ingestion failed with an uncaught error")


if __name__ == "__main__":
    run()
