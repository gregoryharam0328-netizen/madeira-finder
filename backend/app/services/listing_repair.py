"""
Reconcile `listings` with stored `listings_raw.raw_payload_json` when the row is clearly wrong:
missing image while raw has one, or price differs from the raw snapshot (bad card parsing, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import Listing, ListingRaw
from app.services.dedup import upsert_listing
from app.services.normalization import canonicalize_url, normalize_listing

log = logging.getLogger(__name__)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _raw_item_dict(raw: ListingRaw) -> dict[str, Any] | None:
    j = raw.raw_payload_json
    if not isinstance(j, dict):
        return None
    item = dict(j)
    url = item.get("url") or raw.source_url
    if not url:
        return None
    item["url"] = url
    return item


def _resolve_raw(db: Session, listing: Listing) -> ListingRaw | None:
    if listing.raw_listing_id:
        r = db.get(ListingRaw, listing.raw_listing_id)
        if r:
            return r
    if listing.source_url:
        return (
            db.query(ListingRaw)
            .filter(ListingRaw.source_id == listing.source_id, ListingRaw.source_url == listing.source_url)
            .order_by(ListingRaw.scraped_at.desc())
            .first()
        )
    return None


def _listing_needs_repair(listing: Listing, raw_json: dict[str, Any]) -> bool:
    raw_price = _float_or_none(raw_json.get("price"))
    db_price = _float_or_none(listing.price)
    no_image = not (listing.image_url or "").strip()
    raw_image = (raw_json.get("image_url") or "").strip()

    if no_image and raw_image:
        return True
    if raw_price is not None:
        if db_price is None or abs(db_price - raw_price) > 0.5:
            return True
    return False


def _same_display_core(listing: Listing, normalized: dict[str, Any]) -> bool:
    p1 = _float_or_none(listing.price)
    p2 = _float_or_none(normalized.get("price"))
    if p1 is None and p2 is None:
        pass
    elif p1 is None or p2 is None or abs(p1 - p2) > 0.5:
        return False
    i1 = (listing.image_url or "").strip()
    i2 = (normalized.get("image_url") or "").strip()
    return i1 == i2


def repair_listings_from_last_raw(db: Session, *, limit: int | None = None) -> int:
    """
    For active listings tied to raw rows, re-normalize from raw when image is missing or price disagrees.
    Returns count of rows passed to upsert_listing (updates only when data actually changes).
    """
    q = db.query(Listing).filter(Listing.is_active.is_(True))
    if limit is not None:
        q = q.limit(limit)
    rows = q.all()
    repaired = 0

    for listing in rows:
        raw = _resolve_raw(db, listing)
        if not raw:
            continue
        item = _raw_item_dict(raw)
        if not item:
            continue
        try:
            can = canonicalize_url(item["url"])
        except Exception:
            continue
        if can != listing.canonical_url:
            continue
        if not _listing_needs_repair(listing, item):
            continue
        normalized = normalize_listing(item)
        if _same_display_core(listing, normalized):
            continue
        # Dedup key is canonical_url per source — same listing row
        upsert_listing(db, source_id=listing.source_id, payload=normalized, raw_listing_id=raw.id)
        repaired += 1

    if repaired:
        log.info("listing_repair: updated %s listing(s) from listings_raw snapshots", repaired)
    return repaired
