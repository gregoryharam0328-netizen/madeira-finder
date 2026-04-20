"""
Re-fetch individual portal listing pages and re-parse the asking price.

``listings_raw`` snapshots often contain the same bad card parse as ``listings``,
so ``repair_listings_from_last_raw`` cannot fix glue-prefix prices. This module
loads the live HTML (same selectors as search scrapers) and applies ``parse_eur_price``.
"""

from __future__ import annotations

import logging
import time
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import Listing, ListingRaw, Source
from app.scrapers.http import fetch_html, parse_eur_price, soup, strip_price_element_decorations
from app.services.listing_repair import _raw_item_dict, _resolve_raw
from app.services.normalization import canonicalize_url, normalize_listing
from app.services.dedup import upsert_listing

log = logging.getLogger(__name__)

# Detail + card selectors (Imovirtual + generic portal tiles)
_LISTING_PAGE_PRICE_SELECTORS: tuple[str, ...] = (
    '[data-cy="ad-price"]',
    '[data-cy="listing-item-price"]',
    '[data-cy="price"]',
    '[data-cy="offer-price"]',
)


def scrape_price_eur_from_listing_url(url: str) -> float | None:
    """
    GET the public listing page and extract a total asking price using the same
    parsing rules as ingestion (``parse_eur_price``).
    """
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return None
    # Imovirtual (and similar SPAs) are more reliable with a real browser.
    force_pw = "imovirtual" in u.lower()
    res = fetch_html(u, force_playwright=force_pw)
    if res.status_code >= 400 or not (res.html or "").strip():
        log.debug("refetch_price: bad response %s status=%s len=%s", u, res.status_code, len(res.html or ""))
        return None
    doc = soup(res.html)
    for sel in _LISTING_PAGE_PRICE_SELECTORS:
        el = doc.select_one(sel)
        if not el:
            continue
        strip_price_element_decorations(el)
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        p = parse_eur_price(txt)
        if p is not None:
            return float(p)
    blob = doc.get_text(" ", strip=True)[:14_000]
    p2 = parse_eur_price(blob)
    return float(p2) if p2 is not None else None


def _patch_raw_payload_price(raw: ListingRaw, new_price: float) -> None:
    j = raw.raw_payload_json
    if not isinstance(j, dict):
        return
    j = dict(j)
    j["price"] = float(new_price)
    raw.raw_payload_json = j
    flag_modified(raw, "raw_payload_json")


def refetch_suspicious_listing_prices(
    db: Session,
    *,
    limit: int = 300,
    delay_seconds: float = 0.7,
    suspicious_only: bool = True,
    source_name_contains: str | None = "imovirtual",
) -> dict[str, int]:
    """
    For matching active listings, fetch ``source_url`` HTML and replace price when
    the scraped value differs from the stored row. Patches the linked ``listings_raw``
    JSON so ``repair_listings_from_last_raw`` will not revert the fix.

    ``suspicious_only`` (default): rows with price ``> 2_000_000`` EUR, ``< 20_000`` EUR,
    or NULL — typical card-parse failure modes for this product.
    """
    stats = {
        "candidates": 0,
        "updated": 0,
        "unchanged": 0,
        "fetch_failed": 0,
        "no_raw": 0,
        "skipped_bad_url": 0,
    }

    q = db.query(Listing).join(Source, Source.id == Listing.source_id).filter(Listing.is_active.is_(True))
    if source_name_contains and source_name_contains.strip():
        q = q.filter(Source.name.ilike(f"%{source_name_contains.strip()}%"))
    if suspicious_only:
        q = q.filter(
            or_(
                Listing.price.is_(None),
                Listing.price < 20_000,
                Listing.price > 2_000_000,
            )
        )
    q = q.order_by(Listing.last_seen_at.desc()).limit(int(limit))
    rows = q.all()
    stats["candidates"] = len(rows)

    for listing in rows:
        url = (listing.source_url or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            stats["skipped_bad_url"] += 1
            continue
        raw = _resolve_raw(db, listing)
        if not raw:
            stats["no_raw"] += 1
            continue
        item = _raw_item_dict(raw)
        if not item:
            stats["no_raw"] += 1
            continue
        try:
            if canonicalize_url(item["url"]) != listing.canonical_url:
                stats["skipped_bad_url"] += 1
                continue
        except Exception:
            stats["skipped_bad_url"] += 1
            continue

        new_p = scrape_price_eur_from_listing_url(url)
        if new_p is None:
            stats["fetch_failed"] += 1
            log.warning("refetch_price: could not parse price for %s", url)
            time.sleep(delay_seconds)
            continue

        old_p = float(listing.price) if listing.price is not None else None
        if old_p is not None and abs(old_p - new_p) < 0.5:
            stats["unchanged"] += 1
            time.sleep(delay_seconds)
            continue

        item["price"] = new_p
        normalized = normalize_listing(item)
        _patch_raw_payload_price(raw, new_p)
        upsert_listing(db, source_id=listing.source_id, payload=normalized, raw_listing_id=raw.id)
        stats["updated"] += 1
        log.info("refetch_price: %s -> %s (was %s)", url, new_p, old_p)
        time.sleep(delay_seconds)

    return stats
